"""
correlations/beggs_brill.py
============================
Beggs and Brill (1973) two-phase flow correlation with Brill & Beggs (1991)
updated flow-regime map.

Valid for ALL pipe inclination angles: -90° (downhill) to +90° (uphill/vertical).
For a vertical well, pass inclination_deg=90.0 (the default).

Implementation notes
---------------------
* Flow-pattern detection uses the UPDATED 1991 four-boundary map
  (L1–L4), which adds an explicit Transition regime between Segregated
  and Intermittent.
* Holdup is computed in horizontal reference (H_L(0)) then corrected
  for inclination via ψ.  The correction uses N_LV (liquid velocity
  number), identical to the dimensionless group already present in H-B.
* Friction Reynolds number uses NO-SLIP linear-blend viscosity
  (μ_m = μ_L·λ_L + μ_g·(1-λ_L)), NOT the exponential H-B definition.
  This is the standard B&B definition from Brill & Mukherjee (1999).
* The two-phase friction multiplier S / f_tp = f_n·exp(S) is the same
  formula already present in hagedorn_brown.py — shared logic,
  separately implemented here for module independence.
* Acceleration (kinetic) term follows the standard B&B form, identical
  to H-B.
* The fp dict contract is IDENTICAL to what fluid_properties_at_PT()
  already returns, so no PVT changes are needed.

References
-----------
1. Beggs, H.D. and Brill, J.P. (1973). SPE-4007-PA.
2. Brill, J.P. and Beggs, H.D. (1991). Two-Phase Flow in Pipes, 6th ed.
3. Brill, J.P. and Mukherjee, H. (1999). Multiphase Flow in Wells,
   SPE Monograph Vol. 17.
"""

import math


# ─────────────────────────────────────────────────────────────────────────────
#  Friction factor — Chen (1979) explicit (same as hagedorn_brown.py)
# ─────────────────────────────────────────────────────────────────────────────

def _friction_chen(Re, roughness_in, d_in):
    """Darcy friction factor via Chen (1979) explicit formula."""
    if Re <= 0:
        return 0.025
    if Re < 2100:
        return 64.0 / Re          # laminar, Darcy

    e = roughness_in / d_in       # relative roughness
    tmp = -2.0 * math.log10(
        e / 3.7065
        - (5.0452 / Re) * math.log10(
            e ** 1.1098 / 2.8257 + (7.149 / Re) ** 0.8981
        )
    )
    return (1.0 / tmp) ** 2


# ─────────────────────────────────────────────────────────────────────────────
#  Two-phase friction multiplier (shared with H-B — same S formula)
# ─────────────────────────────────────────────────────────────────────────────

def _two_phase_friction_multiplier(lam_l, H_L):
    """
    Compute f_tp / f_n = exp(S) via the Beggs-Brill S function.

    y = λ_L / H_L²
    Special branch for 1 < y < 1.2 prevents the denominator going
    through zero (log singularity).
    """
    if H_L <= 0:
        return 1.0

    y = lam_l / max(H_L ** 2, 1e-10)
    y = max(y, 1e-10)

    if 1.0 < y < 1.2:
        S = math.log(2.2 * y - 1.2)
    else:
        lx  = math.log(y)
        den = -0.0523 + 3.182 * lx - 0.8725 * lx ** 2 + 0.01853 * lx ** 4
        S   = lx / den if abs(den) > 1e-10 else 0.0

    return math.exp(S)


# ─────────────────────────────────────────────────────────────────────────────
#  Flow-pattern detection (updated 1991 map, four boundaries)
# ─────────────────────────────────────────────────────────────────────────────

