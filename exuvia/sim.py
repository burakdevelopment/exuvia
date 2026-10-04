from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field

import numpy as np
from scipy.linalg import eig, solve
from scipy.special import erf

G = 9.81
R_AIR = 287.05
KB = 1.380649e-23
AMU = 1.66053907e-27
RHO_P = 3950.0
M_CLONO2 = 97.46 * AMU
EARTH_R = 6.371e6
AREA = 2 * np.pi * EARTH_R**2
YEAR = 365.25 * 86400.0
DAY = 86400.0
AL_TO_AL2O3 = 101.96 / (2 * 26.98)

Z_EDGES = np.arange(10.0, 92.5 + 1e-9, 2.5) * 1e3
Z = 0.5 * (Z_EDGES[1:] + Z_EDGES[:-1])
DZ = 2500.0
NZ = Z.size
R_EDGES = np.logspace(np.log10(1.4e-9), np.log10(2.8e-6), 9)
R_BIN = np.sqrt(R_EDGES[1:] * R_EDGES[:-1])
NB = R_BIN.size
OZONE_LAYER = (Z >= 15e3) & (Z <= 30e3)
LOWER_STRAT = (Z >= 10e3) & (Z <= 30e3)
TROPOSPHERE = Z < 12.5e3
T_GRID_YR = np.concatenate([np.linspace(0, 5, 251)[:-1], np.linspace(5, 80, 301)])


def temperature(zm):
    z = np.asarray(zm) / 1e3
    return np.select(
        [z < 11, z < 20, z < 32, z < 47, z < 51, z < 71, z < 86],
        [288.15 - 6.5 * z, 216.65 + 0 * z, 216.65 + (z - 20), 228.65 + 2.8 * (z - 32),
         270.65 + 0 * z, 270.65 - 2.8 * (z - 51), 214.65 - 2.0 * (z - 71)],
        186.87 + 0 * z)


def _density_profiles():
    zf = np.linspace(0.0, 95e3, 9501)
    tf = temperature(zf)
    lnp = np.log(101325.0) - np.concatenate(
        [[0.0], np.cumsum(G / (R_AIR * 0.5 * (tf[1:] + tf[:-1])) * np.diff(zf))])
    t_c, t_e = temperature(Z), temperature(Z_EDGES)
    rho_c = np.exp(np.interp(Z, zf, lnp)) / (R_AIR * t_c)
    rho_e = np.exp(np.interp(Z_EDGES, zf, lnp)) / (R_AIR * t_e)
    return t_c, rho_c, t_e, rho_e


T_C, RHO_C, T_E, RHO_E = _density_profiles()


def settling_velocity(r, t, rho):
    mu = 1.458e-6 * t**1.5 / (t + 110.4)
    cbar_air = np.sqrt(8 * R_AIR * t / np.pi)
    mfp = mu / (0.499 * rho * cbar_air)
    kn = mfp / r
    cc = 1.0 + kn * (1.257 + 0.4 * np.exp(-1.1 / kn))
    return 2.0 / 9.0 * RHO_P * G * r**2 * cc / mu


@dataclass
class Params:
    alumina_gg_per_yr: float | None = None
    al_ablated_gg_per_yr: float = 0.912
    oxide_fraction: float = 0.32
    r_med_nm: float = 10.0
    sigma_g: float = 1.6
    w_meso_mm_s: float = 2.0
    w_ustrat_mm_s: float = 0.6
    w_lstrat_mm_s: float = 0.15
    kzz_strat: float = 0.3
    kzz_top: float = 30.0
    tau_trop_days: float = 10.0
    tau_coat_days: float = 30.0
    p_sep: float = 0.5
    gamma_alu: float = 0.02
    theta_hcl: float = 0.5
    gamma_sulf: float = 1e-3
    s_bg_um2_cm3: float = 0.7
    transport: str = "circulation"
    coating: str = "kinetic"


def alumina_flux(p: Params) -> float:
    if p.alumina_gg_per_yr is not None:
        return p.alumina_gg_per_yr
    return p.al_ablated_gg_per_yr * p.oxide_fraction * AL_TO_AL2O3


def mass_fractions(r_med_nm: float, sigma_g: float) -> np.ndarray:
    ln_sg = np.log(max(sigma_g, 1.01))
    r_mm = r_med_nm * 1e-9 * np.exp(3 * ln_sg**2)
    cdf = 0.5 * (1 + erf((np.log(R_EDGES) - np.log(r_mm)) / (np.sqrt(2) * ln_sg)))
    f = np.diff(cdf)
    f[0] += cdf[0]
    f[-1] += 1 - cdf[-1]
    return f / f.sum()


def _w_down(p: Params, z):
    if p.transport == "sedimentation_only":
        return np.zeros_like(z)
    w = np.where(z > 50e3, p.w_meso_mm_s, np.where(z > 30e3, p.w_ustrat_mm_s, p.w_lstrat_mm_s))
    return w * 1e-3


def _kzz(p: Params, z):
    if p.transport == "sedimentation_only":
        return np.zeros_like(z)
    k = np.full_like(z, p.kzz_strat)
    hi = z > 50e3
    k[hi] = p.kzz_strat * np.exp(np.log(p.kzz_top / p.kzz_strat) * (z[hi] - 50e3) / 40e3)
    return k


