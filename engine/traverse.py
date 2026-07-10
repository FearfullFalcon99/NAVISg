import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pvt.fluid_properties import fluid_properties_at_PT
from correlations.hagedorn_brown import pressure_gradient as hb_pressure_gradient
from correlations.hagedorn_brown import _blended_holdup
from correlations.BeggsandBrill import pressure_gradient as bb_pressure_gradient
from correlations.BeggsandBrill import holdup_and_regime as bb_holdup_and_regime


def _resolve_vlp_backend(vlp_model, inclination_deg=90.0):
    # 1. Beggs-Brill
    if vlp_model == 'Beggs-Brill':
        from correlations.BeggsandBrill import pressure_gradient as bb_pressure_gradient
        from correlations.BeggsandBrill import holdup_and_regime as bb_holdup_and_regime
        return (
            lambda fp, roughness: bb_pressure_gradient(fp, roughness, inclination_deg=inclination_deg),
            lambda fp: bb_holdup_and_regime(fp, inclination_deg=inclination_deg),
        )

    # 2. Duns-Ros Integration
    elif vlp_model == 'Duns-Ros':
        import importlib
        DR = importlib.import_module("correlations.Duns-Ros")
        
        def dr_grad(fp, roughness):
            dr_fp = fp.copy()
            dr_fp.update({'sigma_l': fp['sigma'], 'Vsl': fp['v_sl'], 'Vsg': fp['v_sg'], 'Vm': fp['v_m']})
            
            dr = DR.DunsRos(
                tubing_id=fp['d_in']/12.0, tubing_od=(fp['d_in']/12.0)+0.1, casing_id=(fp['d_in']/12.0)+0.2,
                roughness=roughness/12.0, pvt_model=None, fluid_properties=dr_fp, 
                watercut=fp.get('f_w', 0.0)*100, theta=90.0-inclination_deg
            )
            dr._superficial_velocities = lambda: None  # Bypass velocity overwrite
            return dr.calculate_gradient(fp['p'])

        def dr_holdup(fp):
            dr_fp = fp.copy()
            dr_fp.update({'sigma_l': fp['sigma'], 'Vsl': fp['v_sl'], 'Vsg': fp['v_sg'], 'Vm': fp['v_m']})
            
            dr = DR.DunsRos(
                tubing_id=fp['d_in']/12.0, tubing_od=(fp['d_in']/12.0)+0.1, casing_id=(fp['d_in']/12.0)+0.2,
                roughness=0.0006/12.0, pvt_model=None, fluid_properties=dr_fp, 
                watercut=fp.get('f_w', 0.0)*100, theta=90.0-inclination_deg
            )
            dr._superficial_velocities = lambda: None 
            _, hl, _, _, _ = dr.calculate_gradient(fp['p'], return_components=True)
            return hl, "Duns-Ros Flow"

        return dr_grad, dr_holdup

    # 3. Default fallback (Hagedorn-Brown)
    from correlations.hagedorn_brown import pressure_gradient as hb_pressure_gradient
    from correlations.hagedorn_brown import _blended_holdup
    return hb_pressure_gradient, _blended_holdup
#-----------------------------------------------------------------------------------        
    
def temperature_at_depth(depth, total_depth, T_surf, T_bh):
    if total_depth <= 0:
        return T_surf
    return T_surf + (T_bh - T_surf) * (depth / total_depth)


