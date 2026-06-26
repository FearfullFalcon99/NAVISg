import csv
import html
import re

import numpy as np
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QStatusBar, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QStackedWidget, QFrame, QScrollArea,
    QPushButton, QMenu, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from ui.input_panel import InputPanel
from ui.pvt_plots_widget import PVTPlotsWidget
from ui.plot_widget import PlotWidget
from ipr.standing import standing_ipr
from ipr.vogel import vogel_ipr
from engine.traverse import compute_vlp_curve, find_operating_point, compute_vlp_traverse


class Worker(QObject):
    finished = Signal(dict)
    error    = Signal(str)

    def __init__(self, params):
        super().__init__()
        self.p = params

    def run(self):
        try:
            p = dict(self.p)
            p.pop('t_sep', None)
            p.pop('p_sep', None)
            result = {}

            from pvt.fluid_properties import (
                bubblepoint_pressure,
                solution_gor,
                oil_volume_factor,
                live_oil_viscosity,
                z_factor,
                gas_volume_factor,
                gas_viscosity,
                water_density,
                water_volume_factor,
                water_viscosity,
            )
            pb_calc = bubblepoint_pressure(
                p['t_bh'], p['gor'], p['gas_sg'], p['oil_api'],
                pvt_correlation=p['pvt_correlation']
            )
            pb_user = p['pb']
            if pb_calc > 0 and abs(pb_user - pb_calc) / pb_calc < 0.5:
                pb = pb_user
            else:
                pb = pb_calc

            ipr_model = p.get('ipr_model', 'Vogel')
            if ipr_model == 'Standing':
                ipr_p, ipr_q, Qmax, J = standing_ipr(
                    Pr       = p['pr'],
                    Pwf_test = p['pwf_test'],
                    Qo_test  = p['qo_test'],
                    Pb       = pb,
                    fe_old   = p.get('fe_old', 1.0),
                    fe_new   = 1.0,
                    r_e      = p.get('re'),
                    r_w      = p.get('rw'),
                    skin     = p.get('skin'),
                )
            else:
                ipr_p, ipr_q, Qmax, J = vogel_ipr(
                    Pr       = p['pr'],
                    Pwf_test = p['pwf_test'],
                    Qo_test  = p['qo_test'],
                    Pb       = pb,
                )
            result['ipr']  = (ipr_q, ipr_p)
            result['Qmax'] = Qmax
            result['J']    = J
            result['pb_used'] = pb
            result['ipr_model'] = ipr_model

            rate_max = min(Qmax * 1.2, 5000)
            base_rates, base_bhps = compute_vlp_curve(
                whp        = p['whp'],
                well_depth = p['depth'],
                T_surf     = p['t_surf'],
                T_bh       = p['t_bh'],
                wor        = p['wor'],
                gor        = p['gor'],
                gas_sg     = p['gas_sg'],
                oil_api    = p['oil_api'],
                water_sg   = p['water_sg'],
                tubing_id  = p['tubing_id'],
                roughness  = p['roughness'],
                vlp_model  = p['vlp_model'],
                inclination_deg = p['inclination_deg'],
                rate_min   = 20,
                rate_max   = rate_max,
                n_rates    = 40,
                pvt_correlation = p['pvt_correlation']
            )
            result['base_vlp'] = {
                'rates': base_rates,
                'bhps': base_bhps,
                'label': f"{p['vlp_model']} VLP (WHP={p['whp']:.0f} psia)"
            }
            result['vlp_model'] = p['vlp_model']
            q_op, p_op = find_operating_point(base_rates, base_bhps, ipr_q, ipr_p)
            result['op_point'] = (q_op, p_op)

            traverse_rate = q_op if (q_op is not None and q_op > 0) else p['qo_test']
            traverse_data = compute_vlp_traverse(
                q_o        = traverse_rate,
                whp        = p['whp'],
                well_depth = p['depth'],
                T_surf     = p['t_surf'],
                T_bh       = p['t_bh'],
                wor        = p['wor'],
                gor        = p['gor'],
                gas_sg     = p['gas_sg'],
                oil_api    = p['oil_api'],
                water_sg   = p['water_sg'],
                tubing_id  = p['tubing_id'],
                roughness  = p['roughness'],
                vlp_model  = p['vlp_model'],
                inclination_deg = p['inclination_deg'],
                n_steps    = 20,
                pvt_correlation = p['pvt_correlation']
            )
            result['traverse_data'] = traverse_data
            result['traverse_rate'] = traverse_rate

            pvt_p = p_op if (p_op is not None and p_op > 0) else p['pwf_test']
            pvt_T = p['t_bh']

            from pvt.fluid_properties import fluid_properties_at_PT, z_factor, gas_volume_factor, live_oil_viscosity
            q_w = traverse_rate * p['wor']
            q_g = traverse_rate * p['gor'] / 1000.0

            fp = fluid_properties_at_PT(
                pvt_p, pvt_T, traverse_rate, q_w, q_g,
                p['gas_sg'], p['oil_api'], p['water_sg'],
                p['tubing_id'], p['gor'],
                pvt_correlation=p['pvt_correlation'],
                T_res=p['t_bh']
            )

            oil_sg = 141.5 / (131.5 + p['oil_api'])
            rho_oil = (62.4 * oil_sg + 0.0136 * p['gas_sg'] * fp['Rs']) / fp['Bo']
            mu_oil = live_oil_viscosity(
                pvt_T, p['oil_api'], fp['Rs'],
                p=pvt_p, pb=pb,
                pvt_correlation=p['pvt_correlation'],
                Rs_surface=p['gor'],
                gas_sg=p['gas_sg']
            )
            z_val = z_factor(pvt_p, pvt_T, p['gas_sg'])
            bg_val = gas_volume_factor(pvt_p, pvt_T, p['gas_sg'])

            result['pvt_output'] = {
                'pressure': pvt_p,
                'temperature': pvt_T,
                'Bo': fp['Bo'],
                'Rs': fp['Rs'],
                'rho_oil': rho_oil,
                'mu_oil': mu_oil,
                'Z': z_val,
                'Bg': bg_val,
            }

            p_min = 14.7
            p_max = max(p['pr'], pb, pvt_p) * 1.05
            pressures = np.linspace(p_min, p_max, 120)
            rs_surface = p['gor']
            oil_sg = 141.5 / (131.5 + p['oil_api'])

            rs_curve = []
            bo_curve = []
            mu_o_curve = []
            z_curve = []
            bg_curve = []
            mu_g_curve = []
            rho_w_curve = []
            bw_curve = []
            mu_w_curve = []

            for pressure in pressures:
                rs_val = rs_surface if pressure >= pb else min(
                    solution_gor(
                        pressure, pvt_T, p['gas_sg'], p['oil_api'],
                        pvt_correlation=p['pvt_correlation']
                    ),
                    rs_surface,
                )
                bo_val = oil_volume_factor(
                    pressure, pvt_T, rs_val, p['gas_sg'], p['oil_api'],
                    pb=pb, pvt_correlation=p['pvt_correlation'],
                    Rs_surface=rs_surface
                )
                mu_o_val = live_oil_viscosity(
                    pvt_T, p['oil_api'], rs_val,
                    p=pressure, pb=pb,
                    pvt_correlation=p['pvt_correlation'],
                    Rs_surface=rs_surface,
                    gas_sg=p['gas_sg']
                )
                z_val_curve = z_factor(pressure, pvt_T, p['gas_sg'])
                bg_val_curve = gas_volume_factor(pressure, pvt_T, p['gas_sg'])
                mu_g_val = gas_viscosity(pressure, pvt_T, p['gas_sg'])
                bw_val = water_volume_factor(pressure, pvt_T, p['water_sg'])
                mu_w_val = water_viscosity(pressure, pvt_T, p['water_sg'])
                rho_w_val = water_density(pressure, pvt_T, p['water_sg'])

                rs_curve.append(rs_val)
                bo_curve.append(bo_val)
                mu_o_curve.append(mu_o_val)
                z_curve.append(z_val_curve)
                bg_curve.append(bg_val_curve)
                mu_g_curve.append(mu_g_val)
                rho_w_curve.append(rho_w_val)
                bw_curve.append(bw_val)
                mu_w_curve.append(mu_w_val)

            result['pvt_plot_data'] = {
                'pressures': pressures,
                'Rs': np.asarray(rs_curve),
                'Bo': np.asarray(bo_curve),
                'mu_o': np.asarray(mu_o_curve),
                'Z': np.asarray(z_curve),
                'Bg': np.asarray(bg_curve),
                'mu_g': np.asarray(mu_g_curve),
                'rho_w': np.asarray(rho_w_curve),
                'Bw': np.asarray(bw_curve),
                'mu_w': np.asarray(mu_w_curve),
            }

            if p['sens_on'] != 'None':
                n      = int(p['sens_steps'])
                values = np.linspace(p['sens_min'], p['sens_max'], n)
                vlp_curves = []

                for v in values:
                    kw = dict(
                        whp        = p['whp'],
                        well_depth = p['depth'],
                        T_surf     = p['t_surf'],
                        T_bh       = p['t_bh'],
                        wor        = p['wor'],
                        gor        = p['gor'],
                        gas_sg     = p['gas_sg'],
                        oil_api    = p['oil_api'],
                        water_sg   = p['water_sg'],
                        tubing_id  = p['tubing_id'],
                        roughness  = p['roughness'],
                        vlp_model  = p['vlp_model'],
                        inclination_deg = p['inclination_deg'],
                        rate_min   = 20,
                        rate_max   = rate_max,
                        n_rates    = 40,
                        pvt_correlation = p['pvt_correlation']
                    )
                    if p['sens_on'] == 'WHP':
                        kw['whp'] = v;          lbl = f"WHP = {v:.0f} psia"
                    elif p['sens_on'] == 'GOR':
                        kw['gor'] = v;          lbl = f"GOR = {v:.0f} scf/STB"
                    elif p['sens_on'] == 'Tubing ID':
                        kw['tubing_id'] = v;    lbl = f"ID = {v:.3f} in"

                    rates, bhps = compute_vlp_curve(**kw)
                    vlp_curves.append({'rates': rates, 'bhps': bhps, 'label': lbl})

                result['sensitivity_curves'] = vlp_curves
                result['sens_on'] = p['sens_on']
            else:
                result['sensitivity_curves'] = []
                result['sens_on'] = 'None'

            self.finished.emit(result)

        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nodal Analysis  —  IPR / VLP")
        self.resize(1100, 700)

        central = QWidget()
        central.setObjectName("appShell")
        central.setStyleSheet("""
            QWidget#appShell {
                background-color: #d9e8f5;
            }
            QTabWidget {
                background-color: #d9e8f5;
            }
            QTabWidget::pane {
                background-color: #f5fbff;
                border: 1px solid #b8d4ee;
                border-radius: 6px;
            }
            QWidget#baseTab,
            QWidget#traverseTab,
            QWidget#pvtTab,
            QWidget#pvtPlotsTab,
            QWidget#sensTab {
                background-color: #f5fbff;
            }
            QScrollArea#pvtScroll,
            QWidget#pvtContainer {
                background-color: #d9e8f5;
            }
            QSplitter::handle {
                background-color: #d9e8f5;
                border: none;
                border-right: 1px solid #b8d4ee;
            }
            QSplitter::handle:horizontal {
                width: 4px;
            }
            QStatusBar {
                background-color: #b8d4ee;
                color: #12324f;
                border-top: 1px solid #78ade0;
            }
        """)
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self.input_panel = InputPanel()

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #b8d4ee;
                border-radius: 6px;
                background-color: #f5fbff;
            }
            QTabBar::tab {
                background: #b8d4ee;
                border: none;
                border-bottom: 2px solid transparent;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                color: #12324f;
            }
            QTabBar::tab:hover {
                background: #d9e8f5;
                color: #2068b1;
            }
            QTabBar::tab:selected {
                background: #f5fbff;
                color: #2068b1;
                border-bottom: 2px solid #2068b1;
            }
        """)

        self.base_tab = QWidget()
        self.base_tab.setObjectName("baseTab")
        base_layout = QVBoxLayout(self.base_tab)
        base_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_widget = PlotWidget()
        base_layout.addWidget(self.plot_widget)
        self.tabs.addTab(self.base_tab, "📈 IPR / VLP")

        self.traverse_tab = QWidget()
        self.traverse_tab.setObjectName("traverseTab")
        traverse_layout = QVBoxLayout(self.traverse_tab)
        traverse_layout.setContentsMargins(15, 15, 15, 15)
        traverse_layout.setSpacing(10)

        traverse_header_layout = QHBoxLayout()
        traverse_header_layout.setContentsMargins(0, 0, 0, 0)

        self.traverse_info_label = QLabel("<b>Wellbore Traverse Profile</b> (Depth vs Pressure/Temperature/Holdup/Regime)")
        self.traverse_info_label.setStyleSheet("font-size: 11px; color: #12324f;")
        self.traverse_info_label.setTextFormat(Qt.TextFormat.RichText)
        traverse_header_layout.addWidget(self.traverse_info_label, 1)

        self.export_traverse_btn = QPushButton("Export")
        self.export_traverse_btn.setFixedHeight(30)
        self.export_traverse_btn.setEnabled(False)
        self.export_traverse_btn.setToolTip("Export traverse table")
        self.export_traverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2068b1;
                border: none;
                border-radius: 5px;
                color: #ffffff;
                font-weight: 700;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #3c8eda;
            }
            QPushButton:disabled {
                background-color: #78ade0;
                color: #d9e8f5;
            }
            QPushButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)
        export_menu = QMenu(self.export_traverse_btn)
        export_menu.setStyleSheet("""
            QMenu {
                background-color: #f5fbff;
                border: 1px solid #78ade0;
                color: #12324f;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #b8d4ee;
                color: #12324f;
            }
        """)
        export_menu.addAction("Export as CSV", self.export_traverse_csv)
        export_menu.addAction("Export as PDF", self.export_traverse_pdf)
        self.export_traverse_btn.setMenu(export_menu)
        traverse_header_layout.addWidget(self.export_traverse_btn)

        traverse_layout.addLayout(traverse_header_layout)

        self.traverse_table = QTableWidget()
        self.traverse_table.setColumnCount(5)
        self.traverse_table.setHorizontalHeaderLabels([
            "Measured Depth (ft)",
            "Pressure (psia)",
            "Temperature (°F)",
            "Liquid Holdup",
            "Flow Regime"
        ])
        self.traverse_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.traverse_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.traverse_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.traverse_table.setAlternatingRowColors(True)
        self.traverse_table.setStyleSheet("""
            QTableWidget {
                background-color: #f5fbff;
                alternate-background-color: #d9e8f5;
                border: 1px solid #b8d4ee;
                gridline-color: #b8d4ee;
                color: #12324f;
                selection-background-color: #78ade0;
                selection-color: #12324f;
            }
            QHeaderView::section {
                background-color: #b8d4ee;
                border: 1px solid #78ade0;
                color: #12324f;
                padding: 6px;
                font-weight: bold;
            }
        """)
        traverse_layout.addWidget(self.traverse_table)
        self.tabs.addTab(self.traverse_tab, "📋 Traverse Table")

        self.pvt_tab = QWidget()
        self.pvt_tab.setObjectName("pvtTab")
        pvt_layout = QVBoxLayout(self.pvt_tab)
        pvt_layout.setContentsMargins(0, 0, 0, 0)

        pvt_scroll = QScrollArea()
        pvt_scroll.setObjectName("pvtScroll")
        pvt_scroll.setWidgetResizable(True)
        pvt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pvt_scroll.setBackgroundRole(self.palette().ColorRole.Window)

        pvt_container = QWidget()
        pvt_container.setObjectName("pvtContainer")
        pvt_main_layout = QVBoxLayout(pvt_container)
        pvt_main_layout.setContentsMargins(15, 15, 15, 15)
        pvt_main_layout.setSpacing(10)

        self.pvt_info_label = QLabel("<b>Fluid Properties</b> computed at flowing bottomhole pressure (operating point).")
        self.pvt_info_label.setStyleSheet("font-size: 11px; color: #12324f;")
        pvt_main_layout.addWidget(self.pvt_info_label)

        pvt_grid = QGridLayout()
        pvt_grid.setSpacing(12)

        self.pvt_widgets = {}
        properties = [
            ("pressure", "Operating Pressure", "psia"),
            ("temperature", "Operating Temperature", "°F"),
            ("Bo", "Oil Formation Volume Factor (Bo)", "bbl/STB"),
            ("Rs", "Solution GOR (Rs)", "scf/STB"),
            ("rho_oil", "Oil Density (ρ_oil)", "lb/ft³"),
            ("mu_oil", "Oil Viscosity (μ_oil)", "cP"),
            ("Z", "Gas Compressibility Factor (Z)", ""),
            ("Bg", "Gas Formation Volume Factor (Bg)", "bbl/scf"),
        ]

        for idx, (key, title, unit) in enumerate(properties):
            card, val_lbl = self.create_pvt_card(title, unit)
            self.pvt_widgets[key] = val_lbl
            row = idx // 2
            col = idx % 2
            pvt_grid.addWidget(card, row, col)

        pvt_main_layout.addLayout(pvt_grid)
        pvt_main_layout.addStretch()
        pvt_scroll.setWidget(pvt_container)
        pvt_layout.addWidget(pvt_scroll)
        self.tabs.addTab(self.pvt_tab, "🧪 PVT Output")

        self.pvt_plots_tab = QWidget()
        self.pvt_plots_tab.setObjectName("pvtPlotsTab")
        pvt_plots_layout = QVBoxLayout(self.pvt_plots_tab)
        pvt_plots_layout.setContentsMargins(0, 0, 0, 0)

        pvt_plots_scroll = QScrollArea()
        pvt_plots_scroll.setWidgetResizable(True)
        pvt_plots_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pvt_plots_scroll.setBackgroundRole(self.palette().ColorRole.Window)
        pvt_plots_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        pvt_plots_container = QWidget()
        pvt_plots_container.setObjectName("pvtPlotsContainer")
        pvt_plots_container_layout = QVBoxLayout(pvt_plots_container)
        pvt_plots_container_layout.setContentsMargins(15, 15, 15, 15)
        pvt_plots_container_layout.setSpacing(10)

        self.pvt_plots_widget = PVTPlotsWidget()
        pvt_plots_container_layout.addWidget(self.pvt_plots_widget)
        pvt_plots_scroll.setWidget(pvt_plots_container)
        pvt_plots_layout.addWidget(pvt_plots_scroll)
        self.tabs.addTab(self.pvt_plots_tab, "🧪 PVT Plots")

        self.sens_tab = QWidget()
        self.sens_tab.setObjectName("sensTab")
        sens_layout = QVBoxLayout(self.sens_tab)
        sens_layout.setContentsMargins(0, 0, 0, 0)

        self.sens_stack = QStackedWidget()

        self.sens_placeholder = QWidget()
        ph_layout = QVBoxLayout(self.sens_placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sens_ph_label = QLabel(
            "Sensitivity Analysis\n\n"
            "To view multi-curve overlays, configure the 'Sensitivity (VLP)' panel\n"
            "on the left (choose a variable to vary, e.g., GOR or WHP) and click 'Run Analysis'."
        )
        self.sens_ph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sens_ph_label.setStyleSheet("font-size: 13px; color: #12324f; line-height: 1.6;")
        ph_layout.addWidget(self.sens_ph_label)

        self.sens_plot_widget = PlotWidget()

        self.sens_stack.addWidget(self.sens_placeholder)
        self.sens_stack.addWidget(self.sens_plot_widget)
        self.sens_stack.setCurrentIndex(0)

        sens_layout.addWidget(self.sens_stack)
        self.tabs.addTab(self.sens_tab, "⚡ Sensitivity")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #d9e8f5;
                border: none;
                border-right: 1px solid #b8d4ee;
            }
            QSplitter::handle:horizontal {
                width: 4px;
            }
        """)
        splitter.setHandleWidth(4)
        splitter.addWidget(self.input_panel)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        h_layout.addWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready — fill inputs and click Run Analysis")

        self.input_panel.run_requested.connect(self.run_analysis)
        self._thread = None
        self._worker = None

    def create_pvt_card(self, title, unit):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #d9e8f5;
                border: 1px solid #b8d4ee;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #12324f; border: none; background: transparent;")

        val_lbl = QLabel("-")
        val_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #2068b1; border: none; background: transparent;")

        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet("font-size: 10px; color: #185f9d; border: none; background: transparent;")

        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        layout.addWidget(unit_lbl)

        return card, val_lbl

    def _traverse_table_data(self):
        headers = []
        for col in range(self.traverse_table.columnCount()):
            item = self.traverse_table.horizontalHeaderItem(col)
            headers.append(item.text() if item else "")

        rows = []
        for row in range(self.traverse_table.rowCount()):
            values = []
            for col in range(self.traverse_table.columnCount()):
                item = self.traverse_table.item(row, col)
                values.append(item.text() if item else "")
            rows.append(values)

        return headers, rows

    def _warn_no_traverse_data(self):
        QMessageBox.information(
            self,
            "No Traverse Data",
            "Run the analysis first to populate the traverse table.",
        )

    def export_traverse_csv(self):
        headers, rows = self._traverse_table_data()
        if not rows:
            self._warn_no_traverse_data()
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Traverse Table as CSV",
            "traverse_table.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            with open(path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(headers)
                writer.writerows(rows)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export CSV file:\n{exc}")
            return

        self.status.showMessage(f"Traverse table exported to CSV: {path}")

    def export_traverse_pdf(self):
        headers, rows = self._traverse_table_data()
        if not rows:
            self._warn_no_traverse_data()
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Traverse Table as PDF",
            "traverse_table.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        title = re.sub(r"<[^>]*>", "", self.traverse_info_label.text())
        header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
        rows_html = []
        for row in rows:
            cells = "".join(f"<td>{html.escape(value)}</td>" for value in row)
            rows_html.append(f"<tr>{cells}</tr>")

        html_doc = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
                h2 {{ color: #1a5fa8; font-size: 14pt; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #d6dde5; padding: 5px; text-align: left; }}
                th {{ background-color: #eef3f8; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
            </style>
        </head>
        <body>
            <h2>{html.escape(title)}</h2>
            <table>
                <thead><tr>{header_html}</tr></thead>
                <tbody>{"".join(rows_html)}</tbody>
            </table>
        </body>
        </html>
        """

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)

            document = QTextDocument()
            document.setHtml(html_doc)
            if hasattr(document, "print_"):
                document.print_(printer)
            else:
                document.print(printer)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export PDF file:\n{exc}")
            return

        self.status.showMessage(f"Traverse table exported to PDF: {path}")

    def run_analysis(self):
        params = self.input_panel.get_values()
        self.status.showMessage("Computing … please wait")
        self.input_panel.run_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = Worker(params)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_done(self, result):
        self.input_panel.run_btn.setEnabled(True)

        self.plot_widget.plot(
            ipr_data   = result.get('ipr'),
            vlp_curves = [result.get('base_vlp')] if result.get('base_vlp') else None,
            op_point   = result.get('op_point'),
        )

        traverse_data = result.get('traverse_data', [])
        traverse_rate = result.get('traverse_rate', 0)
        vlp_model = result.get('vlp_model', 'VLP')
        self.traverse_info_label.setText(
            f"<b>Wellbore Traverse Profile</b> ({vlp_model}) computed at operating point flow rate: <b>{traverse_rate:.0f} STB/d</b>"
        )
        self.traverse_table.setRowCount(len(traverse_data))
        for row_idx, row in enumerate(traverse_data):
            self.traverse_table.setItem(row_idx, 0, QTableWidgetItem(f"{row['depth']:.0f}"))
            self.traverse_table.setItem(row_idx, 1, QTableWidgetItem(f"{row['pressure']:.1f}"))
            self.traverse_table.setItem(row_idx, 2, QTableWidgetItem(f"{row['temperature']:.1f}"))
            self.traverse_table.setItem(row_idx, 3, QTableWidgetItem(f"{row['holdup']:.3f}"))
            regime = row.get('regime', '-')
            self.traverse_table.setItem(row_idx, 4, QTableWidgetItem(str(regime).replace('_', ' ').title()))
        self.export_traverse_btn.setEnabled(len(traverse_data) > 0)

        pvt_data = result.get('pvt_output', {})
        if pvt_data:
            self.pvt_info_label.setText(
                f"<b>Fluid Properties</b> calculated at flowing bottomhole pressure: <b>{pvt_data['pressure']:.1f} psia</b> and bottomhole temperature: <b>{pvt_data['temperature']:.1f} °F</b>"
            )
            self.pvt_widgets['pressure'].setText(f"{pvt_data['pressure']:.1f}")
            self.pvt_widgets['temperature'].setText(f"{pvt_data['temperature']:.1f}")
            self.pvt_widgets['Bo'].setText(f"{pvt_data['Bo']:.4f}")
            self.pvt_widgets['Rs'].setText(f"{pvt_data['Rs']:.1f}")
            self.pvt_widgets['rho_oil'].setText(f"{pvt_data['rho_oil']:.2f}")
            self.pvt_widgets['mu_oil'].setText(f"{pvt_data['mu_oil']:.3f}")
            self.pvt_widgets['Z'].setText(f"{pvt_data['Z']:.4f}")
            self.pvt_widgets['Bg'].setText(f"{pvt_data['Bg']:.6f}")
        else:
            self.pvt_info_label.setText("<b>Fluid Properties</b>: Run analysis to calculate values.")
            for widget in self.pvt_widgets.values():
                widget.setText("-")

        self.pvt_plots_widget.set_data(result.get('pvt_plot_data'))

        sens_curves = result.get('sensitivity_curves', [])
        sens_on = result.get('sens_on', 'None')

        if sens_on != 'None' and len(sens_curves) > 0:
            self.sens_stack.setCurrentIndex(1)
            self.sens_plot_widget.plot(
                ipr_data   = result.get('ipr'),
                vlp_curves = sens_curves,
                op_point   = (None, None),
            )
        else:
            self.sens_stack.setCurrentIndex(0)
            self.sens_plot_widget.clear()

        q_op, p_op = result.get('op_point', (None, None))
        Qmax = result.get('Qmax', 0)
        J    = result.get('J',    0)
        pb   = result.get('pb_used', 0)

        if q_op:
            eff = q_op / Qmax * 100 if Qmax > 0 else 0
            self.status.showMessage(
                f"✓  Qo = {q_op:.0f} STB/d  |  Pwf = {p_op:.0f} psia  |  "
                f"AOF = {Qmax:.0f} STB/d  |  PI = {J:.3f} STB/d/psi  |  "
                f"Pb = {pb:.0f} psia  |  Eff = {eff:.1f}%"
            )
        else:
            self.status.showMessage(
                f"✓  AOF = {Qmax:.0f} STB/d  |  PI = {J:.3f} STB/d/psi  |  Pb = {pb:.0f} psia"
            )

    def _on_error(self, msg):
        self.input_panel.run_btn.setEnabled(True)
        self.status.showMessage(f"Error: {msg}")
