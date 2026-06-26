import math


# --------------------------------------------------
# Gas Properties
# --------------------------------------------------

def pseudocritical_properties(gas_sg):
    ppc = 709.604 - 58.718 * gas_sg
    Tpc = 170.491 + 307.344 * gas_sg
    return ppc, Tpc


def z_factor(p, T, gas_sg):
    ppc, Tpc = pseudocritical_properties(gas_sg)
    p_eff = max(float(p), 1.0)
    ppr = p_eff / ppc
    Tpr = (T + 460.0) / Tpc

    Z = (
        1.0
        - (3.52 * ppr) / (10 ** (0.9813 * Tpr))
        + (0.274 * ppr ** 2) / (10 ** (0.8157 * Tpr))
    )

    return max(Z, 0.05)


def gas_density(p, T, gas_sg):
    Z = z_factor(p, T, gas_sg)
    p_eff = max(float(p), 1.0)

    return (
        2.7
        * gas_sg
        * p_eff
        / (Z * (T + 460.0))
    )


def gas_viscosity(p, T, gas_sg):
    Z = z_factor(p, T, gas_sg)
    p_eff = max(float(p), 1.0)

    Ta = T + 460.0
    M = 29.0 * gas_sg

    K = (
        ((9.4 + 0.02 * M) * Ta ** 1.5)
        / (209.0 + 19.0 * M + Ta)
    )

    X = 3.5 + 986.0 / Ta + 0.01 * M
    y = 2.4 - 0.2 * X

    rho_gcm3 = (
        0.0433 * gas_sg * p_eff
        / (Z * Ta)
    )

    mu_g = (
        1e-4
        * K
        * math.exp(X * rho_gcm3 ** y)
    )

    return max(mu_g, 0.001)


def gas_volume_factor(p, T, gas_sg):
    Z = z_factor(p, T, gas_sg)
    p_eff = max(float(p), 1.0)

    return (
        0.00504
        * Z
        * (T + 460.0)
        / p_eff
    )


# --------------------------------------------------
# Oil Properties (Kartoatmodjo helper functions)
# --------------------------------------------------

def gas_gravity_correction_kartoatmodjo(gas_sg, oil_api):
    """Correct separator gas gravity to 100 psig reference (Kartoatmodjo eq. 3)."""
    return 1.0 * gas_sg


def solution_gor_kartoatmodjo(p, T, gas_sg, oil_api):
    sg100 = gas_gravity_correction_kartoatmodjo(gas_sg, oil_api)
    TABS = T + 460.0
    if oil_api <= 30.0:
        A = 0.05958
        B = 0.7972
        C = 1.0014
        D = 13.1405
    else:
        A = 0.03150
        B = 0.7587
        C = 1.0937
        D = 11.289
    p_val = max(p, 0.0)
    Rs = A * (sg100 ** B) * (p_val ** C) * (10.0 ** (D * oil_api / TABS))
    return max(Rs, 0.0)


def bubblepoint_pressure_kartoatmodjo(T, Rs, gas_sg, oil_api):
    sg100 = gas_gravity_correction_kartoatmodjo(gas_sg, oil_api)
    TABS = T + 460.0
    if oil_api <= 30.0:
        A = 0.05958
        B = 0.7972
        C = 1.0014
        D = 13.1405
    else:
        A = 0.03150
        B = 0.7587
        C = 1.0937
        D = 11.289
        
    if Rs <= 0:
        return 14.7
        
    denom = A * (sg100 ** B) * (10.0 ** (D * oil_api / TABS))
    if denom <= 0:
        return 14.7
        
    pb = (Rs / denom) ** (1.0 / C)
    return max(pb, 14.7)


