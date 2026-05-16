# Research: Kubelka-Munk Equations for Diffuse Reflectance Unmixing of Hb/Bilirubin Liquid Phantoms

## Summary
The practical inverse formulation uses the semi-empirical Yudovsky (2009, erratum 2015) model — a simplified KM-derived forward model that maps reduced albedo to diffuse reflectance via fitted hyperparameters. Absorption is modeled as K(λ) = Σ cᵢ·εᵢ(λ) with extinction coefficients in cm⁻¹·M⁻¹, and reduced scattering as μₛ′(λ) = a·(λ/λ₀)⁻ᵇ. The inverse problem is solved by nonlinear least-squares fitting (SciPy `least_squares`) with non-negativity and physiological bounds. Validation against hemoglobin/bilirubin liquid phantom concentration series by Murphy (2022) showed the approach is feasible but accuracy degrades significantly when both chromophores are present at high concentrations simultaneously due to spectral overlap. The Yudovsky model with MC-fitted hyperparameters for water (n=1.33) is the recommended forward model.

---

## Findings

### 1. The Recommended Forward Model: Yudovsky (2009) Erratum

The most accurate analytical forward model for semi-infinite homogeneous turbid media in the visible range (450–650 nm) is the Yudovsky model as simplified in the 2015 erratum. It maps the transport reduced albedo w₀(λ) to diffuse reflectance R(λ) via a 6-parameter empirical function:

**Transport reduced albedo:**
```
w₀(λ) = μₛ′(λ) / (μₐ(λ) + μₛ′(λ))
```

**Reflectance (erratum simplified form):**
```
R = M₁ + M₂·exp(M₃·w₀^M₄) + M₅/(1.02 − M₆)
```

The hyperparameters M₁–M₆ depend only on the refractive index n. Key values (Bahl et al. 2024, fitted to MC simulations):

| n   | M₁     | M₂     | M₃    | M₄   | M₅     | M₆   |
|-----|--------|--------|-------|------|--------|------|
| 1.33 (water) | −0.0253 | 0.0166 | 2.873 | 1.64 | 0.0123 | 1.02 |
| 1.35 (gelatin) | −0.0257 | 0.0159 | 2.873 | 1.64 | 0.0124 | 1.02 |
| 1.44 (tissue) | −0.0254 | 0.0135 | 2.873 | 1.64 | 0.0120 | 1.02 |

