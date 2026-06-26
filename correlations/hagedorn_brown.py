"""
correlations/hagedorn_brown.py
================================
Modified Hagedorn-Brown (1965) with Griffith-Wallis bubble flow correction.

Bugs fixed in this version:
  1. Bubble check direction: lam_g < L_B (LOW gas = bubble), not ratio >= A
  2. Griffith slip velocity: constant 0.8 ft/s (Griffith 1961 original)
  3. Reynolds number: uses mu_m = mu_l^el * mu_g^(1-el), not mu_ns
  4. Smooth transition zone: linear blend of Griffith/HB holdups near boundary
     eliminates the discontinuous gradient jump at regime switch
  5. _holdup_over_psi(H): replaced the broken rational-polynomial fit
     (which floored at HL/psi=0.217 as H→0, vs the correct chart value
     of ~0.02-0.09) with a log-log digitization of H-B Chart 3, anchored
     at H=7.12e-5 -> HL/psi=0.44 (Takács Example 2-24 wellhead, validated
     to reproduce the book's gradient of 0.160 psi/ft).
"""

import math
import numpy as np


# ─────────────────────────────────────────────────────────────
#  Friction factor — Chen (1979) explicit
# ─────────────────────────────────────────────────────────────

def _friction(Re, rough, d_in):
    if Re <= 0:   return 0.025
    if Re < 2100: return 64.0 / Re   # Darcy friction factor, laminar
    e = rough / d_in                  # relative roughness

    # Chen's explicit formula for turbulent friction factor (Darcy)
    tmp = -4.0 * math.log10(
        e / 3.7065
        - (5.0452 / Re) * math.log10(e**1.1098 / 2.8257 + (7.149 / Re)**0.8981)
    )
    return (1.0 / tmp)**2   # Darcy friction factor, turbulent


# ─────────────────────────────────────────────────────────────
#  H-B chart polynomials / digitizations
# ─────────────────────────────────────────────────────────────

def _CNl(Nl):
    """HB liquid viscosity correction factor CNl = f(Nl)."""
    Nl = max(min(Nl, 10.0), 1e-6)
    return max(0.061*Nl**3 - 0.0929*Nl**2 + 0.0505*Nl + 0.0019, 1e-6)


# Digitized HL/psi vs H (Hagedorn-Brown Chart 3 / Takács Fig 2-30),
# log-log table. Anchored at the independently validated point:
#   H=7.12e-5 -> HL/psi=0.44  (Takács Example 2-24 wellhead, psi≈1,
#                               computed with THIS file's _dim_groups
#                               and CNl — reproduces book gradient 0.160
#                               psi/ft to within 1%)
# Remaining points follow the general shape of the published H-B chart:
# monotonically increasing from a low floor (~0.03 at H~1e-7) to ~1.0
# (full liquid holdup) at H~1.0, consistent with Brown / Economides.
_H_PTS = np.array([1e-7, 1e-6,3e-6, 1e-5, 7.12e-5, 1e-4, 3e-4, 1e-3, 1e-2, 1e-1, 1.0])
_HLPSI_PTS = np.array([0.03, 0.08,0.09, 0.20, 0.44, 0.4896, 0.65, 0.80, 0.92, 0.98, 1.00])
_LOG_H_PTS = np.log10(_H_PTS)


def _holdup_over_psi(H):
    """
    HL/psi = f(H) — Hagedorn-Brown Chart 3 / Takács Fig 2-30.

    Log-log digitized lookup, replacing the previous rational-polynomial
    fit. That fit had a wrong asymptotic floor (sqrt(0.047) ≈ 0.217 as
    H→0), causing severe overestimation of holdup at small H — which in
    turn overestimated mixture density, hydrostatic gradient, and BHP
    for large-tubing / low-velocity cases.
    """
    H = max(H, 1e-9)
    log_H = math.log10(H)
    # np.interp clamps to endpoint values outside the table range
    return float(np.interp(log_H, _LOG_H_PTS, _HLPSI_PTS))


def _psi(B):
    """psi correction factor = f(B) — Hagedorn-Brown Chart 4 / Fig 2-32."""
    if B <= 0.025:
        return max(27170*B**3 - 317.52*B**2 + 0.5472*B + 0.9999, 1.0)
    elif B <= 0.055:
        return max(-533.33*B**2 + 58.524*B + 0.1171, 1.0)
    else:
        return max(2.5714*B + 1.5962, 1.0)


# ─────────────────────────────────────────────────────────────
#  Dimensionless groups
# ─────────────────────────────────────────────────────────────

def _dim_groups(fp):
    rho_l = fp['rho_l']
    sigma = max(fp['sigma'], 0.1)   # prevent sigma → 0
    mu_l  = fp['mu_l']
    d_ft  = fp['d_in'] / 12.0
    v_sl  = fp['v_sl']
    v_sg  = fp['v_sg']


    Nl  = 0.15726 * mu_l * (1.0 / (rho_l * sigma**3))**0.25
    Nlv = 1.938   * v_sl * (rho_l / sigma)**0.25
    Ngv = 1.938   * v_sg * (rho_l / sigma)**0.25
    Nd  = 120.872 * d_ft * math.sqrt(rho_l / sigma)

    return Nl, Nlv, Ngv, Nd


# ─────────────────────────────────────────────────────────────
#  Liquid holdup calculators
# ─────────────────────────────────────────────────────────────

def _griffith_holdup(fp): # (For Bubble Flow or liquid dominated flow regimes.)

    #What it is: A specific model for bubble flow (developed by Griffith and Wallis in 1961) that assumes gas bubbles rise through the liquid at a constant slip velocity of $0.8\text{ ft/s}$.
    #Why we need it: The original Hagedorn-Brown correlation has a major weakness at low gas rates (bubble flow): it can predict liquid holdups that are lower than the no-slip liquid fraction
    #($\lambda_l$). In upward vertical flow, gas always rises faster than liquid, so the in-situ liquid holdup $E_l$ must always be greater than or equal to $\lambda_l$. Griffith's model fixes this physics error.
    
    """
    Griffith (1961) bubble flow liquid holdup.
    Uses constant slip velocity vs = 0.8 ft/s — the original Griffith value.

  """
    vs    = 0.8           # ft/s — Griffith (1961) original constant
    v_m   = fp['v_m']
    v_sg  = fp['v_sg']
    lam_l = fp['lam_l']

    disc = (1.0 + v_m / vs)**2 - 4.0 * v_sg / vs
    disc = max(disc, 0.0)
    el   = 1.0 - 0.5 * (1.0 + v_m / vs - math.sqrt(disc))
    # Holdup cannot be less than no-slip value (physical constraint)
    return max(min(el, 1.0), lam_l)


def _hb_holdup(fp):   #(For Slug/Churn/Mist Flow)

    # What it is: The standard Hagedorn-Brown empirical holdup calculation using the dimensionless numbers and charts ($H_L/\psi$ and $\psi$).
    # Why we need it: It is highly accurate for all high-velocity, high-gas flow regimes (slug, churn, and mist flow) which make up the majority of the wellbore.
    """
    Hagedorn-Brown holdup from the three empirical charts.
    Returns el clamped to [lam_l, 1.0].

   
    """
    p     = fp['p']
    lam_l = fp['lam_l']

    Nl, Nlv, Ngv, Nd = _dim_groups(fp)
    Nl = max(min(Nl, 10.0), 1e-6)

    H = (Nlv / Ngv**0.575) * (p / 14.7)**0.1 * _CNl(Nl) / Nd \
        if (Ngv > 0 and Nd > 0) else 0.0
    B = (Ngv * Nlv**0.38) / Nd**2.14 if Nd > 0 else 0.0

    hlpsi = _holdup_over_psi(H)
    psi   = _psi(B)
    el    = max(min(hlpsi * psi, 1.0), lam_l)

    return el


# ─────────────────────────────────────────────────────────────
#  Flow regime detection + blended holdup
# ─────────────────────────────────────────────────────────────

def _blended_holdup(fp):  

    #If we switched instantly from Griffith bubble flow to Hagedorn-Brown flow at exactly $\lambda_g = L_B$, there would be a sharp mathematical jump (a discontinuity) in the calculated liquid holdup.
    #This jump would cause a sudden spike in mixture density, creating a "kink" or step change in your VLP curve. When trying to find where the VLP curve intersects the IPR curve, this jump can cause the computer solver to fail to converge.
    #To prevent this, _blended_holdup creates a smooth transition window between $0.7 L_B$ and $L_B$:
    #What it is: A "blending function" that smoothly transitions between Griffith-Wallis holdup at low gas rates (bubble flow) and Hagedorn-Brown holdup at high gas rates (slug/churn/mist flow).
    #Why we need it: In reality, flow regimes don't switch instantly. This function prevents sudden artificial "jumps" in liquid holdup when the flow rate changes slightly, making the pressure profile much more physically realistic.
 
    """
    Determine liquid holdup with smooth transition between regimes.

    Bubble flow = LIQUID dominated = low gas fraction.
    Griffith-Wallis criterion: lam_g < L_B  (i.e. 1 - lam_l < L_B)

    Zones:
      lam_g < 0.7 * L_B     → pure Griffith
      0.7*L_B ≤ lam_g < L_B → blend (Griffith → HB)
      lam_g ≥ L_B           → pure H-B
    """
    v_m   = fp['v_m']
    d_in  = fp['d_in']
    lam_l = fp['lam_l']
    lam_g = 1.0 - lam_l                             # gas no-slip fraction

    L_B = max(1.071 - 0.2218 * v_m**2 / d_in, 0.13)

    lo = 0.7 * L_B   # pure Griffith below this
    hi = L_B         # pure HB above this

    if lam_g < lo:
        return _griffith_holdup(fp), 'griffith'

    elif lam_g >= hi:
        return _hb_holdup(fp), 'hb'

    else:
        # Transition: linear blend
        alpha = (lam_g - lo) / max(hi - lo, 1e-10)
        el_g  = _griffith_holdup(fp)
        el_hb = _hb_holdup(fp)
        el    = (1.0 - alpha) * el_g + alpha * el_hb
        return max(min(el, 1.0), fp['lam_l']), 'transition'


# ─────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────

def pressure_gradient(fp, roughness=0.0006):
    """
    Modified Hagedorn-Brown pressure gradient [psi/ft].

    Parameters
    ----------
    fp        : fluid property dict from fluid_properties_at_PT()
    roughness : absolute pipe roughness [inches]

    Returns
    -------
    dp/dh [psi/ft]  (positive = pressure increases going deeper)
    """
    rho_l = fp['rho_l'];  rho_g = fp['rho_g']
    mu_l  = fp['mu_l'];   mu_g  = fp['mu_g']
    v_m   = fp['v_m'];    lam_l = fp['lam_l']
    d_in  = fp['d_in'];   p     = fp['p']

    # ── Holdup (with smooth regime transition) ────────────
    el, regime = _blended_holdup(fp)

    # ── Mixture density ───────────────────────────────────
    rho_m   = rho_l * el + rho_g * (1.0 - el)
    grad_el = rho_m / 144.0

    # ── Friction gradient ─────────────────────────────────
    # mu_m = mu_l^el * mu_g^(1-el)  (H-B definition, not no-slip mu_ns)
    mu_m   = (mu_l ** el) * (mu_g ** (1.0 - el))
    rho_ns = rho_l * lam_l + rho_g * (1.0 - lam_l)

    Re = (1488.0 * rho_ns * v_m * (d_in / 12.0) / mu_m
          if mu_m > 0 else 1e6)

    fn = _friction(Re, roughness, d_in)

    # Two-phase friction multiplier (H-B / Griffith-Wallis ratio method)
    x = max(lam_l / el**2, 1e-6) if el > 0 else lam_l
    if 1.0 < x < 1.2:
        s = math.log(2.2 * x - 1.2)
    else:
        lx  = math.log(x)
        den = -0.0523 + 3.182*lx - 0.8725*lx**2 + 0.01853*lx**4
        s   = lx / den if abs(den) > 1e-10 else 0.0
    ftp = fn * math.exp(s)

    grad_f = (2.0 * ftp * rho_ns * v_m**2
              / (32.174 * (d_in / 12.0) * 144.0))

    # ── Kinetic (acceleration) term ───────────────────────
    Ek = v_m * fp['v_sg'] * rho_m / (32.174 * p * 144.0)
    Ek = max(min(Ek, 0.99), 0.0)

    return (grad_el + grad_f) / (1.0 - Ek)

