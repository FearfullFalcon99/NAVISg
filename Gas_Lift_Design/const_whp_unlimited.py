import numpy as np
from engine.traverse import compute_vlp_point, _resolve_vlp_backend, temperature_at_depth
from pvt.fluid_properties import fluid_properties_at_PT

def find_optimum_glr(q_o, whp, well_depth, T_surf, T_bh, wor, form_gor, gas_sg, oil_api, water_sg, tubing_id, roughness, vlp_model, pvt_correlation):
    """
    Step 3: Assume a liquid production rate q and find the optimum total GLR
    belonging to that rate and the tubing size used.
    """
    min_fbhp = float('inf')
    opt_glr = form_gor
    
    # Evaluate total GLR incrementally from formation GOR to find the lowest gradient
    glr_range = np.linspace(form_gor, max(form_gor + 3000, 4000), 20)
    
    for glr in glr_range:
        try:
            fbhp = compute_vlp_point(
                q_o=q_o, whp=whp, well_depth=well_depth, T_surf=T_surf, T_bh=T_bh,
                wor=wor, gor=glr, gas_sg=gas_sg, oil_api=oil_api, water_sg=water_sg,
                tubing_id=tubing_id, roughness=roughness, n_steps=15,
                vlp_model=vlp_model, inclination_deg=90.0, pvt_correlation=pvt_correlation
            )
            if fbhp < min_fbhp:
                min_fbhp = fbhp
                opt_glr = glr
        except Exception:
            continue
            
    return opt_glr, min_fbhp

def compute_gl_traverse_unlimited(q_o, whp, pinj, inj_gas_sg, valve_dp, well_depth, form_gor, T_surf, T_bh, wor, gas_sg, oil_api, water_sg, tubing_id, roughness, vlp_model, pvt_correlation):
    """
    Steps 4-7: Calculate pressure traverse using GLR_opt, find gas injection depth, 
    and calculate traverse below injection using formation GLR.
    """
    opt_glr, _ = find_optimum_glr(
        q_o, whp, well_depth, T_surf, T_bh, wor, form_gor, gas_sg, oil_api,
        water_sg, tubing_id, roughness, vlp_model, pvt_correlation
    )
    
    n_steps = 60
    depths = np.linspace(0, well_depth, n_steps + 1)
    dz = depths[1] - depths[0]
    
    # Step 1: Start from the set WHP
    p_tub = float(whp)
    pressure_gradient_fn, _ = _resolve_vlp_backend(vlp_model, 90.0)
    
    traverse_tubing = []
    traverse_casing = []
    inj_depth = None
    
    for i in range(n_steps + 1):
        d = depths[i]
        
        # Step 2: Calculate the gas pressure distribution in the well's annulus
        p_cas = pinj * np.exp(0.0000347 * inj_gas_sg * d)
        
        traverse_casing.append((d, p_cas))
        traverse_tubing.append((d, p_tub))
        
        if i == n_steps: break
        
        # Step 5: Find the depth of gas injection at the intersection of the tubing curve 
        # and annulus gas pressure minus the valve differential (Δp).
        if inj_depth is None and p_tub >= (p_cas - valve_dp) and i > 0:
            inj_depth = d
            
        # Step 6: Below gas injection, use formation GLR. Above, use optimum total GLR.
        current_glr = form_gor if inj_depth is not None else opt_glr
        
        T = temperature_at_depth(d, well_depth, T_surf, T_bh)
        q_g = q_o * current_glr / 1000.0
        q_w = q_o * wor / 100.0
        
        try:
            fp = fluid_properties_at_PT(p_tub, T, q_o, q_w, q_g, gas_sg, oil_api, water_sg, tubing_id, current_glr, pvt_correlation, T_bh)
            grad = pressure_gradient_fn(fp, roughness)
            grad = max(min(grad, 2.0), 0.01)
        except Exception:
            grad = 0.3
            
        # Step 4: Stepwise integration of the pressure distribution
        p_tub += grad * dz
        
    # Step 7: The final p_tub represents the FBHP at perforation depth
    return p_tub, traverse_tubing, traverse_casing, opt_glr, inj_depth

def generate_gl_vlp_curve(whp, pinj, inj_gas_sg, valve_dp, well_depth, form_gor, T_surf, T_bh, wor, gas_sg, oil_api, water_sg, tubing_id, roughness, vlp_model, pvt_correlation, rate_min=100, rate_max=4000, n_rates=15):
    """
    Step 8: Repeat Steps 4-7 with properly selected liquid rates to create the Tubing Performance Curve.
    Returns detailed tabular data for workflow transparency.
    """
    rates = np.linspace(rate_min, rate_max, n_rates)
    performance_data = []
    
    for q in rates:
        fbhp, _, _, opt_glr, inj_depth = compute_gl_traverse_unlimited(
            q, whp, pinj, inj_gas_sg, valve_dp, well_depth, form_gor, T_surf, T_bh,
            wor, gas_sg, oil_api, water_sg, tubing_id, roughness, vlp_model, pvt_correlation
        )
        
        # Calculate Required Injection Gas Rate (Mscf/d)
        inj_gas_rate = max(0.0, q * (opt_glr - form_gor) / 1000.0)
        
        performance_data.append({
            'q_l': q,
            'opt_glr': opt_glr,
            'inj_depth': inj_depth if inj_depth else well_depth,
            'inj_gas_rate': inj_gas_rate,
            'fbhp': fbhp
        })
        
    return performance_data