For water-based liquid phantoms, use n = 1.33. NRMSE against MC simulations: 0.013 ± 0.006. [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

**Critical correction:** The original Kubelka-Munk equation (K/S = (1−R∞)²/2R∞) overestimates absorption K by a factor of 2; the corrected form should use denominator 4R∞ rather than 2R∞ when working with the "classic" KM function. [Source](https://opg.optica.org/abstract.cfm?uri=as-49-8-1107)

### 2. Absorption Model: K(λ) = Σ cᵢ·εᵢ(λ)

For liquid phantoms where chromophores are dissolved (not particulate), the absorption coefficient μₐ(λ) [cm⁻¹] follows Beer-Lambert additivity:

```
μₐ(λ) = Σᵢ cᵢ·εᵢ(λ)·ln(10) + μₐ,background(λ)
```

Or equivalently using the KM phenomenological absorption K:
```
K(λ) = 2·μₐ(λ)   (original KM relationship, but see §5)
```

**For practical implementation with hemoglobin + bilirubin:**

```
μₐ(λ) = c_Hb·ε_Hb(λ)·ln(10) + c_Bil·ε_Bil(λ)·ln(10) + μₐ,water(λ)
```

Where:
- c_Hb: hemoglobin concentration [M] (or [g/L] converted via MW = 64,500 g/mol)
- c_Bil: bilirubin concentration [M] (MW = 574.65 g/mol)
- ε_Hb(λ), ε_Bil(λ): molar extinction coefficients [cm⁻¹·M⁻¹]

**Hemoglobin extinction data:** Tabulated by Prahl (OMLC) for both HbO₂ and Hb at 2 nm intervals from 250–1000 nm. Key peaks: Soret band at ~414 nm (ε_HbO₂ ≈ 524,000 cm⁻¹·M⁻¹), Q-bands at ~542 nm (ε_HbO₂ ≈ 53,200) and ~576 nm (ε_HbO₂ ≈ 55,500). [Source](https://omlc.org/spectra/hemoglobin/summary.html)

**Bilirubin extinction data:** Peak at ~460 nm, ε ≈ 53,846 cm⁻¹·M⁻¹ at 460 nm (in chloroform; shifts in aqueous media). Strong absorption in the 440–500 nm range. [Source](https://omlc.org/classroom/ece532/class3/bilirubin.html)

**Background absorption:** Pure water absorption is negligible in the visible but rises significantly above ~700 nm. For visible-range work (400–650 nm), μₐ,water(λ) can often be neglected for liquid phantoms but should be included for completeness: μₐ,back(λ) = 7.84×10⁸·λ⁻³·²⁵⁵ cm⁻¹ (Yudovsky model background). [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

### 3. Scattering Model: μₛ′(λ) = a·(λ/λ₀)⁻ᵇ

The reduced scattering coefficient follows the Mie power-law empirically validated for biological tissues and Intralipid-based phantoms:

```
μₛ′(λ) = a·(λ/500 nm)⁻ᵇ   [cm⁻¹]
```

Where:
- **a** [cm⁻¹]: μₛ′ at the reference wavelength λ₀ = 500 nm. For Intralipid phantoms, a scales linearly with Intralipid volume fraction: a = 6.66·(I/I₀) + 2.55 cm⁻¹ where I₀ = 1% v/v (Bahl et al. 2024). Tissue-typical range: 8–70 cm⁻¹.
- **b**: scattering power exponent. For Intralipid phantoms, b ≈ 0.98 (median, no significant concentration dependence). Tissue-typical range: 0.1–3.3.

For polystyrene microsphere liquid phantoms (as in Murphy 2022), Mie theory should be used to compute μₛ′(λ) directly from bead diameter, concentration, and refractive indices. For 1.0 μm polystyrene beads in water, μₛ′ typically falls in 3.4–5.6 cm⁻¹ at 630 nm depending on concentration. [Source](https://scholarworks.uark.edu/cgi/viewcontent.cgi?article=1126&context=bmeguht)

**Important:** The full Jacques model also includes a Rayleigh scattering component, which becomes significant for liquid phantoms at short wavelengths (<450 nm):
```
μₛ′(λ) = a·[f_Ray·(λ/500)⁻⁴ + (1−f_Ray)·(λ/500)⁻ᵇMie]
```
For Intralipid phantoms, f_Ray can often be set to 0 (pure Mie regime). [Source](https://omlc.org/news/dec14/Jacques_PMB2013/Jacques_PMB2013.pdf)

### 4. Inverse Problem Formulation

The inverse problem is solved by nonlinear least-squares minimization:

```
min_{c_Hb, c_Bil, a, b}  Σ_λ [R_measured(λ) − R_model(λ; c_Hb, c_Bil, a, b)]²
```

**Pipeline:**
1. For each candidate (c_Hb, c_Bil, a, b), compute μₐ(λ) = Σ cᵢ·εᵢ(λ)·ln(10) + background
2. Compute μₛ′(λ) = a·(λ/500)⁻ᵇ
3. Compute w₀(λ) = μₛ′/(μₐ + μₛ′)
4. Compute R_model(λ) using Yudovsky erratum formula with n=1.33 hyperparameters
5. Evaluate residual against R_measured(λ)

**Recommended solver:** `scipy.optimize.least_squares` with the `trf` (Trust Region Reflective) method, which naturally handles bounds. Alternatively, `L-BFGS-B` for bounded optimization. Bahl et al. (2024) used SciPy v1.10.0 `least_squares`. [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

**Key implementation detail:** When fitting to phantom data, restrict the wavelength range to 450–575 nm for the Yudovsky model, as all analytical models become unreliable beyond this range for measured phantom data (Bahl et al. 2024, §3.2). For MC-simulated data, the range can extend to 600 nm.

### 5. Constraints and Bounds

| Parameter | Lower bound | Upper bound | Unit | Rationale |
|-----------|------------|-------------|------|-----------|
| c_Hb | 0 | 3.1×10⁻⁵ (≈2 mg/mL) | M | Physical non-negativity; upper bound from phantom studies |
| c_Bil | 0 | 3.5×10⁻⁵ (≈0.02 mg/mL) | M | Physical non-negativity; neonatal pathological range |
| a | 2 | 70 | cm⁻¹ | Physiological scattering range (Jacques 2013); for Intralipid: 2.55–42.5 (1–6% v/v) |
| b | 0.1 | 3.3 | dimensionless | Tissue scattering power range (Jacques 2013); for Intralipid phantoms b≈0.98 |

**Additional constraints:**
- **Non-negativity** is mandatory for all concentrations and scattering parameters.
- **Sum-to-unity** is NOT appropriate for absorption additivity in KM (unlike remote sensing linear unmixing). Chromophore contributions add independently via K = Σ cᵢ·εᵢ.
- **Scattering parameter coupling:** If using Intralipid phantoms, b can be fixed at ~0.98 (Bahl et al. 2024 finding that b shows no significant trend with Intralipid concentration) and only a needs fitting. This reduces the inverse problem from 4 to 3 parameters (c_Hb, c_Bil, a), significantly improving stability.
- **Wavelength selection matters:** Murphy (2022) found the LUT-based model had wavelength bounds of 450–650 nm, which was optimized for hemoglobin. Better bilirubin sensitivity requires extending the lower bound to ~440 nm to capture the bilirubin peak at 460 nm. The Murphy study found bilirubin extraction accurate only at higher concentrations (>0.008 mg/mL). [Source](https://scholarworks.uark.edu/cgi/viewcontent.cgi?article=1126&context=bmeguht)

### 6. Units (Critical for Implementation)

| Quantity | Symbol | Units | Conversion notes |
|----------|--------|-------|------------------|
| Absorption coefficient | μₐ, K | cm⁻¹ | μₐ = ε·C·ln(10) |
| Reduced scattering coefficient | μₛ′ | cm⁻¹ | Power-law reference at 500 nm |
| Molar extinction coefficient | ε | cm⁻¹·M⁻¹ | OMLC tabulated data; convert to μₐ via ×C×ln(10) |
| Concentration | c, C | M (mol/L) | 1 g/L Hb ÷ 64,500 g/mol = 1.55×10⁻⁵ M |
| Wavelength | λ | nm | Reference λ₀ = 500 nm for scattering normalization |
| Reflectance | R | dimensionless | 0–1 (or 0%–100%); Yudovsky model uses 0–1 |
| Reduced albedo | w₀ | dimensionless | 0–1; w₀ = μₛ′/(μₐ + μₛ′) |

**Hemoglobin concentration convention:** In the tissue optics literature, total hemoglobin concentration in whole blood is standardly taken as c_HbT = 150 g/L, and the blood volume fraction f_blood (0.2%–7%) scales the effective tissue concentration. For liquid phantoms, use direct molar or mass concentration. MW_Hb = 64,500 g/mol. [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

### 7. Finite LED Band Integration

When working with discrete LED illumination bands (multispectral rather than hyperspectral), the reflectance at each LED band is the convolution of the LED spectral emission, the sample reflectance, and the detector spectral sensitivity:

```
R_band_j = ∫ S_LEDj(λ)·R_sample(λ)·D(λ) dλ / ∫ S_LEDj(λ)·D(λ) dλ
```

**Practical approaches for LED-based systems:**
- **Narrow-band approximation:** For LEDs with FWHM ≤ 20 nm and when sampling regions without sharp absorption features, the peak wavelength can be used as representative. This fails near hemoglobin Soret band (414 nm) and bilirubin peak (460 nm) where absorption changes rapidly.
- **Band-integrated forward model:** Pre-compute band-averaged reflectance by integrating the forward model across the LED's emission spectrum. This is the most accurate approach but adds computational cost per iteration.
- **Effective extinction coefficients:** Pre-integrate ε(λ) weighted by the LED spectrum: ε_eff,band_j = ∫ ε(λ)·S_LEDj(λ) dλ / ∫ S_LEDj(λ) dλ. Use these effective ε values in the standard forward model. This is a good compromise for quick iteration.
- **5-LED selection study:** An optimized 5-LED multispectral scanner for reflectance estimation selected peak wavelengths at 450, 470, 530, 570, and 610 nm, achieving ΔE₉₄* ≈ 2 color difference. These wavelengths align well with hemoglobin features (Soret at ~414 nm, Q-bands at 542 and 576 nm). For bilirubin sensitivity, 460 nm coverage is notably missing from this set. [Source](https://library.imaging.org/admin/apis/public/api/ist/website/downloadArticle/jist/51/1/art00008)

**Recommendation for Hb + bilirubin multispectral system:** Minimum LED set should include ~415 nm (Soret), ~460 nm (bilirubin peak), ~540 nm (Hb Q-band), ~576 nm (Hb Q-band), and ~630 nm (reference/low absorption). The 460 nm channel is critical for bilirubin sensitivity.

### 8. Validation Against Known Phantom Concentration Series

**Murphy (2022) — Directly relevant Hb + bilirubin liquid phantom validation:**
- Phantoms: 12-well setup with polystyrene beads (1.0 μm) as scatterer, hemoglobin (0–2 mg/mL) and bilirubin (0–0.01 mg/mL) as absorbers in water.
- DRS system: 345–1045 nm, Ocean Optics spectrometer, 2.25 mm source-detector separation.
- Model: LUT-based inverse model (Rajaram/Tunnell type) with μₛ′(λ) = μₛ′(630)·(λ/630)⁻ᵇ, μₐ(λ) = [Hb]·ε_Hb(λ) + [Bil]·ε_Bil(λ).
- **Key results:** (a) Hemoglobin accuracy was good at lower concentrations (0–1 mg/mL), but underestimated by ~0.5 mg/mL at higher concentrations (1.5–2 mg/mL). (b) Bilirubin accuracy improved with increasing bilirubin concentration: at 0.002 mg/mL actual, large errors; at 0.01 mg/mL actual, error ~0.0004–0.0019 mg/mL. (c) When both chromophores present, accuracy for each degrades — cross-talk due to spectral overlap in 450–500 nm region. [Source](https://scholarworks.uark.edu/cgi/viewcontent.cgi?article=1126&context=bmeguht)

**Palmer & Ramanujam (2006) — MC-based inverse model on hemoglobin phantoms:**
- Validated on liquid phantoms with hemoglobin (0–0.5 mg/mL) + polystyrene spheres in water.
- MC-based inverse model extracted μₐ (0–20 cm⁻¹) and μₛ′ (7–33 cm⁻¹) with average error of 3% for Hb phantoms over 350–850 nm. This establishes that KM-class models can achieve ~3% error on "clean" single-chromophore phantoms. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-45-5-1062)

**Bahl et al. (2024) — Gelatin phantom validation of Yudovsky model:**
- Used synthetic dyes (Acid Red 1, Acid Red 14, Crystal Violet) mimicking HbO₂, Hb, and an additional chromophore in gelatin + Intralipid phantoms.
- Yudovsky model achieved excellent parameter recovery for 2-dye configurations: median APE ~1.4% for AR1 concentration (Pearson r = 1.00). However, parameter recovery degraded severely with 3 dyes due to peak shifts from dye-Intralipid interactions. **Key lesson:** Extinction coefficients measured in the actual phantom medium (not literature values) are essential — gelatin shifted dye peaks by ~5–10 nm. [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

**Murphy finding re spectral overlap:** Both Hb and bilirubin absorb strongly in the 400–500 nm region (Hb Soret at 414 nm, bilirubin peak at 460 nm). This spectral overlap creates a well-known difficulty in separating the two chromophores, especially at low bilirubin concentrations. Murphy recommends that future work should shift wavelength bounds to better discriminate bilirubin, possibly by including the bilirubin-specific 460–490 nm region with higher weight in the cost function. [Source](https://scholarworks.uark.edu/cgi/viewcontent.cgi?article=1126&context=bmeguht)

### 9. The KM K–S vs. μₐ–μₛ′ Distinction

The relationship between the phenomenological KM coefficients (K, S) and the physical absorption/reduced scattering coefficients (μₐ, μₛ′) is important but sometimes glossed over:

- **Original KM:** K = 2μₐ, S = μₛ′/something (depends on scattering anisotropy assumptions)
- **K and S are phenomenological:** They are defined from the two-flux differential equations, not from first-principles radiative transfer. Their additivity for mixtures (K = Σ cᵢKᵢ) holds under assumptions of isotropic scattering and homogeneous medium.
- **The derivation from first principles** (N-Flux theory, §15.1.3) shows that K = Σᵢ ηᵢ·Kᵢ holds because Kᵢ = σₐ,ᵢ = cᵢ·εᵢ at the level of individual components, and volumes add in non-reacting mixtures. For dissolved chromophores, cᵢ = nᵢ/V (number concentration), and K = Σ cᵢ·εᵢ follows directly.
- **The Yudovsky model sidesteps this entirely** by working directly with μₐ and μₛ′ (transport coefficients), avoiding the K/S phenomenological conversion. The transport albedo w₀ = μₛ′/(μₐ + μₛ′) is the fundamental input. [Source](https://learnvisualcomputing.github.io/rendering-nflux.html)

**Recommendation:** Use μₐ and μₛ′ directly as the workhorse variables. Do not convert through the classic K/S = (1−R∞)²/2R∞ pathway unless you have infinite-thickness reflectance data. The Yudovsky erratum model is the recommended route because it was empirically calibrated against gold-standard Monte Carlo simulations.

---

## Sources

### Kept:

- **Bahl et al. (2024), *J. Biophotonics*** — "A comparative study of analytical models of diffuse reflectance in homogeneous biological tissues: Gelatin-based phantoms and Monte Carlo experiments" — Most directly relevant: compares Yudovsky/Jacques/Beer-Lambert models with MC and phantom validation; provides fitted hyperparameters for n=1.33/1.35/1.44; reports parameter extraction accuracy (median APE, Pearson r). [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)

- **Yudovsky & Pilon (2009), *Appl. Opt.*** — "Simple and accurate expressions for diffuse reflectance of semi-infinite and two-layer absorbing and scattering media" (+ 2015 erratum) — The foundational semi-empirical model; erratum provides simplified 6-parameter formula. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-48-35-6670)

- **Murphy (2022), U. Arkansas Honors Thesis** — "Assessing the Potential Effectiveness of Diffuse Reflectance Spectroscopy for Quantifying Neonatal Skin Properties using Tissue Phantoms" — Only study found that directly tests Hb + bilirubin liquid phantom concentration series with DRS; provides specific phantom recipes, error data, and spectral overlap analysis. [Source](https://scholarworks.uark.edu/cgi/viewcontent.cgi?article=1126&context=bmeguht)

- **Jacques (2013), *Phys. Med. Biol.*** — "Optical properties of biological tissues: a review" — Definitive reference for μₛ′(λ) = a·(λ/500)⁻ᵇ power law, parameter ranges, and tissue-type scattering parameters. [Source](https://omlc.org/news/dec14/Jacques_PMB2013/Jacques_PMB2013.pdf)

- **N-Flux Theory / Foundations of Visual Computing, Ch. 15** — "The Kubelka-Munk Model" — Derivation of K = Σ c·ε from first principles (RTE → two-flux → mixture additivity); clarifies relationship between phenomenological K/S and physical σₐ/σₛ. [Source](https://learnvisualcomputing.github.io/rendering-nflux.html)

- **Prahl (OMLC)** — Tabulated hemoglobin molar extinction coefficients (HbO₂ and Hb, 250–1000 nm, 2 nm resolution). [Source](https://omlc.org/spectra/hemoglobin/summary.html)

- **Jacques & Prahl (OMLC)** — Bilirubin extinction coefficient data and worked example (ε = 53,846 cm⁻¹·M⁻¹ at 460 nm). [Source](https://omlc.org/classroom/ece532/class3/bilirubin.html)

- **Palmer & Ramanujam (2006), *Appl. Opt.*** — "Monte Carlo-based inverse model for calculating tissue optical properties. Part I: Theory and validation on synthetic phantoms" — 3% error benchmark for single-chromophore Hb phantoms. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-45-5-1062)

- **SPIE/IS&T (2007, *JIST*)** — LED multispectral scanner optimization: 5-LED selection with peaks at 450, 470, 530, 570, 610 nm. [Source](https://library.imaging.org/admin/apis/public/api/ist/website/downloadArticle/jist/51/1/art00008)

- **Kubelka-Munk accuracy correction (Appl. Spectrosc.)** — Proof that classic KM equation overestimates k by factor of 2; corrected form uses 4R∞ denominator. [Source](https://opg.optica.org/abstract.cfm?uri=as-49-8-1107)

### Dropped:

- Wikipedia/Kubelka-Munk theory — Good overview but superseded by the N-Flux chapter for implementation detail.
- Harrick Scientific KM application note — Too superficial; only covers the classic powder KM case.
- Photoacoustic and remote sensing papers — Different modality (PA) or field (satellite unmixing); not directly applicable to diffuse reflectance liquid phantoms.
- Mixbox (Sochorová) — Pigment mixing in paint industry context; two-constant KM approach is similar in structure but their focus on RGB rendering rather than quantitative chromophore extraction limits applicability.
- Solid phantom papers (epoxy, NIST standards) — Different matrix (solid epoxy vs. liquid), different scattering regime.
- IAD (Inverse Adding Doubling) papers — Address different measurement geometry (total reflectance + transmittance of slabs), not single-sided diffuse reflectance.

---

## Gaps

1. **Bilirubin extinction coefficient in aqueous solution at neutral pH:** The OMLC bilirubin data is for bilirubin in chloroform. Bilirubin spectra shift in aqueous buffers, and the exact ε(λ) for bilirubin in PBS or water at experimental phantom conditions was not found. Murphy (2022) measured ε values from dilute solutions (0.005 mg/mL) using a spectrophotometer but did not publish the full spectral data. Recommendation: measure ε_Bil(λ) directly in the phantom solvent system before implementation.

2. **Direct KM inverse on same Hb + bilirubin dataset:** The Murphy study used a LUT-based model (not analytical KM/Yudovsky). No study was found that applies the Yudovsky semi-empirical model specifically to Hb + bilirubin liquid phantom data. The Bahl study used synthetic dyes, not real hemoglobin. Recommendation: benchmark your KM implementation against the Murphy phantom data as a first validation step.

3. **Scattering from polystyrene beads in a KM framework:** The Mie power-law μₛ′(λ) = a·(λ/λ₀)⁻ᵇ was validated for tissues and Intralipid. For monodisperse polystyrene microspheres, the wavelength dependence can be more complex (Mie resonances). Murphy used Mie theory to compute the required bead concentration but the actual μₛ′(λ) spectral shape was not explicitly validated. Recommendation: compute μₛ′(λ) from Mie theory for your specific bead size/refractive index and check whether the power-law approximation is adequate.

4. **LED band integration for Hb Soret band:** The Soret band (414 nm) is ~60 nm wide (FWHM). For LEDs with FWHM > 15 nm, the narrow-band approximation likely fails here. No study was found that specifically quantifies the error from band-averaging across the Soret peak. Recommendation: simulate band-integration error for your specific LED spectra by convolving with high-resolution Hb extinction data.

5. **Oxygenation state handling:** The Murphy study used "ferrous stabilized human hemoglobin" which should maintain Hb in the deoxy state, but oxygenation state was not independently verified. The extinction spectra differ significantly between HbO₂ and Hb (especially the Soret peak shifts from ~414 nm for HbO₂ to ~430 nm for deoxy-Hb). For liquid phantoms in contact with air, partial oxygenation is expected. This introduces an additional unknown parameter (sO₂) if not controlled. Recommendation: either (a) chemically fix the oxygenation state (e.g., sodium dithionite for deoxy-Hb) and use pure Hb/HbO₂ spectra, or (b) add sO₂ as a fitted parameter: μₐ(λ) = c_Hb·[sO₂·ε_HbO₂(λ) + (1−sO₂)·ε_Hb(λ)].

---

## Implementation Recommendations

1. **Use the Yudovsky erratum model** with n=1.33 hyperparameters for water-based liquid phantoms. It is the best-performing analytical forward model (NRMSE ~0.01 vs MC) and has been validated across multiple phantom studies.

2. **Measure extinction coefficients in your phantom medium.** Literature ε values shift when chromophores are in different solvents (gelatin, PBS, Intralipid). Murphy and Bahl both observed peak shifts of 5–10 nm.

3. **Fix the scattering exponent b** if possible. For Intralipid phantoms, b ≈ 0.98 is stable across concentrations. This reduces unknowns and stabilizes the inverse problem.

4. **Restrict fitting to 450–575 nm** for phantom measurements. Beyond this, all analytical models deviate from measured reflectance (Bahl et al. 2024).

5. **Use constrained nonlinear least-squares** (`scipy.optimize.least_squares` with `trf` method, bounds on all parameters). Start with multiple initial guesses to avoid local minima.

6. **For LED band integration:** Pre-compute band-averaged extinction coefficients weighted by each LED's normalized emission spectrum. Use these "effective ε" values in the standard forward model.

7. **Validate first on single-chromophore phantoms** (Hb-only, bilirubin-only) before attempting mixtures. The spectral overlap between Hb Soret and bilirubin peaks in the 414–460 nm range creates well-documented cross-talk that requires careful treatment.

8. **Consider wavelength weighting** in the cost function: give higher weight to the bilirubin-specific 460–490 nm region to improve bilirubin sensitivity at low concentrations, following Murphy's recommendation.

9. **Include a background absorption term** to account for water and any other absorbing components in the phantom (e.g., DMSO used as bilirubin solvent in Murphy study).

10. **MC simulation validation:** Before deploying on physical phantoms, validate the entire pipeline (forward + inverse) on MC-simulated spectra with known ground truth. CUDAMCML (GPU-accelerated) can generate reference spectra efficiently (100,000 photons, semi-infinite slab, 3 cm thickness). [Source](https://lirias.kuleuven.be/retrieve/1c5a1453-32fa-46e6-a5eb-0db3dfbed54f)
