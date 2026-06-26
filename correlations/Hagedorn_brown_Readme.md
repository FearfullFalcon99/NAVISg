# Hagedorn-Brown Pressure-Gradient Correlation

This module implements the **Modified Hagedorn-Brown (1965)** vertical two-phase pressure gradient correlation, augmented with the **Griffith-Wallis (1961)** bubble-flow correction. It is designed to compute the pressure gradient ($dp/dh$) at any point along a wellbore under multiphase flow conditions.



## Mathematical Formulation & Calculation Flow

The total vertical two-phase pressure gradient is expressed as the sum of three terms:

$$\frac{dp}{dh} = \left(\frac{dp}{dh}\right)_{\text{elevation}} + \left(\frac{dp}{dh}\right)_{\text{friction}} + \left(\frac{dp}{dh}\right)_{\text{acceleration}}$$

Which is evaluated in field units as:

$$\frac{dp}{dh} = \frac{\frac{\rho_m}{144} + \frac{2 f_{tp} \rho_{ns} v_m^2}{32.174 \, d_{\text{ft}} \, 144}}{1 - E_k}$$

where:
- $\rho_m = \rho_l E_l + \rho_g (1 - E_l)$ is the two-phase mixture density ($\text{lb/ft}^3$).
- $\rho_{ns} = \rho_l \lambda_l + \rho_g (1 - \lambda_l)$ is the no-slip mixture density ($\text{lb/ft}^3$).
- $E_l$ is the liquid holdup (in-situ liquid fraction).
- $\lambda_l = \frac{v_{sl}}{v_m}$ is the no-slip liquid volume fraction.
- $f_{tp}$ is the two-phase Darcy friction factor.
- $d_{\text{ft}}$ is the tubing inner diameter in feet ($d_{\text{in}} / 12$).
- $E_k$ is the dimensionless kinetic energy (acceleration) term:
  $$E_k = \frac{v_m v_{sg} \rho_m}{32.174 \, p \times 144}$$

### 1. Dimensionless Groups
The Hagedorn-Brown correlation uses four dimensionless groups to characterize fluid behaviour:
*   **Liquid Viscosity Number ($N_L$):**
    $$N_L = 0.15726 \cdot \mu_l \cdot \left(\frac{1}{\rho_l \sigma^3}\right)^{0.25}$$
*   **Liquid Velocity Number ($N_{Lv}$):**
    $$N_{Lv} = 1.938 \cdot v_{sl} \cdot \left(\frac{\rho_l}{\sigma}\right)^{0.25}$$
*   **Gas Velocity Number ($N_{gv}$):**
    $$N_{gv} = 1.938 \cdot v_{sg} \cdot \left(\frac{\rho_l}{\sigma}\right)^{0.25}$$
*   **Pipe Diameter Number ($N_d$):**
    $$N_d = 120.872 \cdot d_{\text{ft}} \cdot \sqrt{\frac{\rho_l}{\sigma}}$$

*Units:* $\mu_l$ in cP, $\rho_l$ in $\text{lb/ft}^3$, $\sigma$ in dynes/cm, velocities in ft/s, and $d_{\text{ft}}$ in ft.

### 2. Viscosity Correction Factor ($C_{Nl}$)
Calculated via a polynomial fit to the H-B viscosity correction curve:
$$C_{Nl} = 0.061 N_L^3 - 0.0929 N_L^2 + 0.0505 N_L + 0.0019$$
(constrained to a minimum of $10^{-6}$).

### 3. Base Holdup Chart Factor ($H_L / \psi$)
Determined as a function of the parameter $H$:
$$H = \frac{N_{Lv}}{N_{gv}^{0.575}} \left(\frac{p}{14.7}\right)^{0.1} \frac{C_{Nl}}{N_d}$$
A log-log digitization of **H-B Chart 3** is used to obtain $H_L / \psi = f(H)$.

### 4. Secondary Correction Factor ($\psi$)
Obtained as a function of parameter $B$:
$$B = \frac{N_{gv} N_{Lv}^{0.38}}{N_d^{2.14}}$$
Using a piecewise fit (from H-B Chart 4):
*   For $B \le 0.025$: $\psi = 27170 B^3 - 317.52 B^2 + 0.5472 B + 0.9999$
*   For $0.025 < B \le 0.055$: $\psi = -533.33 B^2 + 58.524 B + 0.1171$
*   For $B > 0.055$: $\psi = 2.5714 B + 1.5962$
(each branch is clamped to a minimum of 1.0).

The final Hagedorn-Brown liquid holdup is:
$$E_{l, \text{HB}} = \max\left(\frac{H_L}{\psi} \times \psi, \, \lambda_l\right)$$

---

## Key Improvements and Bug Fixes in This Version

