import numpy as np

def wiggins_ipr(Pr, Pwf_test, Qo_test, wc_pct=0.0):
    """
    Computes the current Total Liquid IPR curve using Wiggins' Method.
    Assumes the reservoir initially exists at its bubble-point pressure.
    """
    if Pr <= 0:
        return np.array([]), np.array([]), 0.0, 0.0
        
    ratio = Pwf_test / Pr
    
    # 1. Evaluate Oil Components (Equation 7-14)
    denom_o = 1.0 - 0.52 * ratio - 0.48 * (ratio ** 2)
    Qomax = Qo_test / denom_o if denom_o > 0 else 0.0
    
    # 2. Evaluate Water Components (Equation 7-15)
    # Safely calculate Qw_test from Qo_test and Water Cut %
    wc_frac = max(0.0, min(wc_pct / 100.0, 0.9999)) # Prevent division by zero
    Qw_test = Qo_test * (wc_frac / (1.0 - wc_frac)) if wc_frac > 0 else 0.0
    
    denom_w = 1.0 - 0.72 * ratio - 0.28 * (ratio ** 2)
    Qwmax = Qw_test / denom_w if denom_w > 0 else 0.0
    
    # 3. Generate combined Liquid IPR array
    ipr_p = np.linspace(Pr, 0, 50)
    pr_ratio = ipr_p / Pr
    
    ipr_q_o = Qomax * (1.0 - 0.52 * pr_ratio - 0.48 * (pr_ratio ** 2))
    ipr_q_w = Qwmax * (1.0 - 0.72 * pr_ratio - 0.28 * (pr_ratio ** 2))
    
    ipr_q_l = ipr_q_o + ipr_q_w
    Q_Lmax = Qomax + Qwmax
    
    # Productivity Index (J) liquid approximation
    J_L = (1.48 * Q_Lmax) / Pr if Pr > 0 else 0.0
    
    return ipr_p, ipr_q_l, Q_Lmax, J_L


def wiggins_future_ipr(Pr_p, Pwf_test, Qo_test, wc_pct, Pr_f):
    """
    Computes the future Total Liquid IPR curve using Wiggins' Future Maximum Rate correlations.
    """
    if Pr_p <= 0 or Pr_f <= 0:
        return np.array([]), np.array([]), 0.0, 0.0
        
    ratio_test = Pwf_test / Pr_p
    
    # 1. Current Max Rates
    denom_o = 1.0 - 0.52 * ratio_test - 0.48 * (ratio_test ** 2)
    Qomax_p = Qo_test / denom_o if denom_o > 0 else 0.0
    
    wc_frac = max(0.0, min(wc_pct / 100.0, 0.9999))
    Qw_test = Qo_test * (wc_frac / (1.0 - wc_frac)) if wc_frac > 0 else 0.0
    
    denom_w = 1.0 - 0.72 * ratio_test - 0.28 * (ratio_test ** 2)
    Qwmax_p = Qw_test / denom_w if denom_w > 0 else 0.0
    
    # 2. Future Max Rates (Equations 7-16 and 7-17)
    pr_ratio_future = Pr_f / Pr_p
    Qomax_f = Qomax_p * (0.15 * pr_ratio_future + 0.84 * (pr_ratio_future ** 2))
    Qwmax_f = Qwmax_p * (0.59 * pr_ratio_future + 0.36 * (pr_ratio_future ** 2))
    
    # 3. Generate future combined Liquid IPR array
    ipr_p_f = np.linspace(Pr_f, 0, 50)
    pr_ratio_f = ipr_p_f / Pr_f
    
    ipr_q_o_f = Qomax_f * (1.0 - 0.52 * pr_ratio_f - 0.48 * (pr_ratio_f ** 2))
    ipr_q_w_f = Qwmax_f * (1.0 - 0.72 * pr_ratio_f - 0.28 * (pr_ratio_f ** 2))
    
    ipr_q_l_f = ipr_q_o_f + ipr_q_w_f
    Q_Lmax_f = Qomax_f + Qwmax_f
    
    J_L_f = (1.48 * Q_Lmax_f) / Pr_f if Pr_f > 0 else 0.0
    
    return ipr_p_f, ipr_q_l_f, Q_Lmax_f, J_L_f