def compute_vlp_point(q_o, whp, well_depth, T_surf, T_bh,
                      wor, gor, gas_sg, oil_api, water_sg,
                      tubing_id, roughness=0.0006, n_steps=None,
                      vlp_model='Hagedorn-Brown', inclination_deg=90.0,
                      pvt_correlation='Standing'):
    """
    March from surface (WHP) downward to BH.
    Returns BHP [psia].

    FIX 2: q_w now scales with q_o via wor parameter.
    Previously q_w was fixed at qo_test * wor regardless of actual rate.
    """
    Rs_surface = gor                     # scf/STB
    q_g        = q_o * gor / 1000.0     # Mscf/d
    q_w        = q_o * wor / 100.00      # STB/d  — scales with rate

    n_steps = n_steps or max(1, int(well_depth // 10.00))  # Default: 1 step per 10 ft
    depths = np.linspace(0, well_depth, n_steps + 1)
    dz     = depths[1] - depths[0]
    p      = float(whp)

    pressure_gradient_fn, _ = _resolve_vlp_backend(vlp_model, inclination_deg)

    for i in range(n_steps):
        T = temperature_at_depth(depths[i], well_depth, T_surf, T_bh)
        try:
            fp   = fluid_properties_at_PT(
                p, T, q_o, q_w, q_g,
                gas_sg, oil_api, water_sg,
                tubing_id, Rs_surface,
                pvt_correlation=pvt_correlation,
                T_res=T_bh
            )
            grad = pressure_gradient_fn(fp, roughness)
            grad = max(min(grad, 2.0), 0.01)
        except Exception as e:
            print(f"ERROR at step {i}/{n_steps}, q_o = {q_o:.2f} STB/d: {e}")
            raise
        p += grad * dz

    return float(p)


def compute_vlp_curve(whp, well_depth, T_surf, T_bh,
                      wor, gor, gas_sg, oil_api, water_sg,
                      tubing_id, roughness=0.0006,
                      rate_min=50, rate_max=5000,
                      n_rates=30, n_steps=None,
                      vlp_model='Hagedorn-Brown', inclination_deg=90.0,
                      pvt_correlation='Standing'):
    """Build full VLP curve: arrays of (rates [STB/d], BHPs [psia])."""
    n_steps = n_steps or max(1, int(well_depth // 10.00))  # Default: 1 step per 10 ft
    rates = np.linspace(rate_min, rate_max, n_rates)
    bhps  = []
    for q in rates:
        bhp = compute_vlp_point(
            q, whp, well_depth, T_surf, T_bh,
            wor, gor, gas_sg, oil_api, water_sg,
            tubing_id, roughness, n_steps,
            vlp_model=vlp_model,
            inclination_deg=inclination_deg,
            pvt_correlation=pvt_correlation
        )
        bhps.append(bhp)
    return rates, np.array(bhps)


def find_operating_point(vlp_rates, vlp_bhps, ipr_rates, ipr_pwfs):
    """
    Find intersection of VLP and IPR curves.
    Returns the highest-rate intersection (main operating point).
    """
    from scipy.interpolate import interp1d
    from scipy.optimize import brentq

    try:
        vlp_fn = interp1d(vlp_rates, vlp_bhps, kind='linear',
                          bounds_error=False, fill_value='extrapolate')
        ipr_fn = interp1d(ipr_rates, ipr_pwfs,  kind='linear',
                          bounds_error=False, fill_value='extrapolate')

        q_lo   = max(vlp_rates.min(), ipr_rates.min())
        q_hi   = min(vlp_rates.max(), ipr_rates.max())
        q_scan = np.linspace(q_lo, q_hi, 1000)
        diff   = vlp_fn(q_scan) - ipr_fn(q_scan)

        sign_changes = np.where(np.diff(np.sign(diff)))[0]
        if len(sign_changes) == 0:
            return None, None

        roots = []
        for idx in sign_changes:
            try:
                q_root = brentq(
                    lambda q: vlp_fn(q) - ipr_fn(q),
                    q_scan[idx], q_scan[idx + 1]
                )
                roots.append((float(q_root), float(vlp_fn(q_root))))
            except Exception:
                pass

        if not roots:
            return None, None

        # Highest-rate intersection = main operating point
        return max(roots, key=lambda x: x[0])

    except Exception:
        return None, None


def compute_vlp_traverse(q_o, whp, well_depth, T_surf, T_bh,
                         wor, gor, gas_sg, oil_api, water_sg,
                         tubing_id, roughness=0.0006, n_steps=None,
                         vlp_model='Hagedorn-Brown', inclination_deg=90.0,
                         pvt_correlation='Standing'):
    """
    March from surface (WHP) downward to BH, recording depth, P, T, holdup, and flow regime.
    Returns a list of dicts containing 'depth', 'pressure', 'temperature', 'holdup', and 'regime'.
    """
    if n_steps is None:
        n_steps = max(1, int(well_depth // 10.00))  # Default: 1 step per 10 ft

    Rs_surface = gor                     # scf/STB
    q_g        = q_o * gor / 1000.0     # Mscf/d
    q_w        = q_o * wor / 100.00      # STB/d

    depths = np.linspace(0, well_depth, n_steps + 1)
    dz     = depths[1] - depths[0]
    p      = float(whp)

    traverse_data = []
    pressure_gradient_fn, holdup_regime_fn = _resolve_vlp_backend(vlp_model, inclination_deg)

    for i in range(n_steps + 1):
        depth = depths[i]
        T = temperature_at_depth(depth, well_depth, T_surf, T_bh)
        try:
            fp   = fluid_properties_at_PT(
                p, T, q_o, q_w, q_g,
                gas_sg, oil_api, water_sg,
                tubing_id, Rs_surface,
                pvt_correlation=pvt_correlation,
                T_res=T_bh
            )
            el, regime = holdup_regime_fn(fp)
        except Exception:
            el = 1.0
            regime = 'unknown'

        traverse_data.append({
            'depth': float(depth),
            'pressure': float(p),
            'temperature': float(T),
            'holdup': float(el),
            'regime': str(regime),
        })

        if i < n_steps:
            try:
                fp   = fluid_properties_at_PT(
                    p, T, q_o, q_w, q_g,
                    gas_sg, oil_api, water_sg,
                    tubing_id, Rs_surface,
                    pvt_correlation=pvt_correlation,
                    T_res=T_bh
                )
                grad = pressure_gradient_fn(fp, roughness)
                grad = max(min(grad, 2.0), 0.01)
            except Exception:
                grad = 0.3
            p += grad * dz

    return traverse_data