def _flow_pattern(lam_l, Fr):
    """
    Determine horizontal-equivalent flow pattern.

    Returns one of: 'segregated', 'transition', 'intermittent', 'distributed'

    Boundaries (Brill & Beggs 1991):
        L1 = 316   · λ_L^0.302
        L2 = 9.252e-4 · λ_L^-2.4684
        L3 = 0.10  · λ_L^-1.4516
        L4 = 0.50  · λ_L^-6.738
    """
    lam_l = max(lam_l, 1e-8)

    L1 = 316.0    * lam_l **  0.302
    L2 = 9.252e-4 * lam_l ** -2.4684
    L3 = 0.10     * lam_l ** -1.4516
    L4 = 0.50     * lam_l ** -6.738

    # Segregated
    if (lam_l < 0.01 and Fr < L1) or (lam_l >= 0.01 and Fr < L2):
        return 'segregated', L1, L2, L3, L4

    # Transition (between segregated and intermittent)
    if lam_l >= 0.01 and L2 <= Fr <= L3:
        return 'transition', L1, L2, L3, L4

    # Intermittent
    if (0.01 <= lam_l < 0.4 and L3 < Fr <= L1) or \
       (lam_l >= 0.4        and L3 < Fr <= L4):
        return 'intermittent', L1, L2, L3, L4

    # Distributed (everything else)
    return 'distributed', L1, L2, L3, L4


# ─────────────────────────────────────────────────────────────────────────────
#  Horizontal holdup H_L(0)
# ─────────────────────────────────────────────────────────────────────────────

# Coefficients: (A, alpha, beta)  →  H_L(0) = A · λ_L^alpha / Fr^(-beta)
#                                           = A · λ_L^alpha · Fr^beta_exp
# Stored as (A, alpha, beta) where the formula is:
#   H_L(0) = A * lam_l**alpha / Fr**abs_beta
# The negative exponent on Fr is encoded as: H_L(0) = A * lam_l^a / Fr^b
# so b values below are POSITIVE (meaning Fr appears in denominator).

_HL0_COEFFS = {
    'segregated':   (0.98,  0.4846, 0.0868),
    'intermittent': (0.845, 0.5351, 0.0173),
    'distributed':  (1.065, 0.5824, 0.0609),
}


def _horizontal_holdup(pattern, lam_l, Fr, L2, L3):
    """
    H_L(0) for horizontal flow (θ = 0).
    For Transition: weighted average of Segregated and Intermittent.
    Constraint: H_L(0) ≥ λ_L always.
    """
    Fr = max(Fr, 1e-10)

    if pattern == 'transition':
        # Blend weight
        eta = (L3 - Fr) / max(L3 - L2, 1e-10)
        eta = max(min(eta, 1.0), 0.0)

        A_s, a_s, b_s = _HL0_COEFFS['segregated']
        A_i, a_i, b_i = _HL0_COEFFS['intermittent']
        hl0_s = A_s * lam_l ** a_s / Fr ** b_s
        hl0_i = A_i * lam_l ** a_i / Fr ** b_i
        hl0   = eta * hl0_s + (1.0 - eta) * hl0_i
    else:
        A, a, b = _HL0_COEFFS[pattern]
        hl0 = A * lam_l ** a / Fr ** b

    return max(min(hl0, 1.0), lam_l)


# ─────────────────────────────────────────────────────────────────────────────
#  Inclination correction factor ψ  →  H_L = H_L(0) · ψ
# ─────────────────────────────────────────────────────────────────────────────

