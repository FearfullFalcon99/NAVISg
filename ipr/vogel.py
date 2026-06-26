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