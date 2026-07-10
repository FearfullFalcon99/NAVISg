def get_annular_equivalent_diameters(D_c, D_t):
    """
    Calculates the equivalent parameters for annular frictional pressure drop.
    Replaces pipeline diameter logic with casing-tubing annulus equivalents[cite: 1].
    
    Parameters:
    - D_c (float): Casing Internal Diameter in inches
    - D_t (float): Tubing Outside Diameter in inches
    
    Returns:
    - D_equivalent_friction (float): Substitute for D^5 -> (Dc^2 - Dt^2)^2 * (Dc - Dt)[cite: 1]
    - D_equivalent_reynolds (float): Substitute for D in N_Re -> Dc + Dt[cite: 1]
    """
    # Convert inches to feet for standard fluid dynamics equations if required by outer engine
    Dc_ft = D_c / 12.0
    Dt_ft = D_t / 12.0
    
    # Hydraulic diameter logic for pressure drop (D^5 equivalent)
    D_eq_fric = ((Dc_ft**2) - (Dt_ft**2))**2 * (Dc_ft - Dt_ft)
    
    # Equivalent diameter for Reynolds Number
    D_eq_reynolds = Dc_ft + Dt_ft
    
    return D_eq_fric, D_eq_reynolds


# 4. Annular geometry for surface injection pressure sizing-----------------------------
    d_fric, d_re = get_annular_equivalent_diameters(D_c, D_t)
    