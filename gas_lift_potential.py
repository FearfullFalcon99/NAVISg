def calculate_required_gas_lift_rate(q_l, GLR1, GLR2):
    """
    Calculates the required gas injection rate (q_g).
    Equation (11-3): q_g = q_l * (GLR2 - GLR1)
    """
    q_g = q_l * (GLR2 - GLR1)
    return max(q_g, 0.0)

def calculate_constant_flowing_gradient(p_tf, p_wf, H):
    """
    Calculates the average pressure gradient (dp/dz).
    Derived from Equation (11-2): p_tf + (dp/dz)H = p_wf
    """
    if H == 0:
        return 0.0
    return (p_wf - p_tf) / H

def evaluate_gas_lift_design(target_q, target_pwf, base_glr, target_glr, depth, whp):
    req_gradient = calculate_constant_flowing_gradient(whp, target_pwf, depth)
    required_qg = calculate_required_gas_lift_rate(target_q, base_glr, target_glr)
    
    return {
        "Target_Rate_STBd": target_q,
        "Required_BHP_psia": target_pwf,
        "Required_Gradient_psift": req_gradient,
        "Required_GLR2_SCFSTB": target_glr,
        "Injection_Rate_SCFd": required_qg,
    }