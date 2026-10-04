(function (root) {
  const G = 9.81, R_AIR = 287.05, KB = 1.380649e-23, AMU = 1.66053907e-27, RHO_P = 3950;
  const M_CLONO2 = 97.46 * AMU, AREA = 2 * Math.PI * 6.371e6 ** 2, YEAR = 365.25 * 86400, DAY = 86400;
  const AL_TO_AL2O3 = 101.96 / (2 * 26.98), DZ = 2500;

  const Z_EDGES = Array.from({ length: 34 }, (_, i) => (10 + 2.5 * i) * 1e3);
  const Z = Z_EDGES.slice(1).map((z, i) => 0.5 * (z + Z_EDGES[i]));
  const NZ = Z.length;
  const R_EDGES = Array.from({ length: 9 }, (_, i) => 10 ** (Math.log10(1.4e-9) + i * (Math.log10(2.8e-6) - Math.log10(1.4e-9)) / 8));
  const R_BIN = R_EDGES.slice(1).map((r, i) => Math.sqrt(r * R_EDGES[i]));
  const NB = R_BIN.length;
  const OZONE = Z.map(z => z >= 15e3 && z <= 30e3), LOWER = Z.map(z => z >= 10e3 && z <= 30e3), TROPO = Z.map(z => z < 12.5e3);

  function temperature(zm) {
    const z = zm / 1e3;
    if (z < 11) return 288.15 - 6.5 * z;
    if (z < 20) return 216.65;
    if (z < 32) return 216.65 + (z - 20);
    if (z < 47) return 228.65 + 2.8 * (z - 32);
    if (z < 51) return 270.65;
    if (z < 71) return 270.65 - 2.8 * (z - 51);
    if (z < 86) return 214.65 - 2.0 * (z - 71);
    return 186.87;
  }
  function interp(x, xs, ys) {
    let i = Math.min(Math.max(Math.floor(x / (xs[1] - xs[0])), 0), xs.length - 2);
    const t = (x - xs[i]) / (xs[i + 1] - xs[i]);
    return ys[i] + t * (ys[i + 1] - ys[i]);
  }
  const ZF = Array.from({ length: 9501 }, (_, i) => i * 10);
  const LNP = [Math.log(101325)];
  for (let i = 1; i < ZF.length; i++) {
    const tm = 0.5 * (temperature(ZF[i]) + temperature(ZF[i - 1]));
    LNP.push(LNP[i - 1] - G / (R_AIR * tm) * 10);
  }
  const T_C = Z.map(temperature), T_E = Z_EDGES.map(temperature);
  const RHO_C = Z.map((z, i) => Math.exp(interp(z, ZF, LNP)) / (R_AIR * T_C[i]));
  const RHO_E = Z_EDGES.map((z, i) => Math.exp(interp(z, ZF, LNP)) / (R_AIR * T_E[i]));

  function settling(r, t, rho) {
    const mu = 1.458e-6 * t ** 1.5 / (t + 110.4);
    const cbar = Math.sqrt(8 * R_AIR * t / Math.PI);
    const kn = mu / (0.499 * rho * cbar) / r;
    const cc = 1 + kn * (1.257 + 0.4 * Math.exp(-1.1 / kn));
    return 2 / 9 * RHO_P * G * r * r * cc / mu;
  }
  function erf(x) {
    const s = Math.sign(x); x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  function massFractions(rMedNm, sigmaG) {
    const ln = Math.log(Math.max(sigmaG, 1.01)), rmm = rMedNm * 1e-9 * Math.exp(3 * ln * ln);
    const cdf = R_EDGES.map(r => 0.5 * (1 + erf((Math.log(r) - Math.log(rmm)) / (Math.SQRT2 * ln))));
    const f = cdf.slice(1).map((c, i) => c - cdf[i]);
    f[0] += cdf[0]; f[NB - 1] += 1 - cdf[cdf.length - 1];
    const s = f.reduce((a, b) => a + b, 0);
    return f.map(v => v / s);
  }

  const DEFAULTS = {
    alumina_gg_per_yr: null, al_ablated_gg_per_yr: 0.912, oxide_fraction: 0.32, r_med_nm: 10, sigma_g: 1.6,
    w_meso_mm_s: 2.0, w_ustrat_mm_s: 0.6, w_lstrat_mm_s: 0.15, kzz_strat: 0.3, kzz_top: 30, tau_trop_days: 10,
    tau_coat_days: 30, p_sep: 0.5, gamma_alu: 0.02, theta_hcl: 0.5, gamma_sulf: 1e-3, s_bg_um2_cm3: 0.7,
    transport: 'circulation', coating: 'kinetic',
  };
  const flux = p => p.alumina_gg_per_yr != null ? p.alumina_gg_per_yr : p.al_ablated_gg_per_yr * p.oxide_fraction * AL_TO_AL2O3;
  function wDown(p, z) {
    if (p.transport === 'sedimentation_only') return 0;
    return 1e-3 * (z > 50e3 ? p.w_meso_mm_s : z > 30e3 ? p.w_ustrat_mm_s : p.w_lstrat_mm_s);
  }
  function kzz(p, z) {
    if (p.transport === 'sedimentation_only') return 0;
    return z > 50e3 ? p.kzz_strat * Math.exp(Math.log(p.kzz_top / p.kzz_strat) * (z - 50e3) / 40e3) : p.kzz_strat;
  }
  function transportMatrix(p, r) {
    const m = Array.from({ length: NZ }, () => new Float64Array(NZ));
    const v = Z_EDGES.map((z, i) => wDown(p, z) + settling(r, T_E[i], RHO_E[i]));
    for (let i = 0; i < NZ; i++) { m[i][i] -= v[i] / DZ; if (i > 0) m[i - 1][i] += v[i] / DZ; }
    for (let i = 0; i < NZ - 1; i++) {
      const d = kzz(p, Z_EDGES[i + 1]) * RHO_E[i + 1] / (DZ * DZ);
      m[i][i] -= d / RHO_C[i]; m[i][i + 1] += d / RHO_C[i + 1];
      m[i + 1][i + 1] -= d / RHO_C[i + 1]; m[i + 1][i] += d / RHO_C[i];
    }
    for (let i = 0; i < NZ; i++) if (TROPO[i]) m[i][i] -= 1 / (p.tau_trop_days * DAY);
    return m;
  }
  function lu(a) {
    const n = a.length, A = a.map(r => Float64Array.from(r)), piv = Array.from({ length: n }, (_, i) => i);
    for (let k = 0; k < n; k++) {
      let p = k; for (let i = k + 1; i < n; i++) if (Math.abs(A[i][k]) > Math.abs(A[p][k])) p = i;
      [A[k], A[p]] = [A[p], A[k]]; [piv[k], piv[p]] = [piv[p], piv[k]];
      for (let i = k + 1; i < n; i++) { const f = (A[i][k] /= A[k][k]); for (let j = k + 1; j < n; j++) A[i][j] -= f * A[k][j]; }
    }
    return { A, piv };
  }
  function luSolve({ A, piv }, b) {
    const n = A.length, x = piv.map(i => b[i]);
    for (let i = 0; i < n; i++) for (let j = 0; j < i; j++) x[i] -= A[i][j] * x[j];
    for (let i = n - 1; i >= 0; i--) { for (let j = i + 1; j < n; j++) x[i] -= A[i][j] * x[j]; x[i] /= A[i][i]; }
    return x;
  }
  const neg = m => m.map(r => r.map(v => -v));
  const shifted = (m, dt) => m.map((r, i) => r.map((v, j) => (i === j ? 1 : 0) - dt * v));

  function run(params) {
    const p = Object.assign({}, DEFAULTS, params);
    const fl = flux(p) * 1e6 / YEAR;
    const prof = Z.map(z => Math.exp(-0.5 * ((z - 75e3) / 6e3) ** 2));
    const ps = prof.reduce((a, b) => a + b, 0);
    const src = prof.map(v => v / ps * fl / (AREA * DZ));
    const fm = massFractions(p.r_med_nm, p.sigma_g);
    const tau = p.coating === 'instant' ? 0.1 : p.tau_coat_days;
    const kc = Z.map(z => p.coating === 'none' ? 0 : (1 / (tau * DAY)) / (z > 35e3 ? 30 : 1));

    const tGrid = [], dts = [];
    for (let t = 0; t < 5 - 1e-9; t += 5 / 365) tGrid.push(t);
    for (let t = 5; t <= 80 + 1e-9; t += 0.125) tGrid.push(t);
    for (let i = 1; i < tGrid.length; i++) dts.push((tGrid[i] - tGrid[i - 1]) * YEAR);

    const bare = [], coat = [], bOz = new Float64Array(tGrid.length);
    for (let b = 0; b < NB; b++) {
      if (fm[b] < 1e-9) { bare.push(new Array(NZ).fill(0)); coat.push(new Array(NZ).fill(0)); continue; }
      const m = transportMatrix(p, R_BIN[b]);
      const s = src.map(v => v * fm[b]);
      const total = luSolve(lu(neg(m)), s);
      const e = luSolve(lu(neg(m.map((r, i) => r.map((v, j) => v - (i === j ? kc[i] : 0))))), s);
      bare.push(e); coat.push(total.map((v, i) => Math.max(v - e[i], 0)));
      const facs = {}; let c = new Array(NZ).fill(0);
      for (let k = 1; k < tGrid.length; k++) {
        const dt = dts[k - 1], key = dt.toFixed(0);
        if (!facs[key]) facs[key] = lu(shifted(m, dt));
        c = luSolve(facs[key], c.map((v, i) => v + dt * s[i]));
        let oz = 0; for (let i = 0; i < NZ; i++) if (OZONE[i]) oz += c[i];
        bOz[k] += oz;
      }
    }
    const sum = (arr, mask) => arr.reduce((a, v, i) => a + (mask[i] ? v : 0), 0);
    const totalC = Z.map((_, i) => bare.reduce((a, r) => a + r[i], 0) + coat.reduce((a, r) => a + r[i], 0));
    const bareC = Z.map((_, i) => bare.reduce((a, r) => a + r[i], 0));
    const toGg = AREA * DZ / 1e6, bOzSS = sum(totalC, OZONE);
    const frac = Array.from(bOz, v => v / bOzSS);
    let run_ = 0; const mono = frac.map(v => (run_ = Math.max(run_, v)));
    const cross = q => { for (let i = 1; i < mono.length; i++) if (mono[i] >= q) return tGrid[i - 1] + (q - mono[i - 1]) / (mono[i] - mono[i - 1]) * (tGrid[i] - tGrid[i - 1]); return Infinity; };

    const sBare = Z.map((_, i) => bare.reduce((a, r, b) => a + 3 * r[i] / (RHO_P * R_BIN[b]), 0));
    const sCoat = Z.map((_, i) => coat.reduce((a, r, b) => a + 3 * r[i] / (RHO_P * R_BIN[b]), 0));
    const sBg = Z.map(z => p.s_bg_um2_cm3 * 1e-6 * Math.exp(-0.5 * ((z - 20e3) / 6e3) ** 2));
    let actR = 0, actBg = 0, actBare = 0;
    Z.forEach((z, i) => {
      const cbar = Math.sqrt(8 * KB * T_C[i] / (Math.PI * M_CLONO2)), w = Math.exp(-0.5 * ((z - 25e3) / 5e3) ** 2);
      const kb = 0.25 * cbar * p.gamma_alu * p.theta_hcl * sBare[i], kcoat = 0.25 * cbar * p.gamma_sulf * p.p_sep * sCoat[i];
      actR += w * (kb + kcoat); actBare += w * kb; actBg += w * 0.25 * cbar * p.gamma_sulf * sBg[i];
    });
    const i20 = Z.reduce((bi, z, i) => Math.abs(z - 20e3) < Math.abs(Z[bi] - 20e3) ? i : bi, 0);
    return {
      alumina_gg_per_yr: flux(p),
      burden_10_30km_gg: sum(totalC, LOWER) * toGg, burden_total_gg: totalC.reduce((a, b) => a + b, 0) * toGg,
      arrival_t10_yr: cross(0.1), arrival_t50_yr: cross(0.5),
      exposed_fraction_ozone_layer: sum(bareC, OZONE) / bOzSS,
      sad_added_20km_um2_cm3: (sBare[i20] + p.p_sep * sCoat[i20]) * 1e6,
      activation_ratio: actR / actBg, activation_bare_share: actBare / Math.max(actR, 1e-300),
      profiles: { z_km: Z.map(z => z / 1e3), alumina_ug_m3: totalC.map(v => v * 1e9), bare_ug_m3: bareC.map(v => v * 1e9),
                  sad_bare: sBare.map(v => v * 1e6), sad_coated: sCoat.map(v => v * 1e6), sad_bg: sBg.map(v => v * 1e6),
                  t_yr: tGrid, fill: frac },
    };
  }
  const api = { run, DEFAULTS };
  if (typeof module !== 'undefined') module.exports = api; else root.ExuviaSim = api;
})(this);