def oil_volume_factor_kartoatmodjo(p, T, Rs, gas_sg, oil_api, pb=None, Rs_surface=None):
    sg100 = gas_gravity_correction_kartoatmodjo(gas_sg, oil_api)
    oil_sg = 141.5 / (131.5 + oil_api)
    if Rs_surface is None:
        Rs_surface = Rs
        
    if pb is None:
        pb = bubblepoint_pressure_kartoatmodjo(T, Rs_surface, gas_sg, oil_api)
        
    if p <= pb:
        # Saturated region
        term = (Rs ** 0.755) * (sg100 ** 0.25) * (oil_sg ** -1.5) + 0.45 * T
        term = max(term, 0.0)
        Bo = 0.98496 + 1e-4 * (term ** 1.5)
    else:
        # Undersaturated region
        term_pb = (Rs_surface ** 0.755) * (sg100 ** 0.25) * (oil_sg ** -1.5) + 0.45 * T
        term_pb = max(term_pb, 0.0)
        Bob = 0.98496 + 1e-4 * (term_pb ** 1.5)
        
        # Calculate isothermal compressibility CO
        R_val = max(Rs_surface, 1.0)
        api_val = max(oil_api, 1.0)
        T_val = max(T, 1.0)
        sg100_val = max(sg100, 0.01)
        
        co_A = 0.83415 + 0.5002 * math.log10(R_val) + 0.3613 * math.log10(api_val) + 0.7606 * math.log10(T_val) - 0.35505 * math.log10(sg100_val)
        co = (10.0 ** co_A) / (p * 1e6)
        
        Bo = Bob * math.exp(co * (pb - p))
        
    return Bo


def dead_oil_viscosity_kartoatmodjo(T, oil_api):
    T_val = max(T, 1.0)
    api_val = max(oil_api, 1.5)
    log_api = math.log10(api_val)
    if log_api <= 0:
        log_api = 1e-5
    exponent = 5.7526 * math.log10(T_val) - 26.9718
    visd = 16.0e8 * (T_val ** -2.8177) * (log_api ** exponent)
    return max(visd, 0.01)


def live_oil_viscosity_kartoatmodjo(T, oil_api, Rs, p=None, pb=None, Rs_surface=None, gas_sg=0.65):
    visd = dead_oil_viscosity_kartoatmodjo(T, oil_api)
    
    if Rs_surface is None:
        Rs_surface = Rs
        
    if pb is None:
        pb = bubblepoint_pressure_kartoatmodjo(T, Rs_surface, gas_sg, oil_api)
        
    if p is None:
        p = pb
        
    if p < pb:
        # Saturated region
        term1 = 0.2001 + 0.8428 * (10.0 ** (-0.000845 * Rs))
        term2 = 0.43 + 0.5165 * (10.0 ** (-0.00081 * Rs))
        A_val = term1 * (visd ** term2)
        mu_o = -0.06821 + 0.9824 * A_val + 0.0004034 * (A_val ** 2)
    elif p == pb:
        term1 = 0.2001 + 0.8428 * (10.0 ** (-0.000845 * Rs_surface))
        term2 = 0.43 + 0.5165 * (10.0 ** (-0.00081 * Rs_surface))
        A_val = term1 * (visd ** term2)
        mu_o = -0.06821 + 0.9824 * A_val + 0.0004034 * (A_val ** 2)
    else:
        # Undersaturated region
        term1 = 0.2001 + 0.8428 * (10.0 ** (-0.000845 * Rs_surface))
        term2 = 0.43 + 0.5165 * (10.0 ** (-0.00081 * Rs_surface))
        A_val = term1 * (visd ** term2)
        visb = -0.06821 + 0.9824 * A_val + 0.0004034 * (A_val ** 2)
        
        visb_val = max(visb, 1e-4)
        term_p = -0.006517 * (visb_val ** 1.8148) + 0.038 * (visb_val ** 1.590)
        mu_o = 1.00081 * visb + 0.001127 * (p - pb) * term_p
        
    return max(mu_o, 0.01)


# --------------------------------------------------
# Oil Properties (Unified routing functions)
# --------------------------------------------------

def solution_gor(p, T, gas_sg, oil_api, pvt_correlation='Standing'):
    if pvt_correlation == 'Kartoatmodjo':
        return solution_gor_kartoatmodjo(p, T, gas_sg, oil_api)

    y = (
        0.00091 * T
        - 0.0125 * oil_api
    )

    Rs = gas_sg * (
        ((p / 18.2) + 1.4)
        / (10 ** y)
    ) ** (1.0 / 0.83)

    return max(Rs, 0.0)


def bubblepoint_pressure(T, Rs, gas_sg, oil_api, pvt_correlation='Standing'):
    if pvt_correlation == 'Kartoatmodjo':
        return bubblepoint_pressure_kartoatmodjo(T, Rs, gas_sg, oil_api)

    y = (
        0.00091 * T
        - 0.0125 * oil_api
    )

    pb = 18.2 * (
        (Rs / gas_sg) ** 0.83
        * 10 ** y
        - 1.4
    )

    return max(pb, 14.7)


