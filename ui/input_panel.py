# new ui/input_panel.py----------------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QAbstractSpinBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QScrollArea, QFrame, QToolButton, QHBoxLayout, QRadioButton
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path
import sys

def _asset_path(filename: str) -> str:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return (base_dir / "assets" / filename).resolve().as_posix().replace("\\", "/")

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
        self.ipr_model.addItems(["Vogel", "Composite IPR", "Standing", "General IPR", "Wiggins"])
        
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
        
        # --- Add rows to the form ---
        self.ipr_form.addRow("Model", self.ipr_model)
        self.ipr_form.addRow("Avg. Reservoir Pressure", self.pr)
        
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
            "kro": self.kro
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
        
        main_layout.addWidget(ipr_group)
        
        # Connect the dropdown to the dynamic toggle logic
        self.ipr_model.currentTextChanged.connect(self._toggle_ipr_fields)
        self._toggle_ipr_fields() # Trigger immediately to set initial state
        #-----------------------------------------------------------------------------------------------

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
    def _toggle_ipr_fields(self):
        """Dynamically shows/hides QFormLayout rows based on the selected IPR Model."""
        model = self.ipr_model.currentText()
        
        # Map out which fields are required for which model
        fields_map = {
            "Vogel": ["pb", "pwf_test", "qo_test"],
            "Composite IPR": ["pb", "pwf_test", "qo_test"],
            "Standing": ["pb", "pwf_test", "qo_test", "fe_old", "re", "rw", "skin"],
            "General IPR": ["perm_k", "thick_h", "re", "rw", "skin", "kro"],
            "Wiggins": ["pb", "pwf_test", "qo_test"]
        }
        
        active_fields = fields_map.get(model, [])
        
        # Iterate through the dictionary and toggle visibility for both the widget and its label
        for name, widget in self.dynamic_ipr_widgets.items():
            is_visible = name in active_fields
            widget.setVisible(is_visible)
            
            label = self.ipr_form.labelForField(widget)
            if label:
                label.setVisible(is_visible)
    # -------------------------------------------------------------------------------
    
    def get_values(self):
        return {
            "ipr_model": self.ipr_model.currentText(), 
            "pr": self.pr.value(), "pb": self.pb.value(),
            "pwf_test": self.pwf_test.value(), 
            "qo_test": self.qo_test.value(),
            # -------------------------------------------------------------------------------
            "fe_old": self.fe_old.value(),
            "re": self.re.value(),
            "rw": self.rw.value(),
            "skin": self.skin.value(),
            "perm_k": self.perm_k.value(),
            "thick_h": self.thick_h.value(),
            "kro": self.kro.value(),
            # -------------------------------------------------------------------------------
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
            "sens_steps": self.sens_steps.value()
        }
        
    # Add this method to GeneralInputPanel-----------------------------------------------------
    def set_values(self, vals):
        if "ipr_model" in vals: self.ipr_model.setCurrentText(vals["ipr_model"])
        if "pr" in vals: self.pr.setValue(vals["pr"])
        if "pb" in vals: self.pb.setValue(vals["pb"])
        if "pwf_test" in vals: self.pwf_test.setValue(vals["pwf_test"])
        if "qo_test" in vals: self.qo_test.setValue(vals["qo_test"])
        # -------------------------------------------------------------------------------
        if "fe_old" in vals: self.fe_old.setValue(vals["fe_old"])
        if "re" in vals: self.re.setValue(vals["re"])
        if "rw" in vals: self.rw.setValue(vals["rw"])
        if "skin" in vals: self.skin.setValue(vals["skin"])
        if "perm_k" in vals: self.perm_k.setValue(vals["perm_k"])
        if "thick_h" in vals: self.thick_h.setValue(vals["thick_h"])
        if "kro" in vals: self.kro.setValue(vals["kro"])
        # -------------------------------------------------------------------------------
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
    # Custom signal to sync primary inputs
    pull_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("futureIPRInputPanel")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        
        self.btn_carry_forward = QPushButton("⟳ Carry Forward Current IPR")
        self.btn_carry_forward.setToolTip("Pull current reservoir conditions from the General Evaluation tab.")
        self.btn_carry_forward.setStyleSheet("""
            QPushButton {
                background-color: #F0E8E8; color: #8B1E1E; font-size: 13px; font-weight: bold;
                padding: 8px; border: 1px solid #D4C3C3; border-radius: 6px; margin-bottom: 8px;
            }
            QPushButton:hover { background-color: #E8D0D0; }
            QPushButton:pressed { background-color: #D4C3C3; }
        """)
        self.btn_carry_forward.clicked.connect(self.pull_requested.emit)
        main_layout.addWidget(self.btn_carry_forward)
        
        curr_group = QGroupBox("Current Reservoir Parameters")
        curr_form = QFormLayout(curr_group)
        self._style_form(curr_form)
        self.pr_p = self._dbl(500, 15000, 2500, " psia")
        self.pb = self._dbl(100, 10000, 1800, " psia")
        self.pwf_test = self._dbl(100, 9000, 1200, " psia")
        self.qo_test = self._dbl(10, 10000, 800, " STB/d")
        curr_form.addRow("Current Avg. Pressure (Pr)", self.pr_p)
        curr_form.addRow("Bubble Point (Pb)", self.pb)
        curr_form.addRow("Test FBHP (Pwf)", self.pwf_test)
        curr_form.addRow("Test Rate (Qo)", self.qo_test)
        main_layout.addWidget(curr_group)
        
        fut_group = QGroupBox("Future Evaluation Parameters")
        self.fut_form = QFormLayout(fut_group)  # Make it an instance attribute
        self._style_form(self.fut_form)
        
        self.ipr_model = self._disable_scroll(QComboBox())
        self.ipr_model.addItems(["Vogel", "Wiggins"])
        
        self.pr_f = self._dbl(100, 15000, 1500, " psia")
        self.method = self._disable_scroll(QComboBox())
        self.method.addItems(["First Approximation", "Second Approximation"])
        
        # Use self.fut_form to add rows
        self.fut_form.addRow("IPR Model", self.ipr_model)
        self.fut_form.addRow("Approximation Method", self.method)
        self.fut_form.addRow("Future Avg. Pressure (Pr_f)", self.pr_f)
        main_layout.addWidget(fut_group)
        
        # Connect dynamic toggle
        self.ipr_model.currentTextChanged.connect(self._toggle_future_fields)
        self._toggle_future_fields() # Set initial state
        
        main_layout.addStretch()
        
        self.run_btn = QPushButton("▶ Evaluate Future IPR")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_requested.emit)
        main_layout.addWidget(self.run_btn)
        
        scroll.setWidget(container)
        QVBoxLayout(self).addWidget(scroll)
        
    def _toggle_future_fields(self):
        is_vogel = self.ipr_model.currentText() == "Vogel"
        self.method.setVisible(is_vogel)
        
        # Safely extract the label directly from the form layout
        label = self.fut_form.labelForField(self.method)
        
        if label:
            label.setVisible(is_vogel)

    def get_values(self):
        return {
            "ipr_model": self.ipr_model.currentText(),
            "pr_p": self.pr_p.value(), 
            "pb": self.pb.value(),
            "pwf_test": self.pwf_test.value(), 
            "qo_test": self.qo_test.value(),
            "pr_f": self.pr_f.value(), 
            "method": 1 if self.method.currentText() == "First Approximation" else 2
        }
        
    def set_values(self, vals):
        if "pr_p" in vals: self.pr_p.setValue(vals["pr_p"])
        if "pb" in vals: self.pb.setValue(vals["pb"])
        if "pwf_test" in vals: self.pwf_test.setValue(vals["pwf_test"])
        if "qo_test" in vals: self.qo_test.setValue(vals["qo_test"])