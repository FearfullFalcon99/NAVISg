import numpy as np

def general_ipr(Pr, k, h, kro, mu_o, Bo, re, rw, skin):
    """
    Evaluates the General IPR curve based exclusively on Equation 7-4.
    Utilizes rock properties and fluid properties (mu_o, Bo) evaluated at reservoir pressure.
    """
    # Denominator combines the geometry/skin term with the PVT properties
    denominator = (np.log(re / rw) - 0.75 + skin) * mu_o * Bo
    
    if denominator == 0:
        J = 0
    else:
        J = (0.00708 * h * k * kro) / denominator
            
    Qmax = J * Pr
    
    # Generate points for the straight-line IPR (constant J approximation)
    ipr_p = np.linspace(Pr, 0, 50)
    ipr_q = J * (Pr - ipr_p)
    
    # Ensure non-negative flow rates
    ipr_q = np.maximum(ipr_q, 0)
    
    return ipr_p, ipr_q, Qmax, J