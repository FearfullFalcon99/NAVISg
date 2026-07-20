import numpy as np


def vogel_ipr(Pr, Pwf_test, Qo_test, Pb, n_points=100):

    pressures = np.linspace(0, Pr, n_points)

    rates = []

    # Saturated reservoir
    if Pr <= Pb:

        Qmax = Qo_test / (
            1
            - 0.2*(Pwf_test/Pr)
            - 0.8*(Pwf_test/Pr)**2
        )

        J = None

        for Pwf in pressures:

            q = Qmax * (
                1
                - 0.2*(Pwf/Pr)
                - 0.8*(Pwf/Pr)**2
            )

            rates.append(max(q, 0))

    # Undersaturated reservoir
    else:

        Qb = Qo_test / (
            1
            - 0.2*(Pwf_test/Pr)
            - 0.8*(Pwf_test/Pr)**2
        )

        qb = Qb * (
            1
            - 0.2*(Pb/Pr)
            - 0.8*(Pb/Pr)**2
        )

        J = qb / (Pr - Pb)

        Qmax = Qb

        for Pwf in pressures:

            if Pwf >= Pb:

                q = J * (Pr - Pwf)

            else:

                q = Qmax * (
                    1
                    - 0.2*(Pwf/Pr)
                    - 0.8*(Pwf/Pr)**2
                )

            rates.append(max(q, 0))

    return np.array(pressures), np.array(rates), Qmax, J

def vogel_future_ipr(Pr_p, Pwf_test, Qo_test, Pb, Pr_f, method=1, n_points=100):
    """
    Computes the Future IPR curve using Vogel's future approximations.
    method=1: First Approximation (Vogel)
    method=2: Second Approximation (Fetkovich)
    """
    # Step 1: Calculate current Qmax_p utilizing existing vogel logic
    _, _, Qmax_p, _ = vogel_ipr(Pr_p, Pwf_test, Qo_test, Pb, n_points)
    
    # Step 2: Calculate future Qmax_f based on selected approximation method
    if method == 1:
        Qmax_f = Qmax_p * (Pr_f / Pr_p) * (0.2 + 0.8 * (Pr_f / Pr_p))
    elif method == 2:
        Qmax_f = Qmax_p * (Pr_f / Pr_p)**3.0
    else:
        Qmax_f = Qmax_p
        
    pressures = np.linspace(0, Pr_f, n_points)
    rates = []
    
    # Step 3: Generate future IPR data string using Vogel's dimension equation
    for Pwf in pressures:
        q = Qmax_f * (1 - 0.2 * (Pwf / Pr_f) - 0.8 * (Pwf / Pr_f)**2)
        rates.append(max(q, 0))
        
    return np.array(pressures), np.array(rates), Qmax_f, None