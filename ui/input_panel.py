# new ui/input_panel.py----------------------------------------------------------------------------------
import csv
import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QAbstractSpinBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QScrollArea, QFrame, QToolButton, QHBoxLayout, QRadioButton, QTabWidget,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path
import sys

def _asset_path(filename: str) -> str:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return (base_dir / "assets" / filename).resolve().as_posix().replace("\\", "/")

class FetkovichTableWidget(QTableWidget):
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        # Create a new record whenever the user presses "Enter" at the last row
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.currentRow() == self.rowCount() - 1:
                self.insertRow(self.rowCount())
                self.setCurrentCell(self.rowCount() - 1, 0)

class FetkovichEvaluatorDialog(QDialog):
    def __init__(self, pr_val, parent=None):
        super().__init__(parent)
        self.pr_val = pr_val
        self.eval_C = None
        self.eval_n = None

        self.setWindowTitle(f"Fetkovich Evaluator (Pr = {self.pr_val} psia)")
        self.resize(650, 500)
        self.setStyleSheet("QDialog { background-color: #FAFAFA; }")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { background: #E8D0D0; padding: 6px 14px; font-weight: bold; border: 1px solid #D4C3C3; }
            QTabBar::tab:selected { background: #FFFFFF; color: #8B1E1E; }
        """)
        layout.addWidget(self.tabs)
        
        # --- 1. Data Tab ---
        self.data_tab = QWidget()
        data_layout = QVBoxLayout(self.data_tab)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(10) # Added spacing to ensure elements don't crush together
        mode_label = QLabel("Data Entry Mode:")
        mode_label.setStyleSheet("color: #2D1E1E; font-size: 13px;")
        mode_layout.addWidget(mode_label)

        # Added padding to QRadioButton to expand the bounding box and prevent text clipping
        radio_style = """
            QRadioButton { 
                color: #2D1E1E; 
                font-size: 12px; 
                margin-right: 4px; 
                padding: 2px 6px; 
            }
            QRadioButton::indicator { 
                width: 14px; 
                height: 14px; 
                border-radius: 7px; 
                border: 1px solid #D4C3C3; 
                background-color: #FFFFFF; 
            }
            QRadioButton::indicator:checked { 
                background-color: #005A9E; 
                border: 1px solid #FFFFFF; 
                outline: 1px solid #005A9E; 
            }
        """

        self.rb_manual = QRadioButton("Enter Manually")
        self.rb_csv = QRadioButton("Upload a CSV File")
        self.rb_demo = QRadioButton("See a Demo")
        
        for rb in [self.rb_manual, self.rb_csv, self.rb_demo]:
            rb.setStyleSheet(radio_style)
            mode_layout.addWidget(rb)
        
        mode_layout.addStretch()
        data_layout.addLayout(mode_layout)

        # CSV Upload Layout
        self.csv_widget = QWidget()
        csv_layout = QHBoxLayout(self.csv_widget)
        csv_layout.setContentsMargins(0, 5, 0, 5)
        self.btn_browse_csv = QPushButton("Browse CSV...")
        self.btn_browse_csv.setStyleSheet("""
        QPushButton {
            background-color: #E8D0D0;
            color: #FFFFFF;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
            border: none;
        }
        QPushButton:hover {
            background-color: #E8D0D0;
        }
        QPushButton:pressed {
            background-color: #8B1E1E;
        }""")
        self.btn_browse_csv.clicked.connect(self.upload_csv)
        self.lbl_csv_status = QLabel("No file selected.")
        self.lbl_csv_status.setStyleSheet("color: #4A4A4A; font-size: 13px;")
        csv_layout.addWidget(self.btn_browse_csv)
        csv_layout.addWidget(self.lbl_csv_status)
        csv_layout.addStretch()
        self.csv_widget.setVisible(False)
        data_layout.addWidget(self.csv_widget)

        self.lbl_csv_preview = QLabel("CSV Preview (First 10 rows):")
        self.lbl_csv_preview.setStyleSheet("color: #4A4A4A; font-size: 13px;")
        self.lbl_csv_preview.setVisible(False)
        data_layout.addWidget(self.lbl_csv_preview)

        # Connect Radio Buttons
        self.rb_manual.toggled.connect(self._on_mode_changed)
        self.rb_csv.toggled.connect(self._on_mode_changed)
        self.rb_demo.toggled.connect(self._on_mode_changed)

        self.table = FetkovichTableWidget(1, 2)
        self.table.setHorizontalHeaderLabels(["Liquid Production Rate (STB/d)", "FBHP (psi)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("background-color: #FFFFFF; alternate-background-color: #FAFAFA; border: 1px solid #D4C3C3;")
        data_layout.addWidget(self.table)

        bot_data_layout = QHBoxLayout()
        self.btn_eval = QPushButton("▶ Evaluate")
        self.btn_eval.setStyleSheet("background-color: #8B1E1E; color: #FFFFFF; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_eval.clicked.connect(self.evaluate_data)

        bot_data_layout.addWidget(self.btn_eval)
        bot_data_layout.addStretch()
        data_layout.addLayout(bot_data_layout)
        self.tabs.addTab(self.data_tab, "Data")
        
        self.rb_manual.setChecked(True)

        # --- 2. Results Tab ---
        self.res_tab = QWidget()
        res_layout = QVBoxLayout(self.res_tab)

        self.fig = Figure(figsize=(5, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        res_layout.addWidget(self.canvas)

        bot_res_layout = QHBoxLayout()
        bot_res_layout.addStretch()
        self.btn_use = QPushButton("Use")
        self.btn_use.setStyleSheet("background-color: #8B1E1E; color: #FFFFFF; font-weight: bold; padding: 8px 24px; border-radius: 4px;")
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self.accept)
        bot_res_layout.addWidget(self.btn_use)
        res_layout.addLayout(bot_res_layout)
        self.tabs.addTab(self.res_tab, "Results")

    def _on_mode_changed(self):
        is_csv = self.rb_csv.isChecked()
        self.csv_widget.setVisible(is_csv)
        self.lbl_csv_preview.setVisible(is_csv)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers if (self.rb_demo.isChecked() or is_csv) else QTableWidget.EditTrigger.AllEditTriggers)

        if self.rb_manual.isChecked():
            self.setup_manual()
        elif self.rb_demo.isChecked():
            self.load_demo()
        elif is_csv:
            self.table.clearContents()
            self.table.setRowCount(0)
            self.lbl_csv_status.setText("No file selected.")
    
    def setup_manual(self):
        self.table.setRowCount(1)
        self.table.clearContents()

    def load_demo(self):
        # Load Example 7-9 Data
        demo_data = [(263, 3170), (383, 2890), (497, 2440), (640, 2150)]
        self.table.setRowCount(len(demo_data))
        for i, (q, p) in enumerate(demo_data):
            self.table.setItem(i, 0, QTableWidgetItem(str(q)))
            self.table.setItem(i, 1, QTableWidgetItem(str(p)))

    def upload_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path: return
        self.lbl_csv_status.setText(Path(path).name)
        try:
            with open(path, newline='') as f:
                reader = list(csv.reader(f))
                start_idx = 1 if not reader[0][0].replace('.','',1).isdigit() else 0
                data = reader[start_idx:start_idx+10] 
                self.table.setRowCount(len(data))
                for i, row in enumerate(data):
                    if len(row) >= 2:
                        self.table.setItem(i, 0, QTableWidgetItem(row[0].strip()))
                        self.table.setItem(i, 1, QTableWidgetItem(row[1].strip()))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read CSV: {e}")

    def evaluate_data(self):
        q_vals, pwf_vals = [], []
        for r in range(self.table.rowCount()):
            q_it, p_it = self.table.item(r, 0), self.table.item(r, 1)
            if q_it and p_it and q_it.text().strip() and p_it.text().strip():
                try:
                    q_vals.append(float(q_it.text()))
                    pwf_vals.append(float(p_it.text()))
                except ValueError:
                    pass

        if len(q_vals) < 2:
            QMessageBox.warning(self, "Insufficient Data", "Please enter at least 2 valid data points.")
            return

        q_arr = np.array(q_vals)
        pwf_arr = np.array(pwf_vals)

        # 1. Calculate TRUE unscaled dp2 (Required for correct C and n mathematical evaluation)
        dp2_true = self.pr_val**2 - pwf_arr**2

        valid = dp2_true > 0
        q_arr, dp2_true = q_arr[valid], dp2_true[valid]
        if len(q_arr) < 2:
            QMessageBox.warning(self, "Invalid Data", "Check pressures. Must be less than Pr.")
            return

        # Evaluate Parameters C and n using TRUE unscaled values
        log_q = np.log10(q_arr)
        log_dp2 = np.log10(dp2_true)
        
        # --- ROBUST FITTING: Theil-Sen Estimator ---
        # Forces the line to pass through the maximum number of collinear points (ignores outliers)
        num_pts = len(log_q)
        if num_pts > 2:
            slopes = []
            for i in range(num_pts):
                for j in range(i + 1, num_pts):
                    dx = log_dp2[j] - log_dp2[i]
                    if abs(dx) > 1e-12:  # Prevent division by zero
                        slopes.append((log_q[j] - log_q[i]) / dx)
            
            n = float(np.median(slopes))
            log_C = float(np.median(log_q - n * log_dp2))
        else:
            # Fallback to simple linear fit if only 2 points are provided
            n, log_C = np.polyfit(log_dp2, log_q, 1)
        # -------------------------------------------

        self.eval_n = n
        self.eval_C = 10**log_C

        # 2. Scale dp2 for Plotting (Divide by 10^6 as per classical textbook representation)
        dp2_plot = dp2_true / 1e6

        # Generate the Plot
        self.ax.cla()
        self.ax.set_facecolor('#FFFFFF')
        self.fig.patch.set_facecolor('#FAFAFA')

        # Plot Fit Line
        # Calculate maximum possible Q (AOF) to draw the line all the way
        aof = self.eval_C * ((self.pr_val**2)**self.eval_n)
        q_fit = np.logspace(np.log10(np.min(q_arr) * 0.5), np.log10(aof), 50)
        
        # Calculate true dp2 for the line, then scale it down by 10^6 so it overlays the plot data
        dp2_fit_true = (q_fit / self.eval_C)**(1/self.eval_n)
        dp2_fit_plot = dp2_fit_true / 1e6
        
        self.ax.loglog(q_fit, dp2_fit_plot, '--', color='#2D1E1E', linewidth=2.5, label='Fetkovich Fit')

        # Plot Test Data
        self.ax.loglog(q_arr, dp2_plot, 'o', color='#8B1E1E', markersize=8, label='Test Data')

        self.ax.set_xlabel("Liquid Production Rate, Qo (STB/d)", fontsize=10, fontweight='bold')
        self.ax.set_ylabel(r"$(\bar{p}_r^2 - p_{wf}^2) \times 10^{-6}$ (psia$^2$)", fontsize=10, fontweight='bold')
        
        # Log-Log paper style grid
        self.ax.grid(True, which='major', color='#CCCCCC', linestyle='-', linewidth=0.8)
        self.ax.grid(True, which='minor', color='#E5E5E5', linestyle=':', linewidth=0.5)
        self.ax.legend(loc='upper left')

        # Translucent box in bottom-right corner
        bbox_props = dict(boxstyle="round,pad=0.5", fc="#FFFFFF", ec="#D4C3C3", alpha=0.9)
        text_str = f"C = {self.eval_C:.6f}\nn = {self.eval_n:.4f}\nAOF = {aof:.0f} STB/d"
        self.ax.text(0.95, 0.05, text_str, transform=self.ax.transAxes, fontsize=11, 
                     fontweight='bold', color='#8B1E1E', verticalalignment='bottom', 
                     horizontalalignment='right', bbox=bbox_props)

        self.canvas.draw()
        self.tabs.setCurrentIndex(1)
        self.btn_use.setEnabled(True)

class BaseInputPanel(QWidget):
    run_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_styles()

    def _disable_scroll(self, widget):
        """Intercepts and ignores wheel events to prevent accidental scroll changes."""
        widget.wheelEvent = lambda event: event.ignore()
        return widget

    def _apply_styles(self):
        spin_up_url = _asset_path("spin_up.svg")
        spin_down_url = _asset_path("spin_down.svg")
        style = """
            QWidget#inputPanel, QWidget#generalInputPanel, QWidget#gasLiftInputPanel {
                background-color: #FAFAFA;
                border-right: 1px solid #D4C3C3;
            }
            QScrollArea { background-color: #FAFAFA; border: none; }
            QScrollArea QScrollBar:vertical { background: #FAFAFA; width: 10px; margin: 2px; }
            QScrollArea QScrollBar::handle:vertical { background: #C0A0A0; min-height: 28px; border-radius: 4px; }
            QScrollArea QScrollBar::handle:vertical:hover { background: #8B1E1E; }
            QScrollArea QScrollBar::add-line:vertical, QScrollArea QScrollBar::sub-line:vertical { background: transparent; height: 0px; }
            
            QGroupBox {
                background-color: #FFFFFF; border: 1px solid #D4C3C3; border-radius: 6px;
                margin-top: 12px; padding: 14px 10px 10px 10px; color: #2D1E1E;
                font-weight: 600; font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: #8B1E1E; font-size: 13px; }
            QLabel { color: #2D1E1E; font-family: 'Segoe UI', Arial, sans-serif; }
            
            QDoubleSpinBox, QSpinBox, QComboBox {
                background-color: #FFFFFF; border: 1px solid #D4C3C3; border-radius: 4px;
                color: #2D1E1E; padding: 4px 30px 4px 8px;
                selection-background-color: #E8D0D0; selection-color: #2D1E1E;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px; /* Enlarged Font Size */
                min-width: 140px; max-width: 140px; min-height: 24px;
            }
            QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #8B1E1E; }
            
            QDoubleSpinBox::up-button, QSpinBox::up-button {
                subcontrol-origin: border; subcontrol-position: top right; width: 24px;
                background-color: #F0E8E8; border-left: 1px solid #D4C3C3; 
                border-bottom: 1px solid #D4C3C3; border-top-right-radius: 3px;
            }
            QDoubleSpinBox::down-button, QSpinBox::down-button {
                subcontrol-origin: border; subcontrol-position: bottom right; width: 24px;
                background-color: #F0E8E8; border-left: 1px solid #D4C3C3; border-bottom-right-radius: 3px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding; subcontrol-position: top right; width: 24px;
                border-left: 1px solid #D4C3C3; background-color: #F0E8E8;
                border-top-right-radius: 3px; border-bottom-right-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover,
            QComboBox::drop-down:hover { background-color: #D4C3C3; }
            QComboBox::down-arrow { image: url("__SPIN_DOWN_URL__"); width: 10px; height: 10px; }
            
            /* Run Button Synchronization */
            QPushButton#runBtn {
                background-color: #8B1E1E; color: #FFFFFF; font-size: 14px; font-weight: bold;
                padding: 10px; border-radius: 6px; min-height: 38px;
            }
            QPushButton#runBtn:hover { background-color: #A32B2B; }
            QPushButton#runBtn:disabled { background-color: #D4C3C3; color: #FAFAFA; }
        """
        self.setStyleSheet(style.replace("__SPIN_UP_URL__", spin_up_url).replace("__SPIN_DOWN_URL__", spin_down_url))
        
    def _style_form(self, form):
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

    def _dbl(self, mn, mx, val, suffix="", decimals=2):
        sb = QDoubleSpinBox()
        sb.setRange(mn, mx)
        sb.setValue(val)
        sb.setDecimals(decimals)
        sb.setSuffix(suffix)
        sb.setFixedHeight(26)
        sb.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        return self._disable_scroll(sb)

class GeneralInputPanel(BaseInputPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("generalInputPanel")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        self.content_layout = main_layout # Save layout reference for injection---------------------
        
        # 1. Reservoir (IPR) Group------------------------------------------------------------------
        ipr_group = QGroupBox("Reservoir Properties (IPR)")
        self.ipr_form = QFormLayout(ipr_group) # Saved as class attribute to access labels dynamically
        self._style_form(self.ipr_form)
        
        self.ipr_model = self._disable_scroll(QComboBox())
        self.ipr_model.addItems(["Vogel", "Composite IPR", "Standing", "General IPR", "Wiggins", "Fetkovich"])
        
        # --- Initialize all possible IPR inputs universally ---
        self.pr = self._dbl(500, 15000, 2500, " psia") # Always visible
        
        self.pb = self._dbl(100, 10000, 1800, " psia")
        self.pwf_test = self._dbl(100, 9000, 1200, " psia")
        self.qo_test = self._dbl(10, 10000, 800, " STB/d")
        
        self.fe_old = self._dbl(0.1, 5.0, 1.0, "", decimals=3)
        self.re     = self._dbl(10, 50000, 1000, " ft")
        self.rw     = self._dbl(0.01, 10.0, 0.328, " ft", decimals=3)
        self.skin   = self._dbl(-10.0, 10.0, 0.0, "", decimals=3)
        
        self.perm_k = self._dbl(0.01, 15000, 50.0, " md", decimals=2)
        self.thick_h = self._dbl(1.0, 2000, 30.0, " ft", decimals=1)
        self.kro     = self._dbl(0.01, 1.0, 1.0, "", decimals=3)
        
        self.fetkovich_n = self._dbl(0.5, 1.0, 1.0, "", decimals=3)
        self.fetkovich_c = self._dbl(0.00001, 10.0, 0.001, "", decimals=5)
        
        # --- Add rows to the form ---
        self.ipr_form.addRow("Model", self.ipr_model)
        self.ipr_form.addRow("Avg. Reservoir Pressure", self.pr)
        
        self.radio_direct = QRadioButton("Enter Values Directly")
        self.radio_eval = QRadioButton("Evaluate using Stabilized Flow data")
        self.radio_direct.setChecked(True)

        radio_style = """
            QRadioButton { color: #2D1E1E; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; margin-top: 2px; margin-bottom: 2px;}
            QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px; border: 1px solid #D4C3C3; background-color: #FFFFFF; }
            QRadioButton::indicator:checked { background-color: #8B1E1E; border: 3px solid #FFFFFF; outline: 1px solid #8B1E1E; }
        """
        self.radio_direct.setStyleSheet(radio_style)
        self.radio_eval.setStyleSheet(radio_style)

        # --- RESTRUCTURED: Stack Radio Buttons below the "Input Mode" Label ---
        mode_container = QVBoxLayout()
        mode_container.setContentsMargins(0, 4, 0, 4)
        mode_container.setSpacing(4)
        
        mode_label = QLabel("Input Mode:")
        mode_label.setStyleSheet("color: #2D1E1E; font-size: 13px;")
        mode_container.addWidget(mode_label)
        
        radio_layout = QVBoxLayout()
        radio_layout.setContentsMargins(15, 0, 0, 0) # Indents the radio buttons to the right
        radio_layout.setSpacing(2)
        radio_layout.addWidget(self.radio_direct)
        radio_layout.addWidget(self.radio_eval)
        
        mode_container.addLayout(radio_layout)

        self.fetkovich_mode_widget = QWidget()
        self.fetkovich_mode_widget.setLayout(mode_container)

        # Dictionary to track dynamically toggled widgets
        self.dynamic_ipr_widgets = {
            "pb": self.pb,
            "pwf_test": self.pwf_test,
            "qo_test": self.qo_test,
            "fe_old": self.fe_old,
            "re": self.re,
            "rw": self.rw,
            "skin": self.skin,
            "perm_k": self.perm_k,
            "thick_h": self.thick_h,
            "kro": self.kro,
            "fetkovich_mode": self.fetkovich_mode_widget,
            "fetkovich_c": self.fetkovich_c,
            "fetkovich_n": self.fetkovich_n
        }
        
        self.ipr_form.addRow("Bubble Point Pressure", self.pb)
        self.ipr_form.addRow("FBHP (test)", self.pwf_test)
        self.ipr_form.addRow("Flow Rate (test)", self.qo_test)
        self.ipr_form.addRow("FE test (Standing)", self.fe_old)
        self.ipr_form.addRow("Drainage radius (re)", self.re)
        self.ipr_form.addRow("Wellbore radius (rw)", self.rw)
        self.ipr_form.addRow("Skin (s)", self.skin)
        self.ipr_form.addRow("Abs. Permeability (k)", self.perm_k)
        self.ipr_form.addRow("Thickness (h)", self.thick_h)
        self.ipr_form.addRow("Rel. Permeability (kro)", self.kro)
        
        # Add the unified widget spanning both columns
        self.ipr_form.addRow(self.fetkovich_mode_widget)
        
        # --- FIX: Add the missing C and n variables to the layout to stop pop-ups ---
        self.ipr_form.addRow("Performance Coeff (C)", self.fetkovich_c)
        self.ipr_form.addRow("Flow Exponent (n)", self.fetkovich_n)
        
        self.radio_eval.toggled.connect(self._on_eval_mode_toggled)
        self.radio_direct.toggled.connect(self._toggle_ipr_fields)
        
        main_layout.addWidget(ipr_group)
        
        # Connect the dropdown and value changes to the dynamic toggle logic
        self.ipr_model.currentTextChanged.connect(self._toggle_ipr_fields)
        
        # --- NEW CODE: Dynamically trigger group box changes upon Pressure updates ---
        self.pr.valueChanged.connect(self._toggle_ipr_fields)
        self.pb.valueChanged.connect(self._toggle_ipr_fields)
        # -----------------------------------------------------------------------------
        
        self._toggle_ipr_fields() # Trigger immediately to set initial state

        # 2. Fluid Properties Group----------------------------------------------------------------
        fluid_group = QGroupBox("Fluid Properties")
        fluid_form = QFormLayout(fluid_group)
        self._style_form(fluid_form)
        self.pvt_correlation = self._disable_scroll(QComboBox())
        self.pvt_correlation.addItems(["Standing", "Kartoatmodjo"])
        self.oil_api = self._dbl(10, 60, 35, " °API")
        self.gas_sg = self._dbl(0.55, 1.1, 0.65, "", decimals=3)
        self.water_sg = self._dbl(1.0, 1.15, 1.07, "", decimals=3)
        self.gor = self._dbl(50, 5000, 500, " scf/STB")
        self.wor = self._dbl(0, 100, 50, " %")
        fluid_form.addRow("PVT Correlation", self.pvt_correlation)
        fluid_form.addRow("Oil API", self.oil_api)
        fluid_form.addRow("Gas Sp.Gravity", self.gas_sg)
        fluid_form.addRow("Water Sp.Gravity", self.water_sg)
        fluid_form.addRow("GLR", self.gor)
        fluid_form.addRow("Water Cut", self.wor)
        main_layout.addWidget(fluid_group)

        # 3. Well & Tubing (VLP) Group--------------------------------------------------------------
        well_group = QGroupBox("Completion Properties (VLP)")
        well_form = QFormLayout(well_group)
        self._style_form(well_form)
        
        self.vlp_model = self._disable_scroll(QComboBox())
        self.vlp_model.addItems(["Hagedorn-Brown", "Beggs-Brill", "Duns-Ros"])
        self.depth = self._dbl(500, 20000, 6000, " ft")
        self.tubing_id = self._dbl(0.5, 6.0, 2.441, " in", decimals=3)
        self.whp = self._dbl(0.0, 3000, 150, " psia", decimals=3)
        self.t_surf = self._dbl(0, 500, 80.0, " °F")
        self.t_bh = self._dbl(0, 500, 180.0, " °F")
        self.roughness = self._dbl(0.00001, 0.1, 0.0006, "", decimals=5)
        self.inclination_deg = self._dbl(0.0, 90.0, 90.0, " °")
        
        well_form.addRow("Correlation", self.vlp_model)
        well_form.addRow("Depth (TVD)", self.depth)
        well_form.addRow("Tubing ID", self.tubing_id)
        well_form.addRow("WHP", self.whp)
        well_form.addRow("Surface Temp", self.t_surf)
        well_form.addRow("Bottomhole Temp", self.t_bh)
        well_form.addRow("Pipe Roughness", self.roughness)
        well_form.addRow("Inclination", self.inclination_deg)
        main_layout.addWidget(well_group)
        
        # 4. Sensitivity--------------------------------------------------------------------
        self.sens_group = QGroupBox("Sensitivity (VLP)")
        sens_form  = QFormLayout(self.sens_group)
        sens_form.setSpacing(5)
        self._style_form(sens_form)

        self.sens_on = self._disable_scroll(QComboBox())
        self.sens_on.setMinimumWidth(155)
        self.sens_on.addItems(["None", "WHP", "GLR", "Tubing ID"])
        self.sens_min   = self._dbl(0, 9999, 100, "")
        self.sens_max   = self._dbl(0, 9999, 400, "")
        self.sens_steps = self._disable_scroll(QSpinBox())
        self.sens_steps.setRange(2, 10)
        self.sens_steps.setValue(3)
        self.sens_steps.setFixedHeight(26)
        self.sens_steps.setMinimumWidth(155)

        sens_form.addRow("Vary",       self.sens_on)
        sens_form.addRow("Min value",  self.sens_min)
        sens_form.addRow("Max value",  self.sens_max)
        sens_form.addRow("Steps",      self.sens_steps)
        main_layout.addWidget(self.sens_group)

        main_layout.addStretch()
        
    # ── Run button ────────────────────────────────────────────────────
        
        self.run_btn = QPushButton("▶ Evaluate Nodal Analysis")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_requested.emit)
        main_layout.addWidget(self.run_btn)
        
        scroll.setWidget(container)
        QVBoxLayout(self).addWidget(scroll)

    # -------------------------------------------------------------------------------
    def _on_eval_mode_toggled(self, checked):
        if checked:
            self._open_fetkovich_evaluator()
        self._toggle_ipr_fields()

    def _open_fetkovich_evaluator(self):
        dialog = FetkovichEvaluatorDialog(pr_val=self.pr.value(), parent=self)
        if dialog.exec():
            self.fetkovich_c.setValue(dialog.eval_C)
            self.fetkovich_n.setValue(dialog.eval_n)
            self.radio_direct.setChecked(True)
        else:
            self.radio_direct.setChecked(True) # Revert to direct if canceled
    
    def _toggle_ipr_fields(self):
        model = self.ipr_model.currentText()
        pr_val = self.pr.value()
        pb_val = self.pb.value()

        fetkovich_fields = ["pb"]
        if pr_val <= pb_val:
            fetkovich_fields.append("fetkovich_mode")
            if self.radio_direct.isChecked():
                fetkovich_fields.extend(["fetkovich_c", "fetkovich_n"])
        else:
            fetkovich_fields.extend(["pwf_test", "qo_test"])
            
        fields_map = {
            "Vogel": ["pb", "pwf_test", "qo_test"],
            "Composite IPR": ["pb", "pwf_test", "qo_test"],
            "Standing": ["pb", "pwf_test", "qo_test", "fe_old", "re", "rw", "skin"],
            "General IPR": ["pb", "perm_k", "thick_h", "re", "rw", "skin", "kro"], # Safely retained pb
            "Wiggins": ["pb", "pwf_test", "qo_test"],
            "Fetkovich": fetkovich_fields
        }
        
        active_fields = fields_map.get(model, [])
        for name, widget in self.dynamic_ipr_widgets.items():
            is_visible = name in active_fields
            widget.setVisible(is_visible)
            label = self.ipr_form.labelForField(widget)
            if label:
                label.setVisible(is_visible)

    def get_values(self):
        return {
            "ipr_model": self.ipr_model.currentText(), 
            "pr": self.pr.value(), "pb": self.pb.value(),
            "pwf_test": self.pwf_test.value(), 
            "qo_test": self.qo_test.value(),
            "fe_old": self.fe_old.value(),
            "re": self.re.value(),
            "rw": self.rw.value(),
            "skin": self.skin.value(),
            "perm_k": self.perm_k.value(),
            "thick_h": self.thick_h.value(),
            "kro": self.kro.value(),
            "pvt_correlation": self.pvt_correlation.currentText(), 
            "oil_api": self.oil_api.value(), 
            "gas_sg": self.gas_sg.value(), 
            "water_sg": self.water_sg.value(), 
            "gor": self.gor.value(), 
            "wor": self.wor.value(),
            "vlp_model": self.vlp_model.currentText(), 
            "depth": self.depth.value(), 
            "tubing_id": self.tubing_id.value(),
            "whp": self.whp.value(), 
            "t_surf": self.t_surf.value(), 
            "t_bh": self.t_bh.value(),
            "roughness": self.roughness.value(), 
            "inclination_deg": self.inclination_deg.value(),
            "sens_on": self.sens_on.currentText(), 
            "sens_min": self.sens_min.value(), 
            "sens_max": self.sens_max.value(), 
            "sens_steps": self.sens_steps.value(),
            "fetkovich_c": self.fetkovich_c.value(),
            "fetkovich_n": self.fetkovich_n.value(),
            "fetkovich_mode": "Enter Values Directly" if self.radio_direct.isChecked() else "Evaluate"
        }

    def set_values(self, vals):
        if "ipr_model" in vals: self.ipr_model.setCurrentText(vals["ipr_model"])
        if "pr" in vals: self.pr.setValue(vals["pr"])
        if "pb" in vals: self.pb.setValue(vals["pb"])
        if "pwf_test" in vals: self.pwf_test.setValue(vals["pwf_test"])
        if "qo_test" in vals: self.qo_test.setValue(vals["qo_test"])
        if "fe_old" in vals: self.fe_old.setValue(vals["fe_old"])
        if "re" in vals: self.re.setValue(vals["re"])
        if "rw" in vals: self.rw.setValue(vals["rw"])
        if "skin" in vals: self.skin.setValue(vals["skin"])
        if "perm_k" in vals: self.perm_k.setValue(vals["perm_k"])
        if "thick_h" in vals: self.thick_h.setValue(vals["thick_h"])
        if "kro" in vals: self.kro.setValue(vals["kro"])
        if "pvt_correlation" in vals: self.pvt_correlation.setCurrentText(vals["pvt_correlation"])
        if "oil_api" in vals: self.oil_api.setValue(vals["oil_api"])
        if "gas_sg" in vals: self.gas_sg.setValue(vals["gas_sg"])
        if "water_sg" in vals: self.water_sg.setValue(vals["water_sg"])
        if "gor" in vals: self.gor.setValue(vals["gor"])
        if "wor" in vals: self.wor.setValue(vals["wor"])
        if "vlp_model" in vals: self.vlp_model.setCurrentText(vals["vlp_model"])
        if "depth" in vals: self.depth.setValue(vals["depth"])
        if "tubing_id" in vals: self.tubing_id.setValue(vals["tubing_id"])
        if "whp" in vals: self.whp.setValue(vals["whp"])
        if "t_surf" in vals: self.t_surf.setValue(vals["t_surf"])
        if "t_bh" in vals: self.t_bh.setValue(vals["t_bh"])
        if "roughness" in vals: self.roughness.setValue(vals["roughness"])
        if "inclination_deg" in vals: self.inclination_deg.setValue(vals["inclination_deg"])
        if "sens_on" in vals: self.sens_on.setCurrentText(vals["sens_on"])
        if "sens_min" in vals: self.sens_min.setValue(vals["sens_min"])
        if "sens_max" in vals: self.sens_max.setValue(vals["sens_max"])
        if "sens_steps" in vals: self.sens_steps.setValue(vals["sens_steps"])
        if "fetkovich_c" in vals: self.fetkovich_c.setValue(vals["fetkovich_c"])
        if "fetkovich_n" in vals: self.fetkovich_n.setValue(vals["fetkovich_n"])
        if "fetkovich_mode" in vals:
            if vals["fetkovich_mode"] == "Enter Values Directly": self.radio_direct.setChecked(True)
            else: self.radio_eval.setChecked(True)   
# ------------------------------------------------------------------------------------------
    
class GasLiftInputPanel(BaseInputPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gasLiftInputPanel")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        
        target_group = QGroupBox("Design Targets")
        target_form = QFormLayout(target_group)
        self._style_form(target_form)
        self.target_q = self._dbl(10, 20000, 1000, " STB/d")
        self.target_pwf = self._dbl(10, 10000, 1500, " psia")
        target_form.addRow("Target Rate", self.target_q)
        target_form.addRow("Target Pwf", self.target_pwf)
        main_layout.addWidget(target_group)

        gl_group = QGroupBox("Injection Parameters")
        gl_form = QFormLayout(gl_group)
        self._style_form(gl_form)
        self.inj_depth = self._dbl(500, 20000, 8000, " ft") 
        self.base_glr = self._dbl(0, 10000, 300, " SCF/STB")
        self.target_glr = self._dbl(0, 10000, 400, " SCF/STB")
        
        gl_form.addRow("Inj. Depth (H)", self.inj_depth)
        gl_form.addRow("Reservoir GLR", self.base_glr)
        gl_form.addRow("Target GLR", self.target_glr)
        main_layout.addWidget(gl_group)

        main_layout.addStretch()
        self.run_btn = QPushButton("▶ Evaluate Lift Potential")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_requested.emit)
        main_layout.addWidget(self.run_btn)
        
        scroll.setWidget(container)
        QVBoxLayout(self).addWidget(scroll)

    def get_values(self):
        return {
            "target_q": self.target_q.value(), 
            "target_pwf": self.target_pwf.value(),
            "inj_depth": self.inj_depth.value(), 
            "base_glr": self.base_glr.value(),
            "target_glr": self.target_glr.value()
        }
        
# Constant WHP Panel ----------------------------------------------------------------

class GasLiftDesignInputPanel(GeneralInputPanel):
    # Custom signal to notify the main window that data transfer is requested
    pull_requested = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gasLiftDesignInputPanel")
        
        # --- NEW: Carry Forward Button ---
        self.btn_carry_forward = QPushButton("⟳ Carry Forward General Inputs")
        self.btn_carry_forward.setToolTip("Pull the current values from the General Production Evaluation tab.")
        self.btn_carry_forward.setStyleSheet("""
            QPushButton {
                background-color: #F0E8E8; color: #8B1E1E; font-size: 13px; font-weight: bold;
                padding: 8px; border: 1px solid #D4C3C3; border-radius: 6px; margin-bottom: 8px;
            }
            QPushButton:hover { background-color: #E8D0D0; }
            QPushButton:pressed { background-color: #D4C3C3; }
        """)
        self.btn_carry_forward.clicked.connect(self.pull_requested.emit)
        
        # Insert the button at the very top of the scrollable layout (index 0)
        self.content_layout.insertWidget(0, self.btn_carry_forward)
        # ---------------------------------

        # Inject Gas Lift Specifics Group Box
        self.gl_group = QGroupBox("Gas Lift Injection Parameters")
        self.gl_form = QFormLayout(self.gl_group)
        self._style_form(self.gl_form)
        
        self.supply_type = self._disable_scroll(QComboBox())
        self.supply_type.addItems(["Unlimited", "Limited"])
        
        self.pinj = self._dbl(100, 10000, 1000, " psia")
        self.inj_gas_sg = self._dbl(0.5, 1.5, 0.6, "", decimals=3)
        self.valve_dp = self._dbl(0, 1000, 100, " psia")
        self.qg_avail = self._dbl(10, 50000, 1000, " Mscf/d")
        
        self.gl_form.addRow("Supply Range", self.supply_type)
        self.gl_form.addRow("Surface Inj. Pressure", self.pinj)
        self.gl_form.addRow("Inj. Gas Sp. Gravity", self.inj_gas_sg)
        self.gl_form.addRow("Valve Differential (ΔP)", self.valve_dp)
        self.gl_form.addRow("Available Gas Rate (Qg)", self.qg_avail)
        
        # Hide Sensitivity and replace its spatial slot
        self.sens_group.setVisible(False)
        self.content_layout.insertWidget(self.content_layout.indexOf(self.sens_group), self.gl_group)
        
        # Connect the dropdown to the dynamic toggle logic
        self.supply_type.currentTextChanged.connect(self._toggle_supply_fields)
        self._toggle_supply_fields() # Trigger immediately to set initial state

    def _toggle_supply_fields(self):
        """Dynamically shows/hides QFormLayout rows based on the Supply Range."""
        is_limited = self.supply_type.currentText() == "Limited"
        
        # Toggle visibility for both the widget and its label
        self.qg_avail.setVisible(is_limited)
        label = self.gl_form.labelForField(self.qg_avail)
        if label:
            label.setVisible(is_limited)
            
        # Update Run Button Title
        if is_limited:
            self.run_btn.setText("▶ Evaluate Gas Lift (Limited Supply)")
        else:
            self.run_btn.setText("▶ Evaluate Gas Lift (Unlimited Supply)")

    def get_values(self):
        vals = super().get_values()
        vals.update({
            "supply_type": self.supply_type.currentText(),
            "pinj": self.pinj.value(),
            "inj_gas_sg": self.inj_gas_sg.value(),
            "valve_dp": self.valve_dp.value(),
            "qg_avail": self.qg_avail.value()
        })
        return vals
    
class FutureIPRInputPanel(BaseInputPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("futureIPRInputPanel")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        
        # --- Group 1: Current Reservoir Parameters ---
        curr_group = QGroupBox("Current Reservoir Parameters")
        self.curr_form = QFormLayout(curr_group)
        self._style_form(self.curr_form)
        
        # POINT 5: Remove IPR Model Dropdown, fix it to a bold label carrying over from Current IPR
        self.model_display = QLabel("Vogel")
        self.model_display.setStyleSheet("color: #8B1E1E; font-weight: bold; font-size: 14px;")
        self.curr_form.addRow("Fixed IPR Model", self.model_display)
        
        self.pr_p = self._dbl(500, 15000, 2500, " psia")
        self.pb = self._dbl(100, 10000, 1800, " psia")
        self.pwf_test = self._dbl(100, 9000, 1200, " psia")
        self.qo_test = self._dbl(10, 10000, 800, " STB/d")
        self.fetkovich_c = self._dbl(0.00001, 10.0, 0.001, "", decimals=5)
        self.fetkovich_n = self._dbl(0.5, 1.0, 1.0, "", decimals=3)
        
        self.curr_form.addRow("Current Avg. Pressure (Pr)", self.pr_p)
        self.curr_form.addRow("Bubble Point (Pb)", self.pb)
        self.curr_form.addRow("Test FBHP (Pwf)", self.pwf_test)
        self.curr_form.addRow("Test Rate (Qo)", self.qo_test)
        self.curr_form.addRow("Current Perf. Coeff (C_p)", self.fetkovich_c)
        self.curr_form.addRow("Current Flow Exp. (n_p)", self.fetkovich_n)
        
        # POINT 1: Input Mode functionality removed entirely from the Future IPR Tab
        
        main_layout.addWidget(curr_group)
        
        # --- Group 2: Future Evaluation Parameters ---
        fut_group = QGroupBox("Future Evaluation Parameters")
        self.fut_form = QFormLayout(fut_group) 
        self._style_form(self.fut_form)
        
        self.pr_f = self._dbl(100, 15000, 1500, " psia")
        
        self.method = self._disable_scroll(QComboBox())
        self.method.addItems(["First Approximation", "Second Approximation"])
        self.method.setEnabled(False) # Made read-only as it will automatically pick the best case
        
        self.fut_form.addRow("Future Avg. Pressure (Pr_f)", self.pr_f)
        self.fut_form.addRow("Approximation Method", self.method)
        main_layout.addWidget(fut_group)
        
        # Signals to trigger UI Dynamics
        self.pr_p.valueChanged.connect(self._toggle_future_fields)
        self.pb.valueChanged.connect(self._toggle_future_fields)
        self.pr_f.valueChanged.connect(self._toggle_future_fields)
        
        main_layout.addStretch()
        
        self.run_btn = QPushButton("▶ Evaluate Future IPR")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_requested.emit)
        main_layout.addWidget(self.run_btn)
        
        scroll.setWidget(container)
        QVBoxLayout(self).addWidget(scroll)
        
        self._toggle_future_fields() # Set initial state
    
    def _toggle_future_fields(self):
        # POINT 2: Dynamically change the IPR group according to the best suiting case based on pressures
        model = self.model_display.text()
        
        is_vogel = (model == "Vogel")
        is_fetkovich = (model == "Fetkovich")
        is_wiggins = (model == "Wiggins")
        
        pr_val = self.pr_p.value()
        pb_val = self.pb.value()
        prf_val = self.pr_f.value()

        # Vogel Logic Configuration
        self.method.setVisible(is_vogel)
        lbl_method = self.fut_form.labelForField(self.method)
        if lbl_method: lbl_method.setVisible(is_vogel)
        
        if is_vogel:
            # Dynamically select First or Second Approx based strictly on Future Pr vs Pb
            if prf_val > pb_val:
                self.method.setCurrentText("First Approximation")
            else:
                self.method.setCurrentText("Second Approximation")

        # Test Data Visibility logic
        show_test = is_vogel or is_wiggins or (is_fetkovich and pr_val > pb_val)
        for widget in [self.pwf_test, self.qo_test]:
            widget.setVisible(show_test)
            lbl = self.curr_form.labelForField(widget)
            if lbl: lbl.setVisible(show_test)

        # Fetkovich C and n Visibility logic
        show_cn = is_fetkovich and (pr_val <= pb_val)
        for widget in [self.fetkovich_c, self.fetkovich_n]:
            widget.setVisible(show_cn)
            lbl = self.curr_form.labelForField(widget)
            if lbl: lbl.setVisible(show_cn)

    def get_values(self):
        return {
            "ipr_model": self.model_display.text(),
            "pr_p": self.pr_p.value(), 
            "pb": self.pb.value(),
            "pwf_test": self.pwf_test.value(), 
            "qo_test": self.qo_test.value(),
            "pr_f": self.pr_f.value(), 
            "method": 1 if self.method.currentText() == "First Approximation" else 2,
            "fetkovich_c": self.fetkovich_c.value(),
            "fetkovich_n": self.fetkovich_n.value()
        }
        
    def set_values(self, vals):
        if "ipr_model" in vals: self.model_display.setText(vals["ipr_model"])
        if "pr_p" in vals: self.pr_p.setValue(vals["pr_p"])
        if "pb" in vals: self.pb.setValue(vals["pb"])
        if "pwf_test" in vals: self.pwf_test.setValue(vals["pwf_test"])
        if "qo_test" in vals: self.qo_test.setValue(vals["qo_test"])
        if "fetkovich_c" in vals: self.fetkovich_c.setValue(vals["fetkovich_c"])
        if "fetkovich_n" in vals: self.fetkovich_n.setValue(vals["fetkovich_n"])
        
        self._toggle_future_fields()