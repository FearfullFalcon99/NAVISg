# Reservoir Inflow Performance Relationship (ipr/vogel.py)

This module implements the **Vogel (1968)** Inflow Performance Relationship (IPR) for saturated reservoirs, along with its extension for undersaturated reservoirs. It is used to generate the well's inflow curve ($P_{wf}$ vs. $q_o$) and identify the static and maximum flow capabilities.

---

## Mathematical Formulation

The inflow performance relationship describes the oil production rate ($q_o$) as a function of flowing bottomhole pressure ($P_{wf}$). The model splits into two cases based on the relationship between average reservoir pressure ($P_r$) and the reservoir bubblepoint pressure ($P_b$).

---

### Case 1: Saturated Reservoir ($P_r \le P_b$)
When the reservoir pressure is below or equal to the bubblepoint pressure, two-phase gas-liquid flow exists throughout the reservoir drainage area. The relationship is governed entirely by Vogel's quadratic equation:

$$\frac{q_o}{Q_{\text{max}}} = 1 - 0.2 \left( \frac{P_{wf}}{P_r} \right) - 0.8 \left( \frac{P_{wf}}{P_r} \right)^2$$

1.  **Calculate $Q_{\text{max}}$**: Using a known well test point $(Q_{o,\text{test}}, P_{wf,\text{test}})$:
    $$Q_{\text{max}} = \frac{Q_{o,\text{test}}}{1 - 0.2 \left( \frac{P_{wf,\text{test}}}{P_r} \right) - 0.8 \left( \frac{P_{wf,\text{test}}}{P_r} \right)^2}$$
2.  **Generate Curve**: For any flowing bottomhole pressure $P_{wf}$:
    $$q_o(P_{wf}) = Q_{\text{max}} \left[ 1 - 0.2 \left( \frac{P_{wf}}{P_r} \right) - 0.8 \left( \frac{P_{wf}}{P_r} \right)^2 \right]$$

---

### Case 2: Undersaturated Reservoir ($P_r > P_b$)
When reservoir pressure is above the bubblepoint pressure, the reservoir is undersaturated. The inflow behavior is split into two regions:
1.  **Single-Phase Liquid Flow** ($P_{wf} \ge P_b$): Follows linear productivity index (PI) behavior.
2.  **Two-Phase Flow** ($P_{wf} < P_b$): Follows Vogel's quadratic behavior.

#### Step-by-Step Derivation and Calculations:
1.  **Pseudo-maximum flow rate ($Q_b$)**: Calculated by applying Vogel's equation to the test data:
    $$Q_b = \frac{Q_{o,\text{test}}}{1 - 0.2 \left( \frac{P_{wf,\text{test}}}{P_r} \right) - 0.8 \left( \frac{P_{wf,\text{test}}}{P_r} \right)^2}$$
2.  **Flow rate at bubblepoint ($q_b$)**:
    $$q_b = Q_b \left[ 1 - 0.2 \left( \frac{P_b}{P_r} \right) - 0.8 \left( \frac{P_b}{P_r} \right)^2 \right]$$
3.  **Productivity Index ($J$)**: The slope of the single-phase straight-line part:
    $$J = \frac{q_b}{P_r - P_b}$$
4.  **IPR Curve Construction**:
    *   For $P_{wf} \ge P_b$:
        $$q_o(P_{wf}) = J (P_r - P_{wf})$$
    *   For $P_{wf} < P_b$:
        $$q_o(P_{wf}) = Q_b \left[ 1 - 0.2 \left( \frac{P_{wf}}{P_r} \right) - 0.8 \left( \frac{P_{wf}}{P_r} \right)^2 \right]$$

This formulation guarantees mathematical continuity at the boundary ($P_{wf} = P_b$), where both equations yield $q_o = q_b$.

---

## Function Reference

### `vogel_ipr(Pr, Pwf_test, Qo_test, Pb, n_points=100)`

Computes the pressure and rate coordinates to plot the IPR curve.

#### Inputs:
*   `Pr`: Average reservoir pressure (psia)
*   `Pwf_test`: Flowing bottomhole pressure measured during a well test (psia)
*   `Qo_test`: Oil flow rate measured during the well test (STB/d)
*   `Pb`: Bubblepoint pressure of reservoir fluid (psia)
*   `n_points`: Number of discrete calculation steps (default = 100)

#### Returns:
*   `pressures` (`np.ndarray`): Array of $P_{wf}$ values from $0$ to $P_r$.
*   `rates` (`np.ndarray`): Calculated oil rates at each pressure point.
*   `Qmax` (`float`): Maximum theoretical flow rate at $P_{wf} = 0$.
*   `J` (`float` or `None`): Productivity Index above the bubblepoint (returns `None` if reservoir is saturated).

---

## Application Workflow Integration

```
User Input Test Data (Pr, Pb, Pwf_test, Qo_test)
                   │
                   ▼
            vogel_ipr(...)
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
Saturated (Pr <= Pb)      Undersaturated (Pr > Pb)
    │                             │
    ├─► Apply Vogel Eq          ├─► Above Pb: Linear PI Eq
    │   for all pressures         │   q = J * (Pr - Pwf)
    │                             │
    │                             ├─► Below Pb: Vogel Eq
    │                             │   q = Qb * (1 - 0.2*(Pwf/Pr) - 0.8*(Pwf/Pr)^2)
    ▼                             ▼
    └──────────────┬──────────────┘
                   ▼
     Return pressures, rates, Qmax, J
                   │
                   ▼
     Plot results on UI (X: q_o, Y: P_{wf})
```