def _inclination_correction(pattern, lam_l, Fr, N_LV, theta_deg):
    """
    Compute ψ = 1 + C·[sin(1.8θ) - (1/3)·sin³(1.8θ)]
    where θ is inclination from horizontal in RADIANS.

    C coefficients (Brill & Beggs 1991):

    Uphill (θ > 0):
        Segregated:   C = (1-λ_L)·ln(0.011 · λ_L^-3.768 · Fr^-1.614 · N_LV^3.539)
        Intermittent: C = (1-λ_L)·ln(2.96  · λ_L^0.305  · Fr^0.0978 · N_LV^-0.4473)
        Distributed:  C = 0

    Downhill (θ < 0), all patterns:
        C = (1-λ_L)·ln(4.70 · λ_L^-0.3692 · Fr^-0.5056 · N_LV^0.1244)

    Constraint: C ≥ 0 (clamp any negative result to 0).
    """
    theta_rad = math.radians(theta_deg)

    # ψ multiplier shape: sin(1.8θ) - (1/3)·sin³(1.8θ)
    angle = 1.8 * theta_rad
    sin_term = math.sin(angle) - (1.0 / 3.0) * math.sin(angle) ** 3

    lam_l = max(lam_l, 1e-8)
    Fr    = max(Fr,    1e-10)
    N_LV  = max(N_LV,  1e-10)

    # Effective pattern for transition: use intermittent coefficients
    eff_pattern = 'intermittent' if pattern == 'transition' else pattern

    if theta_deg == 0.0:
        return 1.0         # horizontal → no correction

    elif theta_deg > 0.0:  # ── uphill ──
        if eff_pattern == 'distributed':
            C = 0.0
        elif eff_pattern == 'segregated':
            arg = 0.011 * lam_l ** (-3.768) * Fr ** (-1.614) * N_LV ** 3.539
            C = (1.0 - lam_l) * math.log(max(arg, 1e-10))
        else:  # intermittent (and transition)
            arg = 2.96 * lam_l ** 0.305 * Fr ** 0.0978 * N_LV ** (-0.4473)
            C = (1.0 - lam_l) * math.log(max(arg, 1e-10))

    else:                  # ── downhill ──
        arg = 4.70 * lam_l ** (-0.3692) * Fr ** (-0.5056) * N_LV ** 0.1244
        C = (1.0 - lam_l) * math.log(max(arg, 1e-10))

    C = max(C, 0.0)        # physical constraint
    return 1.0 + C * sin_term


# ─────────────────────────────────────────────────────────────────────────────
#  Liquid velocity number N_LV  (same dimensionless group as in H-B)
# ─────────────────────────────────────────────────────────────────────────────

def _N_LV(v_sl, rho_l, sigma):
    sigma = max(sigma, 0.1)
    return 1.938 * v_sl * (rho_l / sigma) ** 0.25


def flow_regime(fp):
    """Return the Beggs-Brill flow regime label for a given fluid state."""
    v_m   = fp['v_m']
    lam_l = fp['lam_l']
    d_in  = fp['d_in']

    d_ft = d_in / 12.0
    g_c  = 32.174
    if v_m < 1e-6:
        return 'segregated'

    Fr = v_m ** 2 / (g_c * d_ft)
    pattern, _, _, _, _ = _flow_pattern(lam_l, Fr)
    return pattern


def liquid_holdup(fp, inclination_deg=90.0):
    """Return Beggs-Brill in-situ liquid holdup for a given fluid state."""
    rho_l = fp['rho_l']
    v_sl  = fp['v_sl']
    v_m   = fp['v_m']
    lam_l = fp['lam_l']
    d_in  = fp['d_in']
    sigma = fp['sigma']

    d_ft = d_in / 12.0
    g_c  = 32.174
    if v_m < 1e-6:
        return 1.0

    Fr = v_m ** 2 / (g_c * d_ft)
    pattern, _, L2, L3, _ = _flow_pattern(lam_l, Fr)
    HL0 = _horizontal_holdup(pattern, lam_l, Fr, L2, L3)
    NLV = _N_LV(v_sl, rho_l, sigma)
    psi = _inclination_correction(pattern, lam_l, Fr, NLV, inclination_deg)

    return max(min(HL0 * psi, 1.0), lam_l)