def transport_matrix(p: Params, r: float) -> np.ndarray:
    v = _w_down(p, Z_EDGES) + settling_velocity(r, T_E, RHO_E)
    k = _kzz(p, Z_EDGES)
    m = np.zeros((NZ, NZ))
    for i in range(NZ):
        m[i, i] -= v[i] / DZ
        if i > 0:
            m[i - 1, i] += v[i] / DZ
    for i in range(NZ - 1):
        d = k[i + 1] * RHO_E[i + 1] / DZ**2
        m[i, i] -= d / RHO_C[i]
        m[i, i + 1] += d / RHO_C[i + 1]
        m[i + 1, i + 1] -= d / RHO_C[i + 1]
        m[i + 1, i] += d / RHO_C[i]
    m[TROPOSPHERE, TROPOSPHERE] -= 1.0 / (p.tau_trop_days * DAY)
    return m


def source_profile() -> np.ndarray:
    f = np.exp(-0.5 * ((Z - 75e3) / 6e3) ** 2)
    return f / f.sum()


def coating_rate(p: Params) -> np.ndarray:
    if p.coating == "none":
        return np.zeros(NZ)
    tau = 0.1 if p.coating == "instant" else p.tau_coat_days
    rate = np.full(NZ, 1.0 / (tau * DAY))
    rate[Z > 35e3] /= 30.0
    return rate


@dataclass
class Result:
    alumina_gg_per_yr: float
    burden_10_30km_gg: float
    burden_total_gg: float
    arrival_t10_yr: float
    arrival_t50_yr: float
    exposed_fraction_ozone_layer: float
    sad_added_20km_um2_cm3: float
    sad_exposed_20km_um2_cm3: float
    activation_ratio: float
    activation_bare_share: float
    runtime_ms: float
    profiles: dict = field(default_factory=dict)


def run(p: Params, keep_profiles: bool = False) -> Result:
    t0 = time.perf_counter()
    flux = alumina_flux(p) * 1e6 / YEAR
    src = source_profile() * flux / (AREA * DZ)
    fm = mass_fractions(p.r_med_nm, p.sigma_g)
    kc = coating_rate(p)

    bare = np.zeros((NB, NZ))
    coat = np.zeros((NB, NZ))
    b_oz_t = np.zeros_like(T_GRID_YR)
    for b in range(NB):
        if fm[b] < 1e-9:
            continue
        m = transport_matrix(p, R_BIN[b])
        s = src * fm[b]
        total = solve(-m, s)
        e = solve(-(m - np.diag(kc)), s)
        bare[b] = e
        coat[b] = np.clip(total - e, 0, None)
        lam, vec = eig(m)
        coef = solve(vec, total.astype(complex))
        w = vec[OZONE_LAYER].sum(axis=0) * coef
        b_oz_t += (total[OZONE_LAYER].sum()
                   - np.real(np.exp(np.outer(T_GRID_YR * YEAR, lam)) @ w))

    total_c = bare + coat
    to_gg = AREA * DZ / 1e6
    b_oz_ss = total_c[:, OZONE_LAYER].sum()
    frac = b_oz_t / b_oz_ss if b_oz_ss > 0 else b_oz_t
    t10 = float(np.interp(0.1, np.maximum.accumulate(frac), T_GRID_YR, right=np.inf))
    t50 = float(np.interp(0.5, np.maximum.accumulate(frac), T_GRID_YR, right=np.inf))

    s_bare = (3 * bare / (RHO_P * R_BIN[:, None])).sum(axis=0)
    s_coat = (3 * coat / (RHO_P * R_BIN[:, None])).sum(axis=0)
    s_bg = p.s_bg_um2_cm3 * 1e-6 * np.exp(-0.5 * ((Z - 20e3) / 6e3) ** 2)
    cbar = np.sqrt(8 * KB * T_C / (np.pi * M_CLONO2))
    weight = np.exp(-0.5 * ((Z - 25e3) / 5e3) ** 2)
    k_bare = 0.25 * cbar * p.gamma_alu * p.theta_hcl * s_bare
    k_coat = 0.25 * cbar * p.gamma_sulf * p.p_sep * s_coat
    k_bg = 0.25 * cbar * p.gamma_sulf * s_bg
    act_reentry = (weight * (k_bare + k_coat)).sum()
    act_bg = (weight * k_bg).sum()

    i20 = int(np.argmin(np.abs(Z - 20e3)))
    res = Result(
        alumina_gg_per_yr=alumina_flux(p),
        burden_10_30km_gg=float(total_c[:, LOWER_STRAT].sum() * to_gg),
        burden_total_gg=float(total_c.sum() * to_gg),
        arrival_t10_yr=t10,
        arrival_t50_yr=t50,
        exposed_fraction_ozone_layer=float(bare[:, OZONE_LAYER].sum() / max(b_oz_ss, 1e-300)),
        sad_added_20km_um2_cm3=float((s_bare[i20] + p.p_sep * s_coat[i20]) * 1e6),
        sad_exposed_20km_um2_cm3=float(s_bare[i20] * 1e6),
        activation_ratio=float(act_reentry / act_bg),
        activation_bare_share=float((weight * k_bare).sum() / max(act_reentry, 1e-300)),
        runtime_ms=(time.perf_counter() - t0) * 1e3,
    )
    if keep_profiles:
        res.profiles = {
            "z_km": (Z / 1e3).tolist(),
            "alumina_ug_m3": (total_c.sum(axis=0) * 1e9).tolist(),
            "bare_ug_m3": (bare.sum(axis=0) * 1e9).tolist(),
            "sad_bare_um2_cm3": (s_bare * 1e6).tolist(),
            "sad_coated_um2_cm3": (s_coat * 1e6).tolist(),
            "sad_background_um2_cm3": (s_bg * 1e6).tolist(),
            "t_yr": T_GRID_YR.tolist(),
            "ozone_layer_fill_fraction": frac.tolist(),
        }
    return res


def as_dict(r: Result) -> dict:
    return asdict(r)