def oil_volume_factor(p, T, Rs, gas_sg, oil_api, pb=None, pvt_correlation='Standing', Rs_surface=None):
    if pvt_correlation == 'Kartoatmodjo':
        return oil_volume_factor_kartoatmodjo(p, T, Rs, gas_sg, oil_api, pb, Rs_surface)

    # Standing correlation applies along saturation line (p <= pb)
    # Above bubblepoint: apply isothermal compressibility
    
    oil_sg = (
        141.5
        / (131.5 + oil_api)
    )

    # Standing formula for Bo  
    F = (
        Rs * (gas_sg / oil_sg) ** 0.5
        + 1.25 * T
    )
    
    Bo = (
        0.972
        + 1.47e-4 * F ** 1.175
    )
    
    # Above bubblepoint: apply isothermal compressibility reduction
    # Oil compresses as pressure increases above pb (typical c_o = 8x10^-5 psi^-1)
    if pb is not None and p > pb:
        c_o = 8e-5
        Bo = Bo * math.exp(-c_o * (p - pb))
    
    return Bo


def dead_oil_viscosity(T, oil_api, pvt_correlation='Standing'):
    if pvt_correlation == 'Kartoatmodjo':
        return dead_oil_viscosity_kartoatmodjo(T, oil_api)

    X = (
        T ** (-1.163)
        * math.exp(
            6.9824
            - 0.04658 * oil_api
        )
    )

    mu_od = 10 ** X - 1.0

    return max(mu_od, 0.01)


def live_oil_viscosity(T, oil_api, Rs, p=None, pb=None, pvt_correlation='Standing', Rs_surface=None, gas_sg=0.65):
    if pvt_correlation == 'Kartoatmodjo':
        return live_oil_viscosity_kartoatmodjo(T, oil_api, Rs, p, pb, Rs_surface, gas_sg)

    # Beggs-Robinson correlation for live oil viscosity
    
    mu_od = dead_oil_viscosity(
        T,
        oil_api
    )

    A = 10 ** (
        Rs
        * (
            2.2e-7 * Rs
            - 7.4e-4
        )
    )

    b = (
        0.68 / 10 ** (8.62e-5 * Rs)
        + 0.25 / 10 ** (1.1e-3 * Rs)
        + 0.062 / 10 ** (3.74e-3 * Rs)
    )

    mu_o_sat = A * mu_od ** b
    
    # Above bubblepoint: viscosity increases with pressure (no free gas)
    # Pressure effect: ~0.2-0.5% increase per 1000 psi
    if pb is not None and p is not None and p > pb:
        # Use typical compressibility effect: mu increases with pressure
        delta_mu_psi = 0.5e-5  # increase per psi above pb
        mu_o = mu_o_sat * (1.0 + delta_mu_psi * (p - pb))
    else:
        mu_o = mu_o_sat

    return max(mu_o, 0.01)


# --------------------------------------------------
# Surface Tension
# --------------------------------------------------

def surface_tension(oil_api, p):
    p_eff = max(float(p), 1.0)

    sigma_dead = max(
        39.0 - 0.2571 * oil_api,
        1.0
    )

    sigma = (
        sigma_dead
        * math.exp(
            -0.00255 * p_eff ** 0.56
        )
    )

    return max(sigma, 1.0)


# --------------------------------------------------
# Water Properties
# --------------------------------------------------

def water_volume_factor(p, T, water_sg):
    p_eff = max(float(p), 1.0)
    # Water compresses with pressure, so Bw decreases
    bw = (
        1.0
        + 3.5e-5 * max(T - 60.0, 0.0)
        - 4.0e-6 * max(p_eff - 14.7, 0.0)
        + 0.01 * max(water_sg - 1.0, 0.0)
    )

    return max(bw, 0.9)


def water_viscosity(p, T, water_sg):
    p_eff = max(float(p), 1.0)

    mu_w = (
        1.0
        * math.exp(-0.0065 * max(T - 60.0, 0.0))
        * (1.0 + 2.5e-5 * max(p_eff - 14.7, 0.0))
        * (1.0 + 0.08 * max(water_sg - 1.0, 0.0))
    )

    return max(mu_w, 0.2)


