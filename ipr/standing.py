from __future__ import annotations

import numpy as np


def calculate_flow_efficiency(r_e: float, r_w: float, skin: float) -> float:
    if r_e <= 0 or r_w <= 0:
        raise ValueError(f"Radii must be positive. Got r_e={r_e}, r_w={r_w}.")

    ln_term = float(np.log(0.472 * r_e / r_w))
    denominator = ln_term + skin
    if np.isclose(denominator, 0.0):
        raise ValueError(
            "Denominator (ln_term + skin) is zero. Standing flow efficiency is undefined."
        )

    return float(ln_term / denominator)


def _modified_pwf(p_reference: float, pwf: float | np.ndarray, fe: float) -> float | np.ndarray:
    return p_reference - fe * (p_reference - pwf)


def _vogel_fraction(pwf_prime: float | np.ndarray, p_ref: float) -> float | np.ndarray:
    ratio = np.asarray(pwf_prime) / p_ref
    return 1.0 - 0.2 * ratio - 0.8 * ratio ** 2


def standing_ipr(
    Pr: float,
    Pwf_test: float,
    Qo_test: float,
    Pb: float,
    n_points: int = 100,
    fe_old: float | None = None,
    fe_new: float = 1.0,
    r_e: float | None = None,
    r_w: float | None = None,
    skin: float | None = None,
):
    if Pr <= 0:
        raise ValueError(f"Pr must be positive. Got Pr={Pr}.")
    if Pwf_test < 0:
        raise ValueError(f"Pwf_test cannot be negative. Got Pwf_test={Pwf_test}.")
    if Qo_test <= 0:
        raise ValueError(f"Qo_test must be positive. Got Qo_test={Qo_test}.")
    if n_points < 3:
        raise ValueError(f"n_points must be >= 3. Got {n_points}.")

    if fe_old is None:
        if r_e is not None and r_w is not None and skin is not None:
            fe_old = calculate_flow_efficiency(r_e, r_w, skin)
        else:
            fe_old = 1.0

    if fe_old <= 0:
        raise ValueError(f"fe_old must be positive. Got fe_old={fe_old}.")
    if fe_new <= 0:
        raise ValueError(f"fe_new must be positive. Got fe_new={fe_new}.")

    pb = Pb if Pb and Pb > 0 else Pr

    if Pr <= pb:
        pwf_prime_test = _modified_pwf(Pr, Pwf_test, fe_old)
        vogel_test = float(_vogel_fraction(pwf_prime_test, Pr))
        if np.isclose(vogel_test, 0.0):
            raise ValueError("Standing IPR cannot back-calculate qmax from the test point.")

        qmax_ideal = Qo_test / vogel_test

        if fe_new <= 1.0:
            pwf_min = 0.0
            pwf_prime_at_min = float(_modified_pwf(Pr, 0.0, fe_new))
            qmax_new = float(qmax_ideal * _vogel_fraction(pwf_prime_at_min, Pr))
        else:
            pwf_min = Pr * (1.0 - 1.0 / fe_new)
            qmax_new = float(qmax_ideal * (0.624 + 0.376 * fe_new))

        Pwf = np.linspace(Pr, pwf_min, n_points)
        Pwf_prime = np.maximum(_modified_pwf(Pr, Pwf, fe_new), 0.0)
        q = np.maximum(qmax_ideal * _vogel_fraction(Pwf_prime, Pr), 0.0)
        J = Qo_test / max(Pr - Pwf_test, 1e-9)

        return Pwf, q, float(qmax_new), float(J)

    if Pwf_test >= pb:
        denominator_j = Pr - Pwf_test
        if np.isclose(denominator_j, 0.0):
            raise ValueError("Cannot calculate Standing IPR: test Pwf equals Pr.")
        j_test = Qo_test / denominator_j
    else:
        pwf_prime_test = _modified_pwf(pb, Pwf_test, fe_old)
        vogel_term = float(_vogel_fraction(pwf_prime_test, pb))
        denominator_j = (Pr - pb) + (pb / 1.8) * vogel_term
        if np.isclose(denominator_j, 0.0):
            raise ValueError(
                "Cannot calculate Standing IPR: composite denominator is zero."
            )
        j_test = Qo_test / denominator_j

    j_new = j_test * (fe_new / fe_old)
    q_at_pb = j_new * (Pr - pb)
    qmax_vogel_ideal = j_new * pb / 1.8

    if fe_new <= 1.0:
        pwf_min_vogel = 0.0
        pwf_prime_at_min = float(_modified_pwf(pb, 0.0, fe_new))
        qmax_total = q_at_pb + qmax_vogel_ideal * float(_vogel_fraction(pwf_prime_at_min, pb))
    else:
        pwf_min_vogel = pb * (1.0 - 1.0 / fe_new)
        qmax_total = q_at_pb + qmax_vogel_ideal * (0.624 + 0.376 * fe_new)

    Pwf = np.linspace(Pr, pwf_min_vogel, n_points)
    q = np.empty_like(Pwf)

    for idx, pwf in enumerate(Pwf):
        if pwf >= pb:
            q[idx] = j_new * (Pr - pwf)
        else:
            pwf_prime = max(float(_modified_pwf(pb, pwf, fe_new)), 0.0)
            q[idx] = q_at_pb + qmax_vogel_ideal * float(_vogel_fraction(pwf_prime, pb))

    q = np.maximum(q, 0.0)
    return Pwf, q, float(qmax_total), float(j_new)