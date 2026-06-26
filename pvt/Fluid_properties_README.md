# Fluid PVT Properties (pvt/fluid_properties.py)

This module implements PVT (Pressure-Volume-Temperature) correlations and physical property calculations for oil, gas, water, and their mixtures. It is used to compute in-situ fluid behavior, properties, and flow parameters at any specific pressure and temperature point in the wellbore.

---

## Mathematical Formulations and Correlations

The module relies on classical petroleum industry empirical correlations to calculate fluid properties.

### 1. Gas Properties
Gas calculations require the pseudocritical properties of the gas based on gas specific gravity ($\gamma_g$):
*   **Pseudocritical Pressure ($P_{pc}$)** and **Temperature ($T_{pc}$)**:
    $$P_{pc} = 709.604 - 58.718 \gamma_g$$
    $$T_{pc} = 170.491 + 307.344 \gamma_g$$
*   **Gas Compressibility Factor ($Z$)**:
    $$Z = 1.0 - \frac{3.52 P_{pr}}{10^{0.9813 T_{pr}}} + \frac{0.274 P_{pr}^2}{10^{0.8157 T_{pr}}}$$
    where pseudo-reduced pressure $P_{pr} = P / P_{pc}$ and pseudo-reduced temperature $T_{pr} = (T + 460) / T_{pc}$. (Bounded to a minimum of 0.05).
*   **Gas Density ($\rho_g$)**:
    $$\rho_g = \frac{2.7 \gamma_g P}{Z (T + 460)}$$
*   **Gas Viscosity ($\mu_g$)**: Calculated using the Carr-Kobayashi-Burrows correlation:
    $$\mu_g = 10^{-4} K e^{X \rho_g^y}$$
    where $K$, $X$, and $y$ are functions of gas molecular weight and temperature.
*   **Gas Formation Volume Factor ($B_g$)**:
    $$B_g = \frac{0.00504 Z (T + 460)}{P}$$

---

### 2. Oil Properties (Standing 1947 Correlations)
*   **Solution Gas-Oil Ratio ($R_s$)**:
    $$R_s = \gamma_g \left[ \frac{P / 18.2 + 1.4}{10^y} \right]^{1.205}$$
    where $y = 0.00091 T - 0.0125 \text{API}$
*   **Bubblepoint Pressure ($P_b$)**:
    $$P_b = 18.2 \left[ \left(\frac{R_s}{\gamma_g}\right)^{0.83} 10^y - 1.4 \right]$$
*   **Oil Formation Volume Factor ($B_o$)**:
    $$B_o = 0.972 + 0.000147 F^{1.175}$$
    where $F = R_s \left(\frac{\gamma_g}{\gamma_o}\right)^{0.5} + 1.25 T$

---

### 3. Oil Viscosity (Beggs-Robinson 1975 Correlation)
*   **Dead Oil Viscosity ($\mu_{od}$)**:
    $$\mu_{od} = 10^X - 1.0$$
    where $X = T^{-1.163} e^{6.9824 - 0.04658 \text{API}}$
*   **Live Oil Viscosity ($\mu_o$)**:
    $$\mu_o = A \mu_{od}^b$$
    where:
    $$A = 10^{R_s (2.2 \times 10^{-7} R_s - 7.4 \times 10^{-4})}$$
    $$b = \frac{0.68}{10^{8.62 \times 10^{-5} R_s}} + \frac{0.25}{10^{1.1 \times 10^{-3} R_s}} + \frac{0.062}{10^{3.74 \times 10^{-3} R_s}}$$

---

### 4. Surface Tension
*   **Oil-Gas Surface Tension ($\sigma$)**:
    $$\sigma = \sigma_{\text{dead}} e^{-0.00255 P^{0.56}}$$
    where dead oil surface tension is $\sigma_{\text{dead}} = \max(39.0 - 0.2571 \text{API}, 1.0)$.

---

### 5. Multi-Phase In-Situ Calculations
To feed the wellbore pressure drop correlations (e.g., Hagedorn-Brown), the module converts surface rates ($q_o, q_w, q_g$) to in-situ rates and velocities at local pressure $P$ and temperature $T$:
*   **In-situ liquid rates**:
    $$q_{o,is} = \frac{q_o B_o \times 5.615}{86400}$$
    $$q_{w,is} = \frac{q_w \times 5.615}{86400}$$
*   **In-situ free gas rate**:
    $$q_{g,is} = \frac{(q_g - R_s q_o) B_g \times 5.615}{86400}$$
*   **Superficial and Mixture Velocities**:
    $$v_{sl} = \frac{q_{o,is} + q_{w,is}}{A_{\text{pipe}}}, \quad v_{sg} = \frac{q_{g,is}}{A_{\text{pipe}}}, \quad v_m = v_{sl} + v_{sg}$$
*   **Mixture density ($\rho_l$) and viscosity ($\mu_l$)**:
    $$\rho_l = \rho_o(1 - f_w) + \rho_w f_w$$
    $$\mu_l = \mu_o(1 - f_w) + \mu_w f_w$$
    where water cut $f_w = \frac{q_w}{q_o + q_w}$.

---

## Function Reference

### `fluid_properties_at_PT(...)`
Computes all fluid physical and flow properties at a given pressure and temperature point.

#### Inputs:
*   `p` (float): Pressure (psia)
*   `T` (float): Temperature (°F)
*   `q_o` (float): Surface oil flow rate (STB/d)
*   `q_w` (float): Surface water flow rate (STB/d)
*   `q_g_surface` (float): Surface gas flow rate (Mscf/d)
*   `gas_sg` (float): Gas specific gravity (air = 1.0)
*   `oil_api` (float): Oil API gravity
*   `water_sg` (float): Water specific gravity
*   `d_in` (float): Tubing inside diameter (inches)
*   `Rs_surface` (float): Producing Gas-Oil Ratio at surface (scf/STB)

#### Returns:
Returns a dictionary `fp` containing:
*   `p`, `T`: Pressure and temperature.
*   `pb`: Bubblepoint pressure (psia).
*   `Rs`: In-situ solution gas-oil ratio (scf/STB).
*   `Bo`: Oil formation volume factor (bbl/STB).
*   `rho_l`, `rho_g`: In-situ liquid and gas density ($lb/ft^3$).
*   `mu_l`, `mu_g`: In-situ liquid and gas viscosity (cP).
*   `sigma`: Surface tension (dynes/cm).
*   `v_sl`, `v_sg`, `v_m`: Superficial liquid, superficial gas, and mixture velocities (ft/s).
*   `lam_l`: Input liquid fraction ($\lambda_l = v_{sl} / v_m$).
*   `A`: Pipe cross-sectional area ($ft^2$).
*   `d_in`: Tubing internal diameter (inches).
