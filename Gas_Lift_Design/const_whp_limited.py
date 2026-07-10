import numpy as np
from engine.traverse import _resolve_vlp_backend, temperature_at_depth, fluid_properties_at_PT

def compute_gl_traverse_limited(q_o, qg_avail, whp, pinj, inj_gas_sg, valve_dp, well_depth, gor,
                                t_surf, t_bh, wor, gas_sg, oil_api, water_sg, tubing_id,
                                roughness, vlp_model, pvt_correlation, inclination_deg=90.0):
    """
    Computes the gas lift pressure traverse for a limited available gas rate.
    q_o: Liquid rate in STB/d
    qg_avail: Available Gas rate in Mscf/d
    """
    # Calculate Total GLR in the tubing above injection
    qg_avail_scf = qg_avail * 1000.0
    total_glr = gor + (qg_avail_scf / q_o) if q_o > 0 else gor
    
    n_steps = int(max(1, well_depth // 10.0))
    depths = np.linspace(0, well_depth, n_steps + 1)
    dz = depths[1] - depths[0]
    
    p_tubing = float(whp)
    traverse_tubing = [(0.0, p_tubing)]
    traverse_casing = [(0.0, float(pinj))]
    
    pressure_gradient_fn, _ = _resolve_vlp_backend(vlp_model, inclination_deg)
    
    T_avg_R = (t_surf + t_bh) / 2.0 + 460.67
    
    inj_depth = None
    
    for i in range(1, n_steps + 1):
        depth = depths[i]
        T = temperature_at_depth(depth, well_depth, t_surf, t_bh)
        
        # Casing pressure at this depth (Static gas column approximation, Z ≈ 0.9)
        p_cas = pinj * np.exp(0.01877 * inj_gas_sg * depth / (0.9 * T_avg_R))
        traverse_casing.append((depth, p_cas))
        
        if inj_depth is None:
            # Above injection point: Use total GLR (Formation + Lift Gas)
            q_g_total = (q_o * total_glr) / 1000.0
            q_w = q_o * wor / 100.0
            
            try:
                fp = fluid_properties_at_PT(
                    p_tubing, T, q_o, q_w, q_g_total, gas_sg, oil_api, water_sg,
                    tubing_id, total_glr, pvt_correlation=pvt_correlation, T_res=t_bh
                )
                grad = pressure_gradient_fn(fp, roughness)
                grad = max(min(grad, 2.0), 0.01)
            except:
                grad = 0.3
            
            p_tubing += grad * dz
            
            # Check for operating valve intersection (Tubing Pressure >= Casing Pressure - Valve dP)
            if p_tubing >= (p_cas - valve_dp):
                inj_depth = depth
        else:
            # Below injection point: Use only formation GLR
            q_g_form = (q_o * gor) / 1000.0
            q_w = q_o * wor / 100.0
            
            try:
                fp = fluid_properties_at_PT(
                    p_tubing, T, q_o, q_w, q_g_form, gas_sg, oil_api, water_sg,
                    tubing_id, gor, pvt_correlation=pvt_correlation, T_res=t_bh
                )
                grad = pressure_gradient_fn(fp, roughness)
                grad = max(min(grad, 2.0), 0.01)
            except:
                grad = 0.3
                
            p_tubing += grad * dz
            
        traverse_tubing.append((depth, p_tubing))
        
    fbhp = p_tubing
    return fbhp, traverse_tubing, traverse_casing, inj_depth

def generate_gl_vlp_curve_limited(qg_avail, whp, pinj, inj_gas_sg, valve_dp, well_depth, gor,
                                  t_surf, t_bh, wor, gas_sg, oil_api, water_sg, tubing_id,
                                  roughness, vlp_model, pvt_correlation, rate_min=50, rate_max=5000, n_rates=20):
    rates = np.linspace(rate_min, rate_max, n_rates)
    perf_data = []
    
    for q_o in rates:
        fbhp, _, _, inj_depth = compute_gl_traverse_limited(
            q_o, qg_avail, whp, pinj, inj_gas_sg, valve_dp, well_depth, gor,
            t_surf, t_bh, wor, gas_sg, oil_api, water_sg, tubing_id,
            roughness, vlp_model, pvt_correlation
        )
        perf_data.append({
            'q_l': q_o,
            'inj_depth': inj_depth if inj_depth else 0.0,
            'inj_gas_rate': qg_avail,
            'fbhp': fbhp
        })
        
    return perf_data