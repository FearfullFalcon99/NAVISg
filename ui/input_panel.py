from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QAbstractSpinBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QScrollArea, QFrame, QToolButton, QHBoxLayout
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path


class InputPanel(QWidget):
    run_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inputPanel")
        self.setFixedWidth(310)
        spin_up_icon = Path(__file__).resolve().parents[1] / "assets" / "spin_up.svg"
        spin_down_icon = Path(__file__).resolve().parents[1] / "assets" / "spin_down.svg"
        spin_up_url = spin_up_icon.as_posix()
        spin_down_url = spin_down_icon.as_posix()
        style = """
            QWidget#inputPanel {
                background-color: #d9e8f5;
                border-right: 1px solid #78ade0;
            }
            QScrollArea#inputScroll,
            QWidget#inputContainer {
                background-color: #d9e8f5;
            }
            QScrollArea#inputScroll QScrollBar:vertical {
                background: #d9e8f5;
                width: 12px;
                margin: 2px;
            }
            QScrollArea#inputScroll QScrollBar::groove:vertical {
                background: #d9e8f5;
                border: none;
                border-radius: 5px;
            }
            QScrollArea#inputScroll QScrollBar::handle:vertical {
                background: #78ade0;
                min-height: 28px;
                border-radius: 5px;
            }
            QScrollArea#inputScroll QScrollBar::handle:vertical:hover {
                background: #2068b1;
            }
            QScrollArea#inputScroll QScrollBar::add-line:vertical,
            QScrollArea#inputScroll QScrollBar::sub-line:vertical {
                background: #b8d4ee;
                border: none;
                height: 0px;
            }
            QScrollArea#inputScroll QScrollBar::up-arrow:vertical,
            QScrollArea#inputScroll QScrollBar::down-arrow:vertical {
                background: transparent;
                width: 0px;
                height: 0px;
            }
            QGroupBox {
                background-color: #f5fbff;
                border: 1px solid #b8d4ee;
                border-radius: 7px;
                margin-top: 8px;
                padding: 10px 8px 8px 8px;
                color: #12324f;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                left: 8px;
                color: #2068b1;
            }
            QLabel {
                color: #12324f;
            }
            QDoubleSpinBox,
            QSpinBox,
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #78ade0;
                border-radius: 5px;
                color: #12324f;
                padding: 2px 6px;
                selection-background-color: #b8d4ee;
                selection-color: #12324f;
            }
            QDoubleSpinBox:focus,
            QSpinBox:focus,
            QComboBox:focus {
                border: 1px solid #2068b1;
                background-color: #ffffff;
            }
            QDoubleSpinBox::up-button,
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
                background-color: #b8d4ee;
                border-left: 1px solid #78ade0;
                border-bottom: 1px solid #78ade0;
                border-top-right-radius: 5px;
            }
            QDoubleSpinBox::down-button,
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
                background-color: #b8d4ee;
                border-left: 1px solid #78ade0;
                border-bottom-right-radius: 5px;
            }
            QDoubleSpinBox::up-button:hover,
            QSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover,
            QSpinBox::down-button:hover {
                background-color: #78ade0;
            }
            QDoubleSpinBox::up-arrow,
            QSpinBox::up-arrow {
                image: url("__SPIN_UP_URL__");
                width: 10px;
                height: 10px;
            }
            QDoubleSpinBox::down-arrow,
            QSpinBox::down-arrow {
                image: url("__SPIN_DOWN_URL__");
                width: 10px;
                height: 10px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #78ade0;
                background-color: #b8d4ee;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::down-arrow {
                image: url("__SPIN_DOWN_URL__");
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #78ade0;
                color: #12324f;
                outline: none;
                selection-background-color: #b8d4ee;
                selection-color: #12324f;
            }
            QPushButton#runBtn {
                background-color: #2068b1;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#runBtn:hover {
                background-color: #3c8eda;
            }
            QPushButton#runBtn:disabled {
                background-color: #78ade0;
                color: #d9e8f5;
            }
        """
        self.setStyleSheet(
            style
            .replace("__SPIN_UP_URL__", spin_up_url)
            .replace("__SPIN_DOWN_URL__", spin_down_url)
        )

        scroll = QScrollArea()
        scroll.setObjectName("inputScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("inputContainer")
        container.setMinimumWidth(0)
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Reservoir / IPR ───────────────────────────────────────────────
        ipr_group = QGroupBox("Reservoir  (IPR)")
        ipr_form  = QFormLayout(ipr_group)
        ipr_form.setSpacing(5)
        self._style_form(ipr_form)

        self.ipr_model = QComboBox()
        self.ipr_model.setMinimumWidth(155)
        self.ipr_model.addItems(["Vogel", "Composite IPR", "Standing"])
        self.pr       = self._dbl(500,  15000, 2500, " psia")
        self.pb       = self._dbl(100,  10000, 1800, " psia")
        self.pwf_test = self._dbl(100,   9000, 1200, " psia")
        self.qo_test  = self._dbl(10,   10000,  800, " STB/d")

        ipr_form.addRow("Model",       self.ipr_model)
        ipr_form.addRow("Pr",          self.pr)
        ipr_form.addRow("Pb",          self.pb)
        ipr_form.addRow("Pwf @ test",  self.pwf_test)
        ipr_form.addRow("Qo @ test",   self.qo_test)
        main_layout.addWidget(ipr_group)

        standing_header = QToolButton()
        standing_header.setText("Standing Inputs (optional)")
        standing_header.setCheckable(True)
        standing_header.setChecked(False)
        standing_header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        standing_header.setArrowType(Qt.ArrowType.RightArrow)
        standing_header.setStyleSheet(
            "QToolButton { border: none; text-align: left; color: #2068b1; font-weight: 600; padding: 4px 2px; }"
            "QToolButton:checked { color: #12324f; }"
        )

        standing_content = QWidget()
        standing_content.setVisible(False)
        standing_form = QFormLayout(standing_content)
        standing_form.setSpacing(5)
        self._style_form(standing_form)

        self.fe_old = self._dbl(0.1, 5.0, 1.0, "", decimals=3)
        self.re     = self._dbl(10, 50000, 1000, " ft")
        self.rw     = self._dbl(0.01, 10.0, 0.328, " ft", decimals=3)
        self.skin   = self._dbl(-10.0, 10.0, 0.0, "", decimals=3)

        standing_form.addRow("FE test", self.fe_old)
        standing_form.addRow("Drainage radius", self.re)
        standing_form.addRow("Wellbore radius", self.rw)
        standing_form.addRow("Skin", self.skin)

        standing_container = QWidget()
        standing_container_layout = QVBoxLayout(standing_container)
        standing_container_layout.setContentsMargins(0, 0, 0, 0)
        standing_container_layout.setSpacing(4)
        standing_container_layout.addWidget(standing_header)
        standing_container_layout.addWidget(standing_content)
        main_layout.addWidget(standing_container)

        def _toggle_standing(checked):
            standing_content.setVisible(checked)
            standing_header.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

        standing_header.toggled.connect(_toggle_standing)

        # ── Fluid properties ──────────────────────────────────────────────
        fluid_group = QGroupBox("Fluid Properties")
        fluid_form  = QFormLayout(fluid_group)
        fluid_form.setSpacing(5)
        self._style_form(fluid_form)

        self.pvt_correlation = QComboBox()
        self.pvt_correlation.setMinimumWidth(155)
        self.pvt_correlation.addItems(["Standing", "Kartoatmodjo"])
        self.oil_api  = self._dbl(10,    60,   35,   " °API")
        self.gas_sg   = self._dbl(0.55,   1.1,  0.65, "",     decimals=3)
        self.water_sg = self._dbl(1.0,    1.15, 1.07, "",     decimals=3)
        self.gor      = self._dbl(50,   5000,  500,   " scf/STB")
        self.wor      = self._dbl(0,      20,   0.5,  " STB/STB")

        fluid_form.addRow("PVT Correlation", self.pvt_correlation)
        fluid_form.addRow("Oil API",   self.oil_api)
        fluid_form.addRow("Gas SG",    self.gas_sg)
        fluid_form.addRow("Water SG",  self.water_sg)
        fluid_form.addRow("GOR",       self.gor)
        fluid_form.addRow("WOR",       self.wor)
        main_layout.addWidget(fluid_group)

        # ── Well / Tubing ─────────────────────────────────────────────────
        well_group = QGroupBox("Well & Tubing  (VLP)")
        well_form  = QFormLayout(well_group)
        well_form.setSpacing(5)
        self._style_form(well_form)

        self.vlp_model = QComboBox()
        self.vlp_model.setMinimumWidth(155)
        self.vlp_model.addItems(["Hagedorn-Brown", "Beggs-Brill"])
        self.inclination = self._dbl(-90.0, 90.0, 90.0, " °", decimals=1)
        self.depth      = self._dbl(500,  20000, 6000,  " ft")
        self.tubing_id  = self._dbl(0.5,    6.0, 2.441, " in",   decimals=3)
        self.whp        = self._dbl(0.0, 3000,  150,   " psia",  decimals=3)
        self.t_surf     = self._dbl(50,    250,   100,  " °F",    decimals=1)
        self.t_bh       = self._dbl(100,   400,   200,  " °F",    decimals=1)
        self.roughness  = self._dbl(0,     0.01,  0.0006," in",   decimals=4)

        well_form.addRow("Correlation",  self.vlp_model)
        well_form.addRow("Inclination",  self.inclination)
        well_form.addRow("Depth (TVD)",  self.depth)
        well_form.addRow("Tubing ID",    self.tubing_id)
        well_form.addRow("WHP",          self.whp)
        well_form.addRow("T surface",    self.t_surf)
        well_form.addRow("T bottomhole", self.t_bh)
        well_form.addRow("Roughness",    self.roughness)
        main_layout.addWidget(well_group)

        # ── Sensitivity ───────────────────────────────────────────────────
        sens_group = QGroupBox("Sensitivity (VLP)")
        sens_form  = QFormLayout(sens_group)
        sens_form.setSpacing(5)
        self._style_form(sens_form)

        self.sens_on = QComboBox()
        self.sens_on.setMinimumWidth(155)
        self.sens_on.addItems(["None", "WHP", "GOR", "Tubing ID"])
        self.sens_min   = self._dbl(0, 9999, 100, "")
        self.sens_max   = self._dbl(0, 9999, 400, "")
        self.sens_steps = QSpinBox()
        self.sens_steps.setRange(2, 10)
        self.sens_steps.setValue(3)
        self.sens_steps.setFixedHeight(26)
        self.sens_steps.setMinimumWidth(155)

        sens_form.addRow("Vary",       self.sens_on)
        sens_form.addRow("Min value",  self.sens_min)
        sens_form.addRow("Max value",  self.sens_max)
        sens_form.addRow("Steps",      self.sens_steps)
        main_layout.addWidget(sens_group)

        main_layout.addStretch()

        # ── Run button ────────────────────────────────────────────────────
        self.run_btn = QPushButton("▶  Run Analysis")
        self.run_btn.setFixedHeight(36)
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_requested.emit)
        main_layout.addWidget(self.run_btn)

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Helpers ───────────────────────────────────────────────────────────

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
        sb.setMinimumWidth(155)
        sb.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        return sb

    def _calc_pb(self):
        from pvt.fluid_properties import bubblepoint_pressure
        pb = bubblepoint_pressure(
            self.t_bh.value(), self.gor.value(),
            self.gas_sg.value(), self.oil_api.value(),
            pvt_correlation=self.pvt_correlation.currentText(),
        )
        self.pb.setValue(round(pb, 0))

    def get_values(self):
        return dict(
            ipr_model  = self.ipr_model.currentText(),
            pr         = self.pr.value(),
            pb         = self.pb.value(),
            pwf_test   = self.pwf_test.value(),
            qo_test    = self.qo_test.value(),
            fe_old     = self.fe_old.value(),
            re         = self.re.value(),
            rw         = self.rw.value(),
            skin       = self.skin.value(),
            pvt_correlation = self.pvt_correlation.currentText(),
            oil_api    = self.oil_api.value(),
            gas_sg     = self.gas_sg.value(),
            water_sg   = self.water_sg.value(),
            gor        = self.gor.value(),
            wor        = self.wor.value(),
            vlp_model  = self.vlp_model.currentText(),
            inclination_deg = self.inclination.value(),
            depth      = self.depth.value(),
            tubing_id  = self.tubing_id.value(),
            whp        = self.whp.value(),
            t_surf     = self.t_surf.value(),
            t_bh       = self.t_bh.value(),
            roughness  = self.roughness.value(),
            sens_on    = self.sens_on.currentText(),
            sens_min   = self.sens_min.value(),
            sens_max   = self.sens_max.value(),
            sens_steps = self.sens_steps.value(),
        )
