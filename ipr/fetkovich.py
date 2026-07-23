import numpy as np

def fetkovich_ipr(Pr, Pwf_test, Qo_test, Pb, C=None, n=None):
    """
    Evaluates Fetkovich IPR considering Cases 1, 2, and 3 depending on pressure inputs.
    """
    if Pr <= Pb:
        # Case 2: Saturated Region
        if C is None or n is None:
            C = 0.001
            n = 1.0
            
        Qmax = C * (Pr**2)**n
        J = 2 * C * Pr * n  
        
        p_arr = np.linspace(0, Pr, 50)
        q_arr = C * (Pr**2 - p_arr**2)**n
        
        return p_arr, q_arr, Qmax, J

    else:
        # Undersaturated Region
        if Pwf_test >= Pb:
            # Case 1: Pr > Pb and Pwf > Pb
            J = Qo_test / (Pr - Pwf_test)
        else:
            # Case 3: Pr > Pb and Pwf < Pb
            J = Qo_test / ((Pr - Pb) + (1 / (2 * Pb)) * (Pb**2 - Pwf_test**2))
            
        Qmax = J * ((Pr - Pb) + (Pb / 2))
        
        p_arr = np.linspace(0, Pr, 50)
        q_arr = np.zeros_like(p_arr)
        
        for i, p in enumerate(p_arr):
            if p >= Pb:
                q_arr[i] = J * (Pr - p)
            else:
                q_arr[i] = J * ((Pr - Pb) + (1 / (2 * Pb)) * (Pb**2 - p**2))
                
        return p_arr, q_arr, Qmax, J


def _klins_clark(Pr, Pb):
    """Calculates dimensionless ratios based on the Klins and Clark empirical correlations."""
    x = 1.0 - (Pr / Pb)
    n_ratio = 1.0 + 0.0577*x - 0.2459*(x**2) + 0.503*(x**3)
    c_ratio = 1.0 - 3.5718*x + 4.7981*(x**2) - 2.3066*(x**3)
    return n_ratio, c_ratio


def fetkovich_future_ipr(Pr_p, Pwf_test, Qo_test, Pb, Pr_f, C_p=None, n_p=None):
    """
    Generates Future IPR using the Klins-Clark empirical modifications.
    """
    # Establish constants at Bubble Point (Cb and nb)
    if Pr_p <= Pb:
        n_ratio_p, c_ratio_p = _klins_clark(Pr_p, Pb)
        nb = n_p / n_ratio_p
        Cb = C_p / c_ratio_p
    else:
        if Pwf_test >= Pb:
            J = Qo_test / (Pr_p - Pwf_test)
        else:
            J = Qo_test / ((Pr_p - Pb) + (1 / (2 * Pb)) * (Pb**2 - Pwf_test**2))
        nb = 1.0
        Cb = J / (2 * Pb)
        
    # Project to Future Reservoir Pressure
    if Pr_f <= Pb:
        n_ratio_f, c_ratio_f = _klins_clark(Pr_f, Pb)
        nf = nb * n_ratio_f
        Cf = Cb * c_ratio_f
        
        Qmax_f = Cf * (Pr_f**2)**nf
        Jf = 2 * Cf * Pr_f * nf 
        p_arr = np.linspace(0, Pr_f, 50)
        q_arr = Cf * (Pr_f**2 - p_arr**2)**nf
    else:
        Jf = Cb * 2 * Pb
        p_arr = np.linspace(0, Pr_f, 50)
        q_arr = np.zeros_like(p_arr)
        for i, p in enumerate(p_arr):
            if p >= Pb:
                q_arr[i] = Jf * (Pr_f - p)
            else:
                q_arr[i] = Jf * (Pr_f - Pb) + Cb * (Pb**2 - p**2)**nb
        Qmax_f = Jf * (Pr_f - Pb) + Cb * (Pb**2)**nb
        
    return p_arr, q_arr, Qmax_f, Jf