def holdup_and_regime(fp, inclination_deg=90.0):
    """Return (liquid holdup, flow regime) for traverse table output."""
    return liquid_holdup(fp, inclination_deg), flow_regime(fp)


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def pressure_gradient(fp, roughness=0.0006, inclination_deg=90.0):
    """
    Beggs-Brill (1973/1991) two-phase pressure gradient [psi/ft].

    Parameters
    ----------
    fp              : fluid property dict from fluid_properties_at_PT()
                      Required keys: p, rho_l, rho_g, mu_l, mu_g,
                                     v_sl, v_sg, v_m, lam_l, d_in, sigma
    roughness       : absolute pipe roughness [inches], default 0.0006
    inclination_deg : pipe angle from horizontal [degrees]
                      +90 = vertical upward (typical producer)
                       0  = horizontal
                      -90 = vertical downward
                      Default 90.0 for a vertical well (same as H-B usage).

    Returns
    -------
    dp/dh [psi/ft]  positive = pressure increases going deeper (downward traverse)
    """
    # ── Unpack fp dict ─────────────────────────────────────────────────────
    p     = fp['p']
    rho_l = fp['rho_l'];  rho_g = fp['rho_g']
    mu_l  = fp['mu_l'];   mu_g  = fp['mu_g']
    v_sl  = fp['v_sl'];   v_sg  = fp['v_sg']
    v_m   = fp['v_m'];    lam_l = fp['lam_l']
    d_in  = fp['d_in'];   sigma = fp['sigma']

    d_ft  = d_in / 12.0
    g_c   = 32.174    # lbm·ft / (lbf·s²)

    # ── Guard: zero or near-zero flow ──────────────────────────────────────
    if v_m < 1e-6:
        # Static column — elevation only, use liquid density
        sin_theta = math.sin(math.radians(inclination_deg))
        return rho_l * sin_theta / 144.0

    # ── Froude number ──────────────────────────────────────────────────────
    Fr = v_m ** 2 / (g_c * d_ft)   # dimensionless (g_c = 32.174 ft/s²)

    # ── Flow pattern ───────────────────────────────────────────────────────
    pattern, L1, L2, L3, L4 = _flow_pattern(lam_l, Fr)

    # ── Horizontal holdup H_L(0) ───────────────────────────────────────────
    HL0 = _horizontal_holdup(pattern, lam_l, Fr, L2, L3)

    # ── Inclination correction → actual holdup H_L ─────────────────────────
    NLV  = _N_LV(v_sl, rho_l, sigma)
    psi  = _inclination_correction(pattern, lam_l, Fr, NLV, inclination_deg)
    H_L  = max(min(HL0 * psi, 1.0), lam_l)   # clamp [λ_L, 1.0]

    # ── Mixture densities ──────────────────────────────────────────────────
    rho_s   = rho_l * H_L   + rho_g * (1.0 - H_L)    # slip density
    rho_ns  = rho_l * lam_l + rho_g * (1.0 - lam_l)  # no-slip density

    # ── Elevation gradient ─────────────────────────────────────────────────
    sin_theta = math.sin(math.radians(inclination_deg))
    grad_el   = rho_s * sin_theta / 144.0              # psi/ft

    # ── Friction gradient ──────────────────────────────────────────────────
    # No-slip mixture viscosity (linear blend — B&B standard, NOT exponential)
    mu_ns = mu_l * lam_l + mu_g * (1.0 - lam_l)

    Re    = (1488.0 * rho_ns * v_m * d_ft / mu_ns) if mu_ns > 0 else 1e6
    f_n   = _friction_chen(Re, roughness, d_in)
    eS    = _two_phase_friction_multiplier(lam_l, H_L)
    f_tp  = f_n * eS

    # Friction term: f_tp · ρ_ns · v_m² / (2·g_c·d) in lbf/ft²/ft → /144 for psi/ft
    grad_f = 2.0 * f_tp * rho_ns * v_m ** 2 / (g_c * d_ft * 144.0)

    # ── Acceleration (kinetic) gradient ────────────────────────────────────
    # Ek = ρ_s · v_m · v_sg / (g_c · p · 144)
    # dp/dL = (el + f) / (1 - Ek)
    Ek = rho_s * v_m * v_sg / (g_c * p * 144.0)
    Ek = max(min(Ek, 0.99), 0.0)

    total_grad = (grad_el + grad_f) / (1.0 - Ek)

    return total_grad
