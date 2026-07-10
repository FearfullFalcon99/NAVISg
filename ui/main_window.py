import csv
import html
import re
import sys
import time
import numpy as np
import pandas as pd

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QStatusBar, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QStackedWidget, QFrame, QScrollArea,
    QPushButton, QMenu, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from Gas_Lift_Design.const_whp_unlimited import compute_gl_traverse_unlimited, find_optimum_glr, generate_gl_vlp_curve
from ui.input_panel import GeneralInputPanel, GasLiftInputPanel, GasLiftIprVlpInputPanel, _asset_path
from ui.pvt_plots_widget import PVTPlotsWidget
from ui.plot_widget import PlotWidget
from ipr.standing import standing_ipr
from ipr.vogel import vogel_ipr
from ipr.general import general_ipr
from engine.traverse import compute_vlp_curve, find_operating_point, compute_vlp_traverse


class Worker(QObject):
    finished = Signal(dict)
    error = Signal(str)

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
                bubblepoint_pressure, solution_gor, oil_volume_factor,
                live_oil_viscosity, z_factor, gas_volume_factor,
                gas_viscosity, water_density, water_volume_factor, water_viscosity, fluid_properties_at_PT
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
                    Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'],
                    Pb=pb, fe_old=p.get('fe_old', 1.0), fe_new=1.0,
                    r_e=p.get('re'), r_w=p.get('rw'), skin=p.get('skin'),
                )
            elif ipr_model == 'General IPR':
                # Calculate PVT properties at static reservoir pressure
                rs_val = p['gor'] if p['pr'] >= pb else solution_gor(p['pr'], p['t_bh'], p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation'])
                bo_val = oil_volume_factor(p['pr'], p['t_bh'], rs_val, p['gas_sg'], p['oil_api'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'])
                mu_o_val = live_oil_viscosity(p['t_bh'], p['oil_api'], rs_val, p=p['pr'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'], gas_sg=p['gas_sg'])
                
                ipr_p, ipr_q, Qmax, J = general_ipr(
                    Pr=p['pr'], k=p.get('perm_k'), h=p.get('thick_h'), kro=p.get('kro', 1.0), 
                    mu_o=mu_o_val, Bo=bo_val, re=p.get('re'), rw=p.get('rw'), skin=p.get('skin')
                )
            else:
                ipr_p, ipr_q, Qmax, J = vogel_ipr(
                    Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'], Pb=pb,
                )
            
            result['ipr'] = (ipr_q, ipr_p)
            result['Qmax'] = Qmax
            result['J'] = J
            result['pb_used'] = pb
            result['ipr_model'] = ipr_model

            rate_max = min(Qmax * 1.2, 5000)
            base_rates, base_bhps = compute_vlp_curve(
                whp=p['whp'], well_depth=p['depth'], T_surf=p['t_surf'],
                T_bh=p['t_bh'], wor=p['wor'], gor=p['gor'], gas_sg=p['gas_sg'],
                oil_api=p['oil_api'], water_sg=p['water_sg'], tubing_id=p['tubing_id'],
                roughness=p['roughness'], vlp_model=p['vlp_model'],
                inclination_deg=p['inclination_deg'], rate_min=20,
                rate_max=rate_max, n_rates=40, pvt_correlation=p['pvt_correlation']
            )
            result['base_vlp'] = {
                'rates': base_rates, 'bhps': base_bhps,
                'label': f"{p['vlp_model']} VLP (WHP={p['whp']:.0f} psia)"
            }
            result['vlp_model'] = p['vlp_model']
            
            q_op, p_op = find_operating_point(base_rates, base_bhps, ipr_q, ipr_p)
            result['op_point'] = (q_op, p_op)

            traverse_rate = q_op if (q_op is not None and q_op > 0) else p['qo_test']
            traverse_data = compute_vlp_traverse(
                q_o=traverse_rate, 
                whp=p['whp'], 
                well_depth=p['depth'],
                T_surf=p['t_surf'], 
                T_bh=p['t_bh'], 
                wor=p['wor'], 
                gor=p['gor'],
                gas_sg=p['gas_sg'], 
                oil_api=p['oil_api'], 
                water_sg=p['water_sg'],
                tubing_id=p['tubing_id'], 
                roughness=p['roughness'],
                vlp_model=p['vlp_model'], 
                inclination_deg=p['inclination_deg'],
                n_steps = int(p['depth'] // 10),  # 100 ft increments
                pvt_correlation=p['pvt_correlation']
            )
            result['traverse_data'] = traverse_data
            result['traverse_rate'] = traverse_rate

            pvt_p = p_op if (p_op is not None and p_op > 0) else p['pwf_test']
            pvt_T = p['t_bh']
            q_w = traverse_rate * p['wor']
            q_g = traverse_rate * p['gor'] / 1000.0

            fp = fluid_properties_at_PT(
                pvt_p, pvt_T, traverse_rate, q_w, q_g, p['gas_sg'], p['oil_api'],
                p['water_sg'], p['tubing_id'], p['gor'],
                pvt_correlation=p['pvt_correlation'], T_res=p['t_bh']
            )

            oil_sg = 141.5 / (131.5 + p['oil_api'])
            rho_oil = (62.4 * oil_sg + 0.0136 * p['gas_sg'] * fp['Rs']) / fp['Bo']
            mu_oil = live_oil_viscosity(
                pvt_T, p['oil_api'], fp['Rs'], p=pvt_p, pb=pb,
                pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'], gas_sg=p['gas_sg']
            )
            z_val = z_factor(pvt_p, pvt_T, p['gas_sg'])
            bg_val = gas_volume_factor(pvt_p, pvt_T, p['gas_sg'])

            result['pvt_output'] = {
                'pressure': pvt_p, 'temperature': pvt_T, 'Bo': fp['Bo'],
                'Rs': fp['Rs'], 'rho_oil': rho_oil, 'mu_oil': mu_oil,
                'Z': z_val, 'Bg': bg_val,
            }

            p_min = 14.7
            p_max = max(p['pr'], pb, pvt_p) * 1.05
            pressures = np.linspace(p_min, p_max, 120)
            rs_surface = p['gor']

            rs_curve, bo_curve, mu_o_curve, z_curve, bg_curve = [], [], [], [], []
            mu_g_curve, rho_w_curve, bw_curve, mu_w_curve = [], [], [], []

            for pressure in pressures:
                rs_val = rs_surface if pressure >= pb else min(
                    solution_gor(pressure, pvt_T, p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation']),
                    rs_surface,
                )
                bo_val = oil_volume_factor(
                    pressure, pvt_T, rs_val, p['gas_sg'], p['oil_api'],
                    pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=rs_surface
                )
                mu_o_val = live_oil_viscosity(
                    pvt_T, p['oil_api'], rs_val, p=pressure, pb=pb,
                    pvt_correlation=p['pvt_correlation'], Rs_surface=rs_surface, gas_sg=p['gas_sg']
                )
                z_curve.append(z_factor(pressure, pvt_T, p['gas_sg']))
                bg_curve.append(gas_volume_factor(pressure, pvt_T, p['gas_sg']))
                mu_g_curve.append(gas_viscosity(pressure, pvt_T, p['gas_sg']))
                rho_w_curve.append(water_density(pressure, pvt_T, p['water_sg']))
                bw_curve.append(water_volume_factor(pressure, pvt_T, p['water_sg']))
                mu_w_curve.append(water_viscosity(pressure, pvt_T, p['water_sg']))
                rs_curve.append(rs_val)
                bo_curve.append(bo_val)
                mu_o_curve.append(mu_o_val)

            result['pvt_plot_data'] = {
                'pressures': pressures, 'Rs': np.asarray(rs_curve), 'Bo': np.asarray(bo_curve),
                'mu_o': np.asarray(mu_o_curve), 'Z': np.asarray(z_curve), 'Bg': np.asarray(bg_curve),
                'mu_g': np.asarray(mu_g_curve), 'rho_w': np.asarray(rho_w_curve),
                'Bw': np.asarray(bw_curve), 'mu_w': np.asarray(mu_w_curve),
            }

            if p['sens_on'] != 'None':
                n = int(p['sens_steps'])
                values = np.linspace(p['sens_min'], p['sens_max'], n)
                vlp_curves = []

                for v in values:
                    kw = dict(
                        whp=p['whp'], well_depth=p['depth'], T_surf=p['t_surf'],
                        T_bh=p['t_bh'], wor=p['wor'], gor=p['gor'], gas_sg=p['gas_sg'],
                        oil_api=p['oil_api'], water_sg=p['water_sg'], tubing_id=p['tubing_id'],
                        roughness=p['roughness'], vlp_model=p['vlp_model'],
                        inclination_deg=p['inclination_deg'], rate_min=20, rate_max=rate_max,
                        n_rates=40, pvt_correlation=p['pvt_correlation']
                    )
                    if p['sens_on'] == 'WHP':
                        kw['whp'] = v; lbl = f"WHP = {v:.0f} psia"
                    elif p['sens_on'] == 'GLR':
                        kw['gor'] = v; lbl = f"GLR = {v:.0f} scf/STB"
                    elif p['sens_on'] == 'Tubing ID':
                        kw['tubing_id'] = v; lbl = f"ID = {v:.3f} in"

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
            
            
# New Constant WHP Model Worker (Unlimited Gas Injection) ------------------------

class GLAdvancedWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, params):
        super().__init__()
        self.p = params
        
    def run(self):
        try:
            from Gas_Lift_Design.const_whp_unlimited import generate_gl_vlp_curve, compute_gl_traverse_unlimited
            from ipr.vogel import vogel_ipr
            from ipr.standing import standing_ipr
            from ipr.general import general_ipr
            from engine.traverse import find_operating_point
            
            p = self.p
            
            # 1. Step 10: Inflow Performance Curve (Using original IPR group inputs)
            if p.get('ipr_model', 'Vogel') == 'Standing':
                ipr_p, ipr_q, Qmax, J = standing_ipr(
                    Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'], Pb=p['pb'],
                    fe_old=p.get('fe_old', 1.0), fe_new=1.0, r_e=p.get('re', 1000.0), r_w=p.get('rw', 0.328), skin=p.get('skin', 0.0)
                )
            elif p.get('ipr_model', 'Vogel') == 'General IPR':
                from pvt.fluid_properties import bubblepoint_pressure, solution_gor, oil_volume_factor, live_oil_viscosity
                pb_calc = bubblepoint_pressure(p['t_bh'], p['gor'], p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation'])
                pb = p['pb'] if abs(p['pb'] - pb_calc) / pb_calc < 0.5 else pb_calc
                
                rs_val = p['gor'] if p['pr'] >= pb else solution_gor(p['pr'], p['t_bh'], p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation'])
                bo_val = oil_volume_factor(p['pr'], p['t_bh'], rs_val, p['gas_sg'], p['oil_api'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'])
                mu_o_val = live_oil_viscosity(p['t_bh'], p['oil_api'], rs_val, p=p['pr'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'], gas_sg=p['gas_sg'])
                
                ipr_p, ipr_q, Qmax, J = general_ipr(
                    Pr=p['pr'], k=p.get('perm_k'), h=p.get('thick_h'), kro=p.get('kro', 1.0), 
                    mu_o=mu_o_val, Bo=bo_val, re=p.get('re'), rw=p.get('rw'), skin=p.get('skin')
                )
            else:
                ipr_p, ipr_q, Qmax, J = vogel_ipr(Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'], Pb=p['pb'])
                
            # 2. Step 9: Tubing Performance Curve (Using wide range Qmax to intersect IPR)
            rate_max = min(Qmax * 1.2, 8000)
            
            perf_data = generate_gl_vlp_curve(
                p['whp'], p['pinj'], p['inj_gas_sg'], p['valve_dp'], p['depth'], p['gor'],
                p['t_surf'], p['t_bh'], p['wor'], p['gas_sg'], p['oil_api'], p['water_sg'],
                p['tubing_id'], p['roughness'], p['vlp_model'], p['pvt_correlation'],
                rate_min=50, rate_max=rate_max, n_rates=20
            )
            
            vlp_rates = np.array([row['q_l'] for row in perf_data])
            vlp_bhps = np.array([row['fbhp'] for row in perf_data])
            
            # 3. Step 11: Intersection of inflow and outflow
            q_op, p_op = find_operating_point(vlp_rates, vlp_bhps, ipr_q, ipr_p)
            
            # 4. Generate visual traverse specifically for the Operating Point
            if q_op is not None and q_op > 0:
                _, trav_t, trav_c, opt_glr, inj_depth = compute_gl_traverse_unlimited(
                    q_op, p['whp'], p['pinj'], p['inj_gas_sg'], p['valve_dp'], p['depth'], p['gor'],
                    p['t_surf'], p['t_bh'], p['wor'], p['gas_sg'], p['oil_api'], p['water_sg'],
                    p['tubing_id'], p['roughness'], p['vlp_model'], p['pvt_correlation']
                )
            else:
                trav_t, trav_c, opt_glr, inj_depth = [], [], None, None
                
            self.finished.emit({
                'ipr': (ipr_q, ipr_p),
                'vlp': {'rates': vlp_rates, 'bhps': vlp_bhps, 'label': 'GL Tubing Perf. Curve'},
                'op_point': (q_op, p_op),
                'traverse_tubing': trav_t,
                'traverse_casing': trav_c,
                'inj_depth': inj_depth,
                'opt_glr': opt_glr,
                'perf_data': perf_data
            })
            
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")

class GLLimitedWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, params):
        super().__init__()
        self.p = params
        
    def run(self):
        try:
            p = self.p
            
            # Step 10: Inflow Performance Curve
            if p.get('ipr_model', 'Vogel') == 'Standing':
                from ipr.standing import standing_ipr
                ipr_p, ipr_q, Qmax, J = standing_ipr(
                    Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'], Pb=p['pb'],
                    fe_old=p.get('fe_old', 1.0), fe_new=1.0, r_e=p.get('re', 1000.0), r_w=p.get('rw', 0.328), skin=p.get('skin', 0.0)
                )
            elif p.get('ipr_model', 'Vogel') == 'General IPR':
                from ipr.general import general_ipr
                from pvt.fluid_properties import bubblepoint_pressure, solution_gor, oil_volume_factor, live_oil_viscosity
                pb_calc = bubblepoint_pressure(p['t_bh'], p['gor'], p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation'])
                pb = p['pb'] if abs(p['pb'] - pb_calc) / pb_calc < 0.5 else pb_calc
                
                rs_val = p['gor'] if p['pr'] >= pb else solution_gor(p['pr'], p['t_bh'], p['gas_sg'], p['oil_api'], pvt_correlation=p['pvt_correlation'])
                bo_val = oil_volume_factor(p['pr'], p['t_bh'], rs_val, p['gas_sg'], p['oil_api'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'])
                mu_o_val = live_oil_viscosity(p['t_bh'], p['oil_api'], rs_val, p=p['pr'], pb=pb, pvt_correlation=p['pvt_correlation'], Rs_surface=p['gor'], gas_sg=p['gas_sg'])
                
                ipr_p, ipr_q, Qmax, J = general_ipr(
                    Pr=p['pr'], k=p.get('perm_k'), h=p.get('thick_h'), kro=p.get('kro', 1.0), 
                    mu_o=mu_o_val, Bo=bo_val, re=p.get('re'), rw=p.get('rw'), skin=p.get('skin')
                )
            else:
                from ipr.vogel import vogel_ipr
                ipr_p, ipr_q, Qmax, J = vogel_ipr(Pr=p['pr'], Pwf_test=p['pwf_test'], Qo_test=p['qo_test'], Pb=p['pb'])
                
            # Step 9: Tubing Performance Curve (Limited)
            from Gas_Lift_Design.const_whp_limited import generate_gl_vlp_curve_limited, compute_gl_traverse_limited
            from engine.traverse import find_operating_point
            
            rate_max = min(Qmax * 1.2, 8000)
            
            perf_data = generate_gl_vlp_curve_limited(
                p['qg_avail'], p['whp'], p['pinj'], p['inj_gas_sg'], p['valve_dp'], p['depth'], p['gor'],
                p['t_surf'], p['t_bh'], p['wor'], p['gas_sg'], p['oil_api'], p['water_sg'],
                p['tubing_id'], p['roughness'], p['vlp_model'], p['pvt_correlation'],
                rate_min=50, rate_max=rate_max, n_rates=20
            )
            
            vlp_rates = np.array([row['q_l'] for row in perf_data])
            vlp_bhps = np.array([row['fbhp'] for row in perf_data])
            
            # Intersection of inflow and outflow
            q_op, p_op = find_operating_point(vlp_rates, vlp_bhps, ipr_q, ipr_p)
            
            # Generate traverse exclusively for the finalized Operating Point
            if q_op is not None and q_op > 0:
                _, trav_t, trav_c, inj_depth = compute_gl_traverse_limited(
                    q_op, p['qg_avail'], p['whp'], p['pinj'], p['inj_gas_sg'], p['valve_dp'], p['depth'], p['gor'],
                    p['t_surf'], p['t_bh'], p['wor'], p['gas_sg'], p['oil_api'], p['water_sg'],
                    p['tubing_id'], p['roughness'], p['vlp_model'], p['pvt_correlation']
                )
            else:
                trav_t, trav_c, inj_depth = [], [], None
                
            self.finished.emit({
                'ipr': (ipr_q, ipr_p),
                'vlp': {'rates': vlp_rates, 'bhps': vlp_bhps, 'label': f"Limited GL VLP (Qg={p['qg_avail']:.0f} Mscf/d)"},
                'op_point': (q_op, p_op),
                'traverse_tubing': trav_t,
                'traverse_casing': trav_c,
                'inj_depth': inj_depth,
                'perf_data': perf_data
            })
            
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NAVISg — Nodal Analysis and VLP Integrated System (extended with Gas Lift Designing and Optimisation)")
        self.resize(1200, 780) # Slightly streamlined vertical window proportion

        central = QWidget()
        central.setObjectName("appShell")
        self.setCentralWidget(central)
        
        # --- POINT 1: Compact, Elegant Superior Tab Styling ---
        self.setStyleSheet("""
            QTabWidget > QTabBar::tab:top { 
                background: #F0E8E8; 
                border: 1px solid #D4C3C3; 
                padding: 8px 16px; /* Reduced from 12px 25px for compact elegance */
                font-size: 13px;   /* Streamlined from 15px to prevent truncation */
                font-weight: 700; 
                color: #2D1E1E;
                min-width: 0px;    /* Allows text to dictate exact width without clipping */
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabWidget > QTabBar::tab:top:selected { 
                background: #FFFFFF; 
                border-bottom-color: #FFFFFF; 
                color: #8B1E1E; 
            }
            QTabWidget::pane { 
                border: 1px solid #D4C3C3; 
                background: #FFFFFF; 
                top: -1px;
            }
        """)

        # Refined Inferior Style Strategy
        inferior_style = """
            QTabWidget::pane {
                border: 1px solid #D4C3C3;
                background: #FFFFFF;
                top: -1px;
            }
            QTabBar::tab {
                background: #E8D0D0;
                border: 1px solid #D4C3C3;
                border-bottom: 1px solid #D4C3C3;
                padding: 6px 14px; /* Reduced for tighter hierarchy */
                font-size: 12px;
                font-weight: 600;
                color: #4A4A4A;
                margin-right: -1px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                border-bottom-color: #FFFFFF;
                color: #A32B2B;
            }
        """
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.superior_tabs = QTabWidget()
        main_layout.addWidget(self.superior_tabs)

    #----------------------------------------------------------------------------------------------
    #                               TAB 1: General Production Evaluation
    #----------------------------------------------------------------------------------------------
        self.gen_tab = QWidget()
        gen_main_layout = QVBoxLayout(self.gen_tab)
        gen_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the sub-tabs container and apply the existing elegant styling
        self.gen_subtabs = QTabWidget()
        self.gen_subtabs.setStyleSheet(inferior_style) 
        
        # --- Sub-tab a: Current IPR ---
        self.current_ipr_tab = QWidget()
        gen_layout = QHBoxLayout(self.current_ipr_tab)
        gen_layout.setContentsMargins(0,0,0,0)
        
        self.gen_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.gen_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #FAFAFA;
                border: none;
                border-right: 1px solid #D4C3C3;
            }
            QSplitter::handle:horizontal {
                width: 4px;
            }
        """)
        self.gen_splitter.setHandleWidth(4)

        self.gen_input_panel = GeneralInputPanel()
        self.gen_input_panel.setMinimumWidth(400)
        self.gen_input_panel.setMaximumWidth(400) # Limit left-side growth
        
        # Define splitter start sizes 
        self.gen_splitter.setSizes([400, 900])
        # --------------------------------------------------------------------------------------------- 
        self.gen_results_tabs = QTabWidget()  
            
        #-------------------- Sub-tabs for General Evaluation--------------------------------------------------------------------
        self.plot_widget = PlotWidget()
        self.gen_results_tabs.addTab(self.plot_widget, "IPR-VLP")
        
        # Traverse tab-----------------------------------------------------
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
        self.export_traverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B1E1E; border: none; border-radius: 5px; color: #ffffff; font-weight: 700; padding: 5px 14px;
            }
            QPushButton:hover { background-color: #A32B2B; }
            QPushButton:disabled { background-color: #D4C3C3; color: #FAFAFA; }
        """)
        export_menu = QMenu(self.export_traverse_btn)
        export_menu.addAction("Export as CSV", self.export_traverse_csv)
        export_menu.addAction("Export as PDF", self.export_traverse_pdf)
        self.export_traverse_btn.setMenu(export_menu)
        traverse_header_layout.addWidget(self.export_traverse_btn)

        traverse_layout.addLayout(traverse_header_layout)

        self.traverse_table = QTableWidget()
        self.traverse_table.setColumnCount(5)
        self.traverse_table.setHorizontalHeaderLabels(["Measured Depth (ft)", "Pressure (psia)", "Temperature (°F)", "Liquid Holdup", "Flow Regime"])
        self.traverse_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.traverse_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.traverse_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.traverse_table.setAlternatingRowColors(True)
        
        # --- NEW CODE FOR ISSUE 1 ----------------------------------------
        self.traverse_table.setMouseTracking(True)
        self.traverse_table.viewport().setMouseTracking(True)
        self.traverse_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #FAFAFA;
                border: 1px solid #D4C3C3;
            }
            QTableWidget::item:hover {
                background-color: #E8D0D0; /* Elegant soft red hover */
                color: #8B1E1E;
            }
            QTableWidget::item:selected {
                background-color: #8B1E1E; /* Distinct solid red selection */
                color: #FFFFFF;
            }
        """)
        # ------------------------------------------------------------------
        
        traverse_layout.addWidget(self.traverse_table)
        self.gen_results_tabs.addTab(self.traverse_tab, "Traverse Table")

        # PVT Output tab-----------------------------------------------------
        self.pvt_tab = QWidget()
        pvt_layout = QVBoxLayout(self.pvt_tab)
        pvt_scroll = QScrollArea()
        pvt_scroll.setWidgetResizable(True)
        pvt_container = QWidget()
        pvt_main_layout = QVBoxLayout(pvt_container)
        
        self.pvt_info_label = QLabel("<b>Fluid Properties</b> computed at flowing bottomhole pressure (operating point).")
        pvt_main_layout.addWidget(self.pvt_info_label)

        pvt_grid = QGridLayout()
        self.pvt_widgets = {}
        properties = [
            ("pressure", "Operating Pressure", "psia"), ("temperature", "Operating Temperature", "°F"),
            ("Bo", "Oil FVF (Bo)", "bbl/STB"), ("Rs", "Solution GOR (Rs)", "scf/STB"),
            ("rho_oil", "Oil Density", "lb/ft³"), ("mu_oil", "Oil Viscosity", "cP"),
            ("Z", "Z Factor", ""), ("Bg", "Gas FVF (Bg)", "bbl/scf"),
        ]

        for idx, (key, title, unit) in enumerate(properties):
            card, val_lbl = self.create_pvt_card(title, unit)
            self.pvt_widgets[key] = val_lbl
            pvt_grid.addWidget(card, idx // 2, idx % 2)

        pvt_main_layout.addLayout(pvt_grid)
        pvt_main_layout.addStretch()
        pvt_scroll.setWidget(pvt_container)
        pvt_layout.addWidget(pvt_scroll)
        self.gen_results_tabs.addTab(self.pvt_tab, "PVT Output")

        # PVT Plots tab-----------------------------------------------------
        self.pvt_plots_tab = QWidget()
        pvt_plots_layout = QVBoxLayout(self.pvt_plots_tab)
        self.pvt_plots_widget = PVTPlotsWidget()
        pvt_plots_layout.addWidget(self.pvt_plots_widget)
        self.gen_results_tabs.addTab(self.pvt_plots_tab, "PVT Plots")

        # Sensitivity tab---------------------------------------------------
        self.sens_tab = QWidget()
        sens_layout = QVBoxLayout(self.sens_tab)
        self.sens_stack = QStackedWidget()
        self.sens_placeholder = QWidget()
        ph_layout = QVBoxLayout(self.sens_placeholder)
        self.sens_ph_label = QLabel("Sensitivity Analysis Configuration Required")
        ph_layout.addWidget(self.sens_ph_label)
        self.sens_plot_widget = PlotWidget()
        self.sens_stack.addWidget(self.sens_placeholder)
        self.sens_stack.addWidget(self.sens_plot_widget)
        sens_layout.addWidget(self.sens_stack)
        self.gen_results_tabs.addTab(self.sens_tab, "Sensitivity")
        self.gen_results_tabs.setStyleSheet(inferior_style)

        self.gen_splitter.addWidget(self.gen_input_panel)
        self.gen_splitter.addWidget(self.gen_results_tabs)
        self.gen_splitter.setStretchFactor(1, 1)
        gen_layout.addWidget(self.gen_splitter)
        
        # Finalize the Current IPR tab
        self.gen_subtabs.addTab(self.current_ipr_tab, "Current IPR")
        
        # --- Sub-tab b: Future IPR (Placeholder) ---
        self.future_ipr_tab = QWidget()
        future_layout = QVBoxLayout(self.future_ipr_tab)
        future_placeholder = QLabel("Future IPR Calculation Model Configuration Required")
        future_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        future_placeholder.setStyleSheet("color: #8B1E1E; font-size: 14px; font-weight: bold;")
        future_layout.addWidget(future_placeholder)
        self.gen_subtabs.addTab(self.future_ipr_tab, "Future IPR")
        
        # Add the nested tabs to the main General tab layout
        gen_main_layout.addWidget(self.gen_subtabs)
        self.superior_tabs.addTab(self.gen_tab, "General Production Evaluation")
         
        
    # ----------------------------------------------------------------------------------------------------------
    #                                TAB 2: Gas Lift Designing and Optimisation 
    # ----------------------------------------------------------------------------------------------------------
        
        self.gl_tab = QWidget()
        gl_layout = QVBoxLayout(self.gl_tab)
        gl_layout.setContentsMargins(0, 0, 0, 0)
        gl_layout.setSpacing(0) 
        
        # --- POINT 2 & 3: Left-Aligned Header & Synchronized Dropdown Icon ---
        spin_down_url = _asset_path("spin_down.svg")
        
        self.gl_header = QWidget()
        self.gl_header.setStyleSheet(f"""
            QWidget {{ 
                background-color: #FAFAFA; 
                border: none; /* Removed underline/bottom line completely */
            }}
            QLabel {{ 
                font-weight: 700; 
                color: #2D1E1E; 
                font-size: 13px; 
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QComboBox {{
                background-color: #FFFFFF; 
                border: 1px solid #D4C3C3; 
                border-radius: 4px;
                padding: 5px 30px 5px 12px; 
                color: #8B1E1E; 
                font-weight: 700; 
                font-size: 13px;
                min-width: 240px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; 
                subcontrol-position: top right; 
                width: 26px;
                border-left: 1px solid #D4C3C3; 
                background-color: #F0E8E8;
                border-top-right-radius: 3px; 
                border-bottom-right-radius: 3px;
            }}
            QComboBox::drop-down:hover {{ background-color: #D4C3C3; }}
            QComboBox::down-arrow {{ 
                image: url("{spin_down_url}"); 
                width: 10px; 
                height: 10px; 
            }}
            QComboBox:focus {{ border: 1px solid #8B1E1E; }}
        """)
        
        gl_header_layout = QHBoxLayout(self.gl_header)
        gl_header_layout.setContentsMargins(12, 10, 12, 10) # Clean padding around the toolbar
        
        # Placed on the left side before adding the stretch
        gl_header_layout.addWidget(QLabel("Perform:"))
        
        self.gl_action_dropdown = QComboBox()
        self.gl_action_dropdown.addItems([
            "Gas Lift Design at Constant WHP",
            "Gas Lift Design at Variable WHP",
            "GLV Unloading",
            "Design Optimisation"
        ])
        gl_header_layout.addWidget(self.gl_action_dropdown)
        gl_header_layout.addStretch() # Pushes all remaining whitespace to the right
        
        gl_layout.addWidget(self.gl_header)

        # --- Dynamic Content Stack ---
        self.gl_content_stack = QStackedWidget()
        gl_layout.addWidget(self.gl_content_stack)

        splitter_style = """
            QSplitter::handle { background-color: #FAFAFA; border: none; border-right: 1px solid #D4C3C3; }
            QSplitter::handle:horizontal { width: 4px; }
        """

        # ================= STACK INDEX 0: Constant WHP =================
        self.const_whp_tab = QWidget()
        const_whp_layout = QVBoxLayout(self.const_whp_tab)
        const_whp_layout.setContentsMargins(0, 0, 0, 0)
        self.const_whp_subtabs = QTabWidget()
        self.const_whp_subtabs.setStyleSheet(inferior_style)

        # -- Sub-tab a: Unlimited Supply --
        self.cw_unlim_tab = QWidget()
        cw_unlim_layout = QHBoxLayout(self.cw_unlim_tab)
        cw_unlim_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cw_u_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.cw_u_splitter.setStyleSheet(splitter_style)
        
        from ui.input_panel import GasLiftAdvancedInputPanel
        from ui.plot_widget import TraversePlotWidget
        
        self.cw_u_input = GasLiftAdvancedInputPanel()
        self.cw_u_input.setMinimumWidth(400)
        self.cw_u_input.setMaximumWidth(400)
        
        self.cw_u_results_tabs = QTabWidget()
        self.cw_u_results_tabs.setStyleSheet(inferior_style)
        
        # 1. Pressure Traverse Profile Tab (Prioritized First)
        self.cw_u_plot_traverse = TraversePlotWidget()
        self.cw_u_results_tabs.addTab(self.cw_u_plot_traverse, "Pressure Traverse Profile")
        
        # 2. IPR-VLP Output Tab
        self.cw_u_plot_iprvlp = PlotWidget()
        self.cw_u_results_tabs.addTab(self.cw_u_plot_iprvlp, "IPR-VLP Output")
        
        # 3. Gas Lift Performance Table Tab (Transparency Checkpoint)
        self.cw_u_table_tab = QWidget()
        cw_u_table_layout = QVBoxLayout(self.cw_u_table_tab)
        cw_u_table_layout.setContentsMargins(15, 15, 15, 15)
        
        self.cw_u_table = QTableWidget()
        self.cw_u_table.setColumnCount(5)
        self.cw_u_table.setHorizontalHeaderLabels([
            "Liquid Rate (STB/d)", "Optimum GLR (scf/STB)", 
            "Inj. Depth (ft)", "Inj. Gas Rate (Mscf/d)", "FBHP (psia)"
        ])
        self.cw_u_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cw_u_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cw_u_table.setAlternatingRowColors(True)
        self.cw_u_table.setStyleSheet("""
            QTableWidget { background-color: #FFFFFF; alternate-background-color: #FAFAFA; border: 1px solid #D4C3C3; }
            QTableWidget::item:hover { background-color: #E8D0D0; color: #8B1E1E; }
        """)
        cw_u_table_layout.addWidget(self.cw_u_table)
        self.cw_u_results_tabs.addTab(self.cw_u_table_tab, "GL Performance Table")
        
        self.cw_u_splitter.addWidget(self.cw_u_input)
        self.cw_u_splitter.addWidget(self.cw_u_results_tabs)
        self.cw_u_splitter.setCollapsible(0, False)
        self.cw_u_splitter.setSizes([400, 920])
        cw_unlim_layout.addWidget(self.cw_u_splitter)
        
        self.const_whp_subtabs.addTab(self.cw_unlim_tab, "Unlimited Supply")

       # -- Sub-tab b: Limited Supply --
        self.cw_lim_tab = QWidget()
        cw_lim_layout = QHBoxLayout(self.cw_lim_tab)
        cw_lim_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cw_l_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.cw_l_splitter.setStyleSheet(splitter_style)
        
        from ui.input_panel import GasLiftLimitedInputPanel
        
        self.cw_l_input = GasLiftLimitedInputPanel()
        self.cw_l_input.setMinimumWidth(400)
        self.cw_l_input.setMaximumWidth(400)
        
        self.cw_l_results_tabs = QTabWidget()
        self.cw_l_results_tabs.setStyleSheet(inferior_style)
        
        # 1. Pressure Traverse Profile Tab
        self.cw_l_plot_traverse = TraversePlotWidget()
        self.cw_l_results_tabs.addTab(self.cw_l_plot_traverse, "Pressure Traverse Profile")
        
        # 2. IPR-VLP Output Tab
        self.cw_l_plot_iprvlp = PlotWidget()
        self.cw_l_results_tabs.addTab(self.cw_l_plot_iprvlp, "IPR-VLP Output")
        
        # 3. Gas Lift Performance Table Tab (Does not contain Optimum GLR column)
        self.cw_l_table_tab = QWidget()
        cw_l_table_layout = QVBoxLayout(self.cw_l_table_tab)
        cw_l_table_layout.setContentsMargins(15, 15, 15, 15)
        
        self.cw_l_table = QTableWidget()
        self.cw_l_table.setColumnCount(4)
        self.cw_l_table.setHorizontalHeaderLabels([
            "Liquid Rate (STB/d)", "Inj. Depth (ft)", "Available Gas Rate (Mscf/d)", "FBHP (psia)"
        ])
        self.cw_l_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cw_l_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cw_l_table.setAlternatingRowColors(True)
        self.cw_l_table.setStyleSheet("""
            QTableWidget { background-color: #FFFFFF; alternate-background-color: #FAFAFA; border: 1px solid #D4C3C3; }
            QTableWidget::item:hover { background-color: #E8D0D0; color: #8B1E1E; }
        """)
        cw_l_table_layout.addWidget(self.cw_l_table)
        self.cw_l_results_tabs.addTab(self.cw_l_table_tab, "GL Performance Table")
        
        self.cw_l_splitter.addWidget(self.cw_l_input)
        self.cw_l_splitter.addWidget(self.cw_l_results_tabs)
        self.cw_l_splitter.setCollapsible(0, False)
        self.cw_l_splitter.setSizes([400, 920])
        cw_lim_layout.addWidget(self.cw_l_splitter)
        
        self.const_whp_subtabs.addTab(self.cw_lim_tab, "Limited Supply")

        const_whp_layout.addWidget(self.const_whp_subtabs)
        self.gl_content_stack.addWidget(self.const_whp_tab)

        # ================= STACK INDEX 1: Variable WHP =================
        self.var_whp_tab = QWidget()
        var_whp_layout = QVBoxLayout(self.var_whp_tab)
        var_whp_layout.setContentsMargins(0, 0, 0, 0)
        self.var_whp_subtabs = QTabWidget()
        self.var_whp_subtabs.setStyleSheet(inferior_style)
        
        self.vw_unlim_tab = QWidget()
        vw_unlim_layout = QVBoxLayout(self.vw_unlim_tab)
        vw_unlim_layout.addWidget(QLabel("Variable WHP (Unlimited) Configuration Required"))
        self.var_whp_subtabs.addTab(self.vw_unlim_tab, "Unlimited Supply")
        
        self.vw_lim_tab = QWidget()
        vw_lim_layout = QVBoxLayout(self.vw_lim_tab)
        vw_lim_layout.addWidget(QLabel("Variable WHP (Limited) Configuration Required"))
        self.var_whp_subtabs.addTab(self.vw_lim_tab, "Limited Supply")
        
        var_whp_layout.addWidget(self.var_whp_subtabs)
        self.gl_content_stack.addWidget(self.var_whp_tab)

        # ================= STACK INDEX 2: GLV Unloading =================
        self.glv_tab = QWidget()
        glv_layout = QVBoxLayout(self.glv_tab)
        glv_lbl = QLabel("GLV Unloading Environment Configuration Required")
        glv_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glv_lbl.setStyleSheet("color: #8B1E1E; font-size: 14px; font-weight: bold;")
        glv_layout.addWidget(glv_lbl)
        self.gl_content_stack.addWidget(self.glv_tab)

        # ================= STACK INDEX 3: Design Optimisation =================
        self.opt_tab = QWidget()
        opt_layout = QVBoxLayout(self.opt_tab)
        opt_lbl = QLabel("Design Optimisation Environment Configuration Required")
        opt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        opt_lbl.setStyleSheet("color: #8B1E1E; font-size: 14px; font-weight: bold;")
        opt_layout.addWidget(opt_lbl)
        self.gl_content_stack.addWidget(self.opt_tab)

        self.superior_tabs.addTab(self.gl_tab, "Gas Lift Designing and Optimisation")
        
        # Connect Dropdown to Stacked Widget View Switcher
        self.gl_action_dropdown.currentIndexChanged.connect(self.gl_content_stack.setCurrentIndex)
        
        # --- ADD THIS MISSING LINE TO RESTORE FUNCTIONALITY ---
        # Wire hooks for execution for Gas Lift (Constant WHP - unlimited)
        self.cw_u_input.run_requested.connect(self.run_cw_unlimited_analysis)
        # Wire hooks for execution for Gas Lift (Constant WHP - limited)
        self.cw_l_input.run_requested.connect(self.run_cw_limited_analysis)
        # ------------------------------------------------------
        
        # Status Bar Connections---------------------------------------------------------------
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready — fill inputs and click Run Analysis")

        self.gen_input_panel.run_requested.connect(self.run_general_analysis)
        
        self._thread = None
        self._worker = None

    def create_pvt_card(self, title, unit):
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #FFFFFF; border: 1px solid #D4C3C3; border-radius: 6px; }
            QLabel { border: none; background: transparent; } /* Removes oval inheritance */
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #8B1E1E; font-weight: bold; font-size: 13px;") # Font size up
        
        val_lbl = QLabel("-")
        val_lbl.setStyleSheet("color: #2D1E1E; font-size: 18px; font-weight: bold;") # Font size up
        
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet("color: #666666; font-size: 11px;")
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        layout.addWidget(unit_lbl)
        return card, val_lbl

    def _traverse_table_data(self):
        headers = [self.traverse_table.horizontalHeaderItem(col).text() for col in range(self.traverse_table.columnCount())]
        rows = [[self.traverse_table.item(row, col).text() if self.traverse_table.item(row, col) else "" for col in range(self.traverse_table.columnCount())] for row in range(self.traverse_table.rowCount())]
        return headers, rows

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

    def run_general_analysis(self):
        params = self.gen_input_panel.get_values()
        self.status.showMessage("Computing General Analysis… please wait")
        self.gen_input_panel.run_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = Worker(params)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    # New Constant WHP Model (Unlimited Gas Injection) -------------------------------

    def run_cw_unlimited_analysis(self):
        params = self.cw_u_input.get_values()
        self.status.showMessage("Computing Constant WHP Gas Lift Evaluation… please wait")
        self.cw_u_input.run_btn.setEnabled(False)

        self._cw_thread = QThread()
        self._cw_worker = GLAdvancedWorker(params)
        self._cw_worker.moveToThread(self._cw_thread)
        self._cw_thread.started.connect(self._cw_worker.run)
        
        def on_done(res):
            self.cw_u_input.run_btn.setEnabled(True)
            self.cw_u_plot_iprvlp.plot(
                ipr_data=res.get('ipr'),
                vlp_curves=[res.get('vlp')],
                op_point=res.get('op_point')
            )
            self.cw_u_plot_traverse.plot_traverse(
                traverse_tubing=res.get('traverse_tubing'),
                traverse_casing=res.get('traverse_casing'),
                inj_depth=res.get('inj_depth'),
                op_point=res.get('op_point')
            )
            
            # Populate the transparency table
            perf_data = res.get('perf_data', [])
            self.cw_u_table.setRowCount(len(perf_data))
            for i, row in enumerate(perf_data):
                self.cw_u_table.setItem(i, 0, QTableWidgetItem(f"{row['q_l']:.0f}"))
                self.cw_u_table.setItem(i, 1, QTableWidgetItem(f"{row['opt_glr']:.0f}"))
                self.cw_u_table.setItem(i, 2, QTableWidgetItem(f"{row['inj_depth']:.0f}"))
                self.cw_u_table.setItem(i, 3, QTableWidgetItem(f"{row['inj_gas_rate']:.2f}"))
                self.cw_u_table.setItem(i, 4, QTableWidgetItem(f"{row['fbhp']:.1f}"))
                
            q_op, p_op = res.get('op_point', (None, None))
            if q_op:
                self.status.showMessage(
                    f"Gas Lift Op. Point Found: Qo = {q_op:.0f} STB/d  |  Pwf = {p_op:.0f} psia  |  "
                    f"Optimum GLR = {res.get('opt_glr', 0):.0f} scf/STB  |  "
                    f"Injection Depth = {res.get('inj_depth', 0):.0f} ft"
                )
            else:
                self.status.showMessage("Analysis complete: No intersection found.")
                
        def on_err(msg):
            self.cw_u_input.run_btn.setEnabled(True)
            self.status.showMessage(f"Error: {msg}")

        self._cw_worker.finished.connect(on_done)
        self._cw_worker.error.connect(on_err)
        self._cw_worker.finished.connect(self._cw_thread.quit)
        self._cw_worker.error.connect(self._cw_thread.quit)
        self._cw_thread.start()
    # -------------------------------------------------------------------------------
    def run_cw_limited_analysis(self):
        params = self.cw_l_input.get_values()
        self.status.showMessage("Computing Limited Supply Gas Lift Evaluation… please wait")
        self.cw_l_input.run_btn.setEnabled(False)

        self._cw_l_thread = QThread()
        self._cw_l_worker = GLLimitedWorker(params)
        self._cw_l_worker.moveToThread(self._cw_l_thread)
        self._cw_l_thread.started.connect(self._cw_l_worker.run)
        
        def on_done(res):
            self.cw_l_input.run_btn.setEnabled(True)
            self.cw_l_plot_iprvlp.plot(
                ipr_data=res.get('ipr'),
                vlp_curves=[res.get('vlp')],
                op_point=res.get('op_point')
            )
            self.cw_l_plot_traverse.plot_traverse(
                traverse_tubing=res.get('traverse_tubing'),
                traverse_casing=res.get('traverse_casing'),
                inj_depth=res.get('inj_depth'),
                op_point=res.get('op_point')
            )
            
            # Populate the transparency table
            perf_data = res.get('perf_data', [])
            self.cw_l_table.setRowCount(len(perf_data))
            for i, row in enumerate(perf_data):
                self.cw_l_table.setItem(i, 0, QTableWidgetItem(f"{row['q_l']:.0f}"))
                self.cw_l_table.setItem(i, 1, QTableWidgetItem(f"{row['inj_depth']:.0f}"))
                self.cw_l_table.setItem(i, 2, QTableWidgetItem(f"{row['inj_gas_rate']:.2f}"))
                self.cw_l_table.setItem(i, 3, QTableWidgetItem(f"{row['fbhp']:.1f}"))
                
            q_op, p_op = res.get('op_point', (None, None))
            if q_op:
                self.status.showMessage(
                    f"Limited GL Op. Point Found: Qo = {q_op:.0f} STB/d  |  Pwf = {p_op:.0f} psia  |  "
                    f"Inj. Gas = {params['qg_avail']:.0f} Mscf/d  |  "
                    f"Injection Depth = {res.get('inj_depth', 0):.0f} ft"
                )
            else:
                self.status.showMessage("Analysis complete: No intersection found.")
                
        def on_err(msg):
            self.cw_l_input.run_btn.setEnabled(True)
            self.status.showMessage(f"Error: {msg}")

        self._cw_l_worker.finished.connect(on_done)
        self._cw_l_worker.error.connect(on_err)
        self._cw_l_worker.finished.connect(self._cw_l_thread.quit)
        self._cw_l_worker.error.connect(self._cw_l_thread.quit)
        self._cw_l_thread.start()
    
    # --- NEW CODE FOR ISSUE 2 (Executing the run and handling data sync) -------------------------------
    def run_gaslift_iprvlp_analysis(self):
        # 1. Sync values automatically if 'Carry forward' is selected
        if self.gl_new_iprvlp_input.btn_carry.isChecked():
            gen_vals = self.gen_input_panel.get_values()
            gl_vals = self.gl_input_panel.get_values()
            
            # Push general values across
            self.gl_new_iprvlp_input.set_values(gen_vals)
            # Push new Target GLR & Inj. Depth
            self.gl_new_iprvlp_input.gor.setValue(gl_vals['target_glr'])
            self.gl_new_iprvlp_input.depth.setValue(gl_vals['inj_depth'])

        # 2. Run analysis using standard Nodal Analysis Worker
        params = self.gl_new_iprvlp_input.get_values()
        self.status.showMessage("Computing New Gas Lift IPR-VLP… please wait")
        self.gl_new_iprvlp_input.run_btn.setEnabled(False)

        self._gl_thread = QThread()
        self._gl_worker = Worker(params)
        self._gl_worker.moveToThread(self._gl_thread)
        self._gl_thread.started.connect(self._gl_worker.run)
        
        # Using a dedicated local callback for rendering the secondary plot
        def on_gl_iprvlp_done(result):
            self.gl_new_iprvlp_input.run_btn.setEnabled(True)
            self.gl_new_iprvlp_plot.plot(
                ipr_data=result.get('ipr'),
                vlp_curves=[result.get('base_vlp')] if result.get('base_vlp') else None,
                op_point=result.get('op_point'),
            )
            q_op, p_op = result.get('op_point', (None, None))
            if q_op:
                self.status.showMessage(f"Gas Lift Op. Point Found: Qo = {q_op:.0f} STB/d  |  Pwf = {p_op:.0f} psia")
            else:
                self.status.showMessage("Analysis complete: No intersection found.")

        def on_gl_iprvlp_error(msg):
            self.gl_new_iprvlp_input.run_btn.setEnabled(True)
            self.status.showMessage(f"Error: {msg}")

        self._gl_worker.finished.connect(on_gl_iprvlp_done)
        self._gl_worker.error.connect(on_gl_iprvlp_error)
        self._gl_worker.finished.connect(self._gl_thread.quit)
        self._gl_worker.error.connect(self._gl_thread.quit)
        self._gl_thread.start()
    
    # -------------------------------------------------------------------------------
        
    def _on_done(self, result):
        self.gen_input_panel.run_btn.setEnabled(True)
        self.plot_widget.plot(
            ipr_data=result.get('ipr'),
            vlp_curves=[result.get('base_vlp')] if result.get('base_vlp') else None,
            op_point=result.get('op_point'),
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
            self.traverse_table.setItem(row_idx, 4, QTableWidgetItem(str(regime).replace('_', ' ')))
        self.export_traverse_btn.setEnabled(len(traverse_data) > 0)

        pvt_data = result.get('pvt_output', {})
        if pvt_data:
            self.pvt_info_label.setText(
                f"<b>Fluid Properties</b> calculated at flowing bottomhole pressure: <b>{pvt_data['pressure']:.1f} psia</b> and bottomhole temperature: <b>{pvt_data['temperature']:.1f} °F</b>"
            )
            self.pvt_widgets['pressure'].setText(f"{pvt_data['pressure']:.1f}")
            self.pvt_widgets['temperature'].setText(f"{pvt_data['temperature']:.1f}")
            self.pvt_widgets['Bo'].setText(f"{pvt_data['Bo']:.3f}")
            self.pvt_widgets['Rs'].setText(f"{pvt_data['Rs']:.1f}")
            self.pvt_widgets['rho_oil'].setText(f"{pvt_data['rho_oil']:.2f}")
            self.pvt_widgets['mu_oil'].setText(f"{pvt_data['mu_oil']:.2f}")
            self.pvt_widgets['Z'].setText(f"{pvt_data['Z']:.3f}")
            self.pvt_widgets['Bg'].setText(f"{pvt_data['Bg']:.4f}")
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
        J = result.get('J', 0)
        pb   = result.get('pb_used', 0)
        
        if q_op:
            eff = q_op / Qmax * 100 if Qmax > 0 else 0
            self.status.showMessage(
                f"Qo = {q_op:.0f} STB/d  |  Pwf = {p_op:.0f} psia  |  "
                f"AOF = {Qmax:.0f} STB/d  |  PI = {J:.3f} STB/d/psi  |  "
                f"Pb = {pb:.0f} psia "
            )
        else:
            self.status.showMessage(
                f"AOF = {Qmax:.0f} STB/d  |  PI = {J:.3f} STB/d/psi  |  Pb = {pb:.0f} psia"
            )

    def _on_error(self, msg):
        self.gen_input_panel.run_btn.setEnabled(True)
        self.status.showMessage(f"Error: {msg}")