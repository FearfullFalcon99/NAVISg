import numpy as np

from engine.traverse import compute_vlp_curve


def test_compute_vlp_curve_accepts_zero_whp():
    rates, bhps = compute_vlp_curve(
        whp=0,
        well_depth=6000,
        T_surf=100,
        T_bh=200,
        wor=0.5,
        gor=500,
        gas_sg=0.65,
        oil_api=35,
        water_sg=1.07,
        tubing_id=2.441,
        roughness=0.0006,
        rate_min=20,
        rate_max=5000,
        n_rates=10,
        vlp_model='Hagedorn-Brown',
        inclination_deg=90.0,
        pvt_correlation='Standing',
        T_sep=120.0,
        P_sep=114.7,
    )

    assert rates.shape == (10,)
    assert bhps.shape == (10,)
    assert np.isfinite(bhps).all()
    assert np.all(bhps > 0)