def water_density(p, T, water_sg):

    bw = water_volume_factor(p, T, water_sg)
    return 62.4 * water_sg / bw


# --------------------------------------------------
# Main Property Package
# --------------------------------------------------

def fluid_properties_at_PT(
    p,
    T,
    q_o,
    q_w,
    q_g_surface,
    gas_sg,
    oil_api,
    water_sg,
    d_in,
    Rs_surface,
    pvt_correlation='Standing',
    T_res=None,
):

    T_oil = T_res if T_res is not None else T

    # Bubblepoint
    pb = bubblepoint_pressure(
        T_oil,
        Rs_surface,
        gas_sg,
        oil_api,
        pvt_correlation=pvt_correlation
    )

    # Solution GOR
    if p < pb:

        Rs = solution_gor(
            p,
            T_oil,
            gas_sg,
            oil_api,
            pvt_correlation=pvt_correlation
        )

        Rs = min(
            Rs,
            Rs_surface
        )

    else:

        Rs = Rs_surface

    # Formation volume factors
    Bo = oil_volume_factor(
        p,
        T_oil,
        Rs,
        gas_sg,
        oil_api,
        pb=pb,
        pvt_correlation=pvt_correlation,
        Rs_surface=Rs_surface
    )

    Bg = gas_volume_factor(
        p,
        T,
        gas_sg
    )

    # Densities
    oil_sg = (
        141.5
        / (131.5 + oil_api)
    )

    rho_o = (
        (
            62.4 * oil_sg
            + 0.0136 * gas_sg * Rs
        )
        / Bo
    )

    rho_w = 62.4 * water_sg

    rho_g = gas_density(
        p,
        T,
        gas_sg
    )

    # In-situ rates
    q_o_is = (
        q_o * Bo * 5.615
        / 86400.0
    )

    q_w_is = (
        q_w * 5.615
        / 86400.0
    )

    free_gas_scf_day = max(
        q_g_surface * 1000.0
        - Rs * q_o,
        0.0
    )

    q_g_is = (
        free_gas_scf_day
        * Bg
        * 5.615
        / 86400.0
    )

    # Pipe area
    A = (
        math.pi
        * (d_in / 12.0) ** 2
        / 4.0
    )

    # Velocities
    v_sl = (
        q_o_is + q_w_is
    ) / A

    v_sg = q_g_is / A

    v_m = v_sl + v_sg

    lam_l = (
        v_sl / v_m
        if v_m > 0
        else 1.0
    )

    # Water cut
    f_w = (
        q_w / (q_o + q_w)
        if (q_o + q_w) > 0
        else 0.0
    )

    # Mixture liquid density
    rho_l = (
        rho_o * (1.0 - f_w)
        + rho_w * f_w
    )

    # Mixture liquid viscosity
    mu_o = live_oil_viscosity(
        T_oil,
        oil_api,
        Rs,
        p=p,
        pb=pb,
        pvt_correlation=pvt_correlation,
        Rs_surface=Rs_surface,
        gas_sg=gas_sg
    )

    mu_w = water_viscosity(
        p,
        T,
        water_sg
    )

    mu_l = (
        mu_o * (1.0 - f_w)
        + mu_w * f_w
    )

    sigma = surface_tension(
        oil_api,
        p
    )

    # Return all properties in a dict named 'fp' (fluid properties) assigned to fp in traverse.py
    return dict(
        p=p,
        T=T,
        pb=pb,
        Rs=Rs,
        Bo=Bo,
        Bw=water_volume_factor(p, T, water_sg),
        Bg=Bg,
        Z=z_factor(p, T, gas_sg),

        rho_l=rho_l,
        rho_o=rho_o,
        rho_w=water_density(p, T, water_sg),
        rho_g=rho_g,

        mu_l=mu_l,
        mu_o=mu_o,
        mu_w=mu_w,
        mu_g=gas_viscosity(
            p,
            T,
            gas_sg
        ),

        sigma=sigma,

        v_sl=v_sl,
        v_sg=v_sg,
        v_m=v_m,

        lam_l=lam_l,

        A=A,
        d_in=d_in,
    )