This implementation fixes five critical bugs commonly found in legacy/textbook versions of the correlation:

1.  **Correct Bubble Flow Check Direction**
    *   **Legacy Bug:** The transition to bubble flow was checked incorrectly (e.g., using gas-to-liquid ratio checks going the wrong way).
    *   **Fix:** Uses the Griffith-Wallis criterion: bubble flow is active when the gas no-slip fraction is small ($\lambda_g < L_B$, where $L_B = 1.071 - 0.2218 \frac{v_m^2}{d_{\text{in}}}$ with a floor of $0.13$).
2.  **Standard Griffith Slip Velocity**
    *   **Legacy Bug:** Incorrect or variable slip velocity values used in the quadratic holdup equation.
    *   **Fix:** Uses the original Griffith (1961) constant slip velocity of $v_s = 0.8 \text{ ft/s}$.
3.  **Correct Two-Phase Friction Mixture Viscosity**
    *   **Legacy Bug:** Used the no-slip mixture viscosity $\mu_{ns}$ to compute the Reynolds number.
    *   **Fix:** Correctly computes the dynamic two-phase mixture viscosity as $\mu_m = \mu_l^{E_l} \cdot \mu_g^{1 - E_l}$, which matches the Hagedorn-Brown definition.
4.  **Smooth Flow Regime Transition**
    *   **Legacy Bug:** Sudden jumps between Griffith bubble flow and Hagedorn-Brown correlations caused numerical discontinuities in VLP curves, leading to non-convergence.
    *   **Fix:** Implements a linear blending zone near the transition boundary:
        *   $\lambda_g < 0.7 L_B$: Pure Griffith
        *   $\lambda_g \ge L_B$: Pure Hagedorn-Brown
        *   $0.7 L_B \le \lambda_g < L_B$: Linear blend of Griffith and Hagedorn-Brown holdups.
5.  **Accurate Chart 3 Digitization (`_holdup_over_psi`)**
    *   **Legacy Bug:** Used a rational-polynomial fit that artificially floored at $H_L / \psi = 0.217$ as $H \to 0$. This severely overpredicted mixture density and pressure drop in large tubing / low-velocity wells.
    *   **Fix:** Replaced with a log-log digitized lookup of H-B Chart 3, extending down to a floor of $\approx 0.03$, and anchored at $H = 7.12 \times 10^{-5} \to H_L / \psi = 0.44$ (validated against Takács Example 2-24).

## File and Function Structure

*   `_friction(Re, rough, d_in)`: Computes the Darcy friction factor. Uses $64/Re$ for laminar flow ($Re < 2100$) and Chen's (1979) explicit formula for turbulent flow.
*   `_CNl(Nl)`: Computes the liquid viscosity correction factor.
*   `_holdup_over_psi(H)`: Performs the digitized log-log lookup for the base holdup chart.
*   `_psi(B)`: Computes the secondary correction factor.
*   `_dim_groups(fp)`: Evaluates the four dimensionless numbers ($N_L$, $N_{Lv}$, $N_{gv}$, $N_d$).
*   `_griffith_holdup(fp)`: Computes the Griffith liquid holdup.
*   `_hb_holdup(fp)`: Computes the Hagedorn-Brown liquid holdup.
*   `_blended_holdup(fp)`: Determines the active flow regime (Griffith, H-B, or Transition) and returns the blended liquid holdup.
*   `pressure_gradient(fp, roughness)`: Main entry point. Combines elevation, friction, and acceleration terms to return the pressure gradient in **psi/ft** (positive downward).

---

## Fluid Properties Input (`fp`) Dictionary

The `pressure_gradient` function expects a dictionary `fp` containing properties at local $P$ and $T$:

| Key | Description | Units |
| :--- | :--- | :--- |
| `p` | Local Pressure | psia |
| `d_in` | Tubing Inside Diameter | inches |
| `rho_l` | Liquid Density | $\text{lb/ft}^3$ |
| `rho_g` | Gas Density | $\text{lb/ft}^3$ |
| `mu_l` | Liquid Viscosity | cP |
| `mu_g` | Gas Viscosity | cP |
| `sigma` | Liquid-Gas Surface Tension | dynes/cm |
| `v_sl` | Superficial Liquid Velocity | ft/s |
| `v_sg` | Superficial Gas Velocity | ft/s |
| `v_m` | Mixture superficial velocity ($v_{sl} + v_{sg}$) | ft/s |
| `lam_l` | No-slip liquid volume fraction ($v_{sl} / v_m$) | fraction |

---

## Validation

A simple verification script is provided in the root directory:
```bash
python validate_hb_example.py
```
This validates the pressure gradient calculation against reference wellbore conditions to ensure calculations align with engineering standards.
