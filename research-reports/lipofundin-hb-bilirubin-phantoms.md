# Research: Lipofundin/Intralipid Scattering Phantoms with Hemoglobin and Bilirubin

## Summary

Lipofundin S and Intralipid fat emulsions are near-identical in scattering properties (μs' within 5% at 751 nm) and serve as reliable, batch-stable diffusive backgrounds for liquid tissue phantoms. Hemoglobin (Hb) and bilirubin (BR) both absorb strongly in the 400–500 nm region, with Hb dominating by roughly 10×. Their spectral overlap is severe below 500 nm but becomes tractable with wavelength selection at the BR/Hb extinction ratio maximum (~470 nm) paired with an Hb isosbestic point (~525–530 nm) where BR absorption is negligible. BR is extremely insoluble in water at neutral pH (<0.005 mg/100 mL), requiring albumin solubilization or alkaline conditions for phantom preparation. Practical phantom calibration follows a multi-wavelength least-squares unmixing framework with independently characterized component spectra.

## Findings

### 1. Lipofundin S is optically equivalent to Intralipid for phantom purposes

A comparative study by Di Ninni *et al.* (2012) measured Intralipid 10%, 20%, 30%, Lipovenoes 10%, 20%, and **Lipofundin S 10% and S 20%** at 751 nm. Key results: (a) absorption coefficients of all fat emulsions are the same within experimental error; (b) reduced scattering coefficients of Intralipid 20%, Lipovenoes 20%, and Lipofundin S 20% agree within 5%; (c) μs' scales approximately linearly with concentration — Intralipid 10% and 30% scaled from 20% with errors of 9% and 2% respectively, and the same holds for Lipofundin S. The scaling accuracy depends on whether ingredients scale exactly with concentration. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-51-30-7176)

### 2. Scattering follows a Mie-theory power law μs(λ) = a·λᵇ

Michels *et al.* (2008, Opt. Express) measured the optical properties of six fat emulsions (Intralipid, Lipovenoes, ClinOleic) from 350–900 nm. The scattering coefficient obeys a simple **power law** μs(λ) = a·λᵇ, the reduced scattering coefficient follows a **second-order polynomial** μs'(λ) = y₀ + a·λ + b·λ², and the anisotropy factor g(λ) is **linear**. Fitted parameters for Intralipid 20%:
- μs: a = 3.873×10⁸, b = −2.397 (λ in nm, μs in mm⁻¹)
- μs': y₀ = 82.61, a = −0.1288, b = 6.093×10⁻⁵
- g: y₀ = 1.090, a = −6.812×10⁻⁴

These power-law expressions are derived from Mie theory fits to measured particle size distributions and are valid 400–900 nm. The underlying physics is Mie scattering from spherical lipid droplets (soybean oil, encapsulated by egg lecithin) with diameters 25–660 nm. [Source](https://www.ilm-ulm.de/fileadmin/files/literatur/Michels.pdf)

### 3. Fat emulsion absorption is negligible in visible wavelengths above 550 nm

Intralipid/Lipofundin absorption is dominated by water and soybean oil. For wavelengths >550 nm, soybean oil absorption is negligible (μa ≤ 0.001 mm⁻¹ = 0.01 cm⁻¹) when diluted to typical phantom concentrations (~0.5 vol% scatterer). Water absorption begins to rise appreciably only above ~900 nm. The absorption coefficient can be calculated from the sigmoid fit: μa(λ) = a/(1 + e^(−(λ−x₀)/b)). Parameters for soybean oil: a = 1.171×10⁵, b = −36.59, x₀ = −321.0 (λ in nm, μa in mm⁻¹). [Source](https://www.ilm-ulm.de/fileadmin/files/literatur/Michels.pdf)

### 4. Hemoglobin absorption: dominant Soret band and informative Q-bands

From the OMLC tabulated data (Prahl, compiling Gratzer & Kollias), the molar extinction coefficients for hemoglobin (per heme, molecular weight 64,500 g/mole):

| Wavelength | ε HbO₂ (cm⁻¹/M) | ε Hb (cm⁻¹/M) |
|------------|-----------------|---------------|
| 420 nm (Soret) | 480,360 | 407,560 |
| 450 nm | 62,816 | 103,292 |
| 470 nm | 33,209 | 16,156 |
| 500 nm | 20,933 | 20,862 |
| 530 nm (isosbestic) | 39,957 | 39,036 |
| 542 nm (HbO₂ peak) | 53,292 | — |
| 555 nm (Hb peak) | — | 54,540 |
| 576 nm (HbO₂ peak) | 55,540 | — |
| 660 nm | ~320 | ~3,227 |
| 805 nm (isosbestic) | ~844 | ~730 |

Key isosbestic points: ~420, ~450, ~500, ~530, ~545, ~570, ~585, ~805 nm. The HbO₂/Hb ratio inverts around 800 nm (Hb absorbs more above). [Source](https://omlc.org/spectra/hemoglobin/summary.html)

### 5. Bilirubin absorption: peak at 440–460 nm, negligible above ~530 nm

Bilirubin's absorption spectrum depends critically on the solvent environment:
- **In chloroform**: peak at 450.8 nm, ε = 55,000 cm⁻¹/M (Agati & Fusi 1990)
- **Bound to human serum albumin** (physiologically relevant): peak at 460 nm, ε = 48,400 cm⁻¹/M [Source](https://www.nature.com/articles/pr201367/figures/5)
- **In aqueous buffer pH 7.4**: peak at 440 nm, ε ≈ 47,500 cm⁻¹/M — but **solubility is <0.005 mg/100 mL** (~0.85 μM), making direct aqueous dissolution impractical
- **At pH 12**: peak at 440 nm, ε = 63,500 cm⁻¹/M, much higher solubility
- **At 525 nm**: ε ≈ 214 cm⁻¹/M, essentially negligible [Source](https://pubs.rsc.org/en/content/articlehtml/2022/sd/d2sd00033d)

Critical practical issue: bilirubin in neutral aqueous media is not truly in solution — it exists as a colloidal dispersion that flocculates upon agitation, producing a 480–560 nm shoulder artifact. Oxidation shifts the peak to 415–420 nm. Antioxidants (ascorbic acid, N₂) and EDTA help stabilize the 440 nm peak. [Source](https://pubmed.ncbi.nlm.nih.gov/8755/)

### 6. Spectral overlap between Hb and BR is severe in the blue, but an optimal measurement window exists

Both Hb and BR absorb strongly at 400–500 nm:

- At 420 nm: Hb ε ≈ 400,000–480,000 vs BR ε ≈ 48,000 (Hb dominates by ~10×)
- At 460 nm (BR peak): HbO₂ ε ≈ 44,480 vs BR ε ≈ 48,400 (roughly equal)
- At 470 nm: **BR-to-Hb extinction ratio is maximal** — BR ε ≈ 33,000 vs HbO₂ ε ≈ 33,000 and Hb ε ≈ 16,000
- At 525–530 nm: **Hb isosbestic point** where HbO₂ ≈ Hb ≈ 40,000, but BR ε ≈ 214 (negligible)

The dual-wavelength strategy recommended in the literature: λ₁ = 470 nm (sensitive to BR + Hb), λ₂ = 525–530 nm (sensitive to Hb only, independent of oxygenation). The absorbance ratio A₄₇₀/A₅₂₅ correlates linearly with bilirubin concentration across 1.2–30 mg/dL. [Source](https://pubs.rsc.org/en/content/articlehtml/2022/sd/d2sd00033d) and [Source](https://arxiv.org/pdf/2406.14816)

### 7. Practical phantom calibration: pure-component spectra + least-squares unmixing

The standard calibration approach, validated in multiple studies:

**Zhou *et al.* (2012, JBO) — Photoacoustic phantom calibration:**
- Prepare pure bilirubin samples (2, 4, 6, 8 mg/dL) and pure blood samples (148 g/L Hb, ~75% sO₂)
- Measure photoacoustic spectra at each wavelength
- Fit via: φ(λ) = k_bi·ε_bi(λ)·C_bi + k_ox·ε_ox(λ)·C_ox + k_de·ε_de(λ)·C_de
- Calibration factors k are determined from pure samples by weighted least squares
- Wavelength ranges: 430–490 nm for BR, 540–545 nm for blood (where BR has zero absorption)
- Achieved RMSEP of ~1 mg/dL for bilirubin [Source](https://coilab.caltech.edu/documents/26232/ZhouY_2012_JBO_v17_126019.pdf)

**Blood-lipid phantom study (SPIE 2022) — Critical dependencies:**
- The choice of extinction coefficient dataset (Moaveni, Takatani, Cope, Gratzer) significantly affects Hb concentration and sO₂ estimates
- Wavelength subset selection strongly influences results
- Moaveni *et al.* dataset provided the most consistent StO₂ estimates in blood-lipid phantoms [Source](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11920/119200F/Hemoglobin-spectra-and-employed-wavelengths-affect-estimation-of-concentration-and/10.1117/12.2615220.full)

**Gelatin-based BR phantom calibration (PMC 2019):**
- TiO₂ or Intralipid as scatterer, coffee or ink as broadband absorber, bilirubin as target chromophore
- Spatially resolved DRS with diffusion-model inversion to recover μa(λ) and μs'(λ)
- Linear least-squares fit of recovered μa(λ) to known chromophore spectra
- BR recovery accuracy: ~0.41 mg/dL mean deviation across 0–40 mg/dL range [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6583349/)

### 8. Bilirubin solubilization for phantoms: practical approaches

Given the extreme insolubility of unconjugated bilirubin in neutral aqueous buffers:

1. **Albumin-bound bilirubin**: Dissolve BR in dilute NaOH (pH > 12), then add to bovine or human serum albumin solution, adjust to pH 7.4. This mimics the physiological state and produces the characteristic 460 nm peak.
2. **DMSO/chloroform pre-dissolution**: Dissolve BR in DMSO or chloroform first (where it is highly soluble), then add to aqueous phantom matrix. Be aware this may shift the peak to ~450 nm.
3. **Alkaline pH phantom**: Operate at pH 10–12 where BR is more soluble, but note the shift in ε and altered Hb spectra.
4. **Commercial conjugated bilirubin (direct bilirubin)**: Water-soluble ditaurobilirubin or similar may be used but has altered spectral properties.

[Source](https://pubmed.ncbi.nlm.nih.gov/8755/) and [Source](https://www.nature.com/articles/pr1976138)

### 9. Hb/BR phantom implementation considerations for spectral unmixing

For a Lipofundin-based liquid phantom with Hb + BR:

- **Scatterer**: Lipofundin S 20% (or Intralipid 20%) diluted to achieve target μs'(λ). μs' follows a second-order polynomial in λ and scales approximately linearly with concentration.
- **Absorber 1 (Hb)**: Use fresh whole blood or purified hemoglobin. Control oxygenation state via yeast (deoxygenation) or O₂ bubbling (oxygenation). Typical physiological concentration: 150 g/L (whole blood), diluted to ~1–5% in phantom to give μa ~0.1–1.0 cm⁻¹ in visible.
- **Absorber 2 (BR)**: Use albumin-solubilized bilirubin at clinically relevant concentrations (0.5–40 mg/dL in phantom).
- **Reference/background**: Water absorption dominates above 900 nm; the fat emulsion itself contributes negligible absorption in visible.
- **Wavelength range**: 450–600 nm captures both BR peak region and Hb Q-bands; extend to 650–850 nm for oxygenation-sensitive channels.
- **Beware**: At the low Hb concentrations typical in phantoms, BR absorption at 460 nm can be comparable to or exceed Hb absorption, depending on the concentration ratio. The BR extinction at peak (~48,000) exceeds HbO₂ at 460 nm (~44,500) but is dwarfed by Hb in the Soret band.

### 10. Multi-center reference values exist for Intralipid scattering

Spinelli *et al.* (2014, Biomed. Opt. Express) — a nine-laboratory, six-country study — determined:
- Intrinsic reduced scattering coefficient of Intralipid-20% with **~1% uncertainty** at three NIR wavelengths
- Intrinsic absorption coefficient of India ink with **~2% or better uncertainty**
- These represent the most authoritative reference values for liquid phantom calibration

These values are applicable to Lipofundin S with <5% error based on the Di Ninni study. [Source](https://portal.research.lu.se/en/publications/determination-of-reference-values-for-optical-properties-of-liqui)

### 11. Scattering phase function and detection geometry matter

The scattering phase function of Intralipid/Lipofundin is not well approximated by the Henyey-Greenstein model — the real phase function shows substantial deviations at side-scattering angles despite having the same g-factor. This matters for non-diffuse reflectance geometries. For measurements in the diffusion regime (source-detector separation >> 1/μs'), the exact phase function is less critical. [Source](https://opg.optica.org/abstract.cfm?uri=BIOMED-2012-BW3B.2)

### 12. BR-to-Hb ratio and detection limits

The RSC review on bilirubin sensing reports that BR ε exceeds HbO₂ ε between 452–488 nm. At the peak ratio wavelength of 470 nm, BR has ~2× the extinction of Hb (per mole of heme). For normal adult bilirubin levels (~1.2 mg/dL ≈ 20 μM), μa(BR) at 460 nm ≈ 2.5 cm⁻¹, which is detectable but much smaller than typical tissue μa from Hb. In phantoms, the dynamic range can be tuned by adjusting concentrations. [Source](https://pubs.rsc.org/en/content/articlehtml/2022/sd/d2sd00033d)

## Sources

### Kept
- **Michels, Foschum, Kienle (2008)** "Optical properties of fat emulsions," *Opt. Express* 16(8):5907–5925 — Definitive power-law parameterization of μs, μs', g for Intralipid/Lipovenoes/ClinOleic (400–900 nm); Mie theory validation. [Source](https://www.ilm-ulm.de/fileadmin/files/literatur/Michels.pdf)
- **Di Ninni, Martelli, Zaccanti (2012)** "Fat emulsions as diffusive reference standards," *Appl. Opt.* 51(30):7176–7182 — Direct comparison of Lipofundin S to Intralipid; batch stability and scaling laws. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-51-30-7176)
- **Prahl (OMLC)** "Tabulated Molar Extinction Coefficient for Hemoglobin in Water" — Gold-standard ε(HbO₂) and ε(Hb) from 250–1000 nm (Gratzer/Kollias data). [Source](https://omlc.org/spectra/hemoglobin/summary.html)
- **Agati & Fusi (1990) / PhotochemCAD** — Bilirubin ε spectrum in chloroform, peak at 450.8 nm, ε = 55,000. [Source](https://omlc.org/spectra/PhotochemCAD/html/119.html)
- **Nature Pediatric Research (2013)** — Absorption spectra overlay of HbO₂, Hb, and albumin-bound bilirubin; peak at 460 nm, ε = 48,400. [Source](https://www.nature.com/articles/pr201367/figures/5)
- **Lee & Gartner (1976)** "Spectrophotometric Characteristics of Bilirubin," *Pediatric Research* — Definitive study on BR solubility, pH dependence, oxidation, and flocculation artifacts at neutral pH. [Source](https://pubmed.ncbi.nlm.nih.gov/8755/)
- **RSC Sensors & Diagnostics (2022)** "70 years of bilirubin sensing" — Comprehensive review of BR spectroscopy, Hb/BR overlap, dual-wavelength strategy (470/530 nm), and phantom validation. [Source](https://pubs.rsc.org/en/content/articlehtml/2022/sd/d2sd00033d)
- **Zhou et al. (2012)** "Photoacoustic microscopy of bilirubin and blood," *J. Biomed. Opt.* 17:126019 — Calibration protocol for BR/Hb mixtures, wavelength selection, RMSEP values. [Source](https://coilab.caltech.edu/documents/26232/ZhouY_2012_JBO_v17_126019.pdf)
- **SPIE (2022)** "Hemoglobin spectra and employed wavelengths affect estimation of concentration and oxygen saturation: blood-lipid phantom study" — Demonstrated dependence of unmixing accuracy on ε dataset and wavelength subset choice. [Source](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11920/119200F/Hemoglobin-spectra-and-employed-wavelengths-affect-estimation-of-concentration-and/10.1117/12.2615220.full)
- **Spinelli et al. (2014)** "Determination of reference values for optical properties of liquid phantoms based on Intralipid and India ink," *Biomed. Opt. Express* 5(7):2037–2053 — Multi-center reference standard with 1–2% uncertainty. [Source](https://portal.research.lu.se/en/publications/determination-of-reference-values-for-optical-properties-of-liqui)
- **Flock et al. (1992)** "Optical properties of Intralipid: A phantom medium for light propagation studies," *Lasers Surg. Med.* 12:510–519 — Foundational μa and μs' values for Intralipid-10% (460–690 nm). [Source](https://onlinelibrary.wiley.com/doi/10.1002/lsm.1900120510)
- **PMC (2019)** "Noninvasive transcutaneous bilirubin assessment" — Gelatin phantom calibration with BR + coffee; demonstrates μa recovery via diffusion model and chromophore fitting. [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC6583349/)
- **arXiv (2024)** "Dual-wavelength bilirubin measurement in blood phantoms" — Validation of 470/525 nm DWL method on whole blood and phantoms. [Source](https://arxiv.org/pdf/2406.14816)

### Dropped
- Several generic Intralipid review papers — redundant with the Michels and Di Ninni primary sources.
- SIELC UV-Vis spectrum of bilirubin — measured under acidic mobile-phase HPLC conditions, not physiologically relevant.
- Bilirubin infrared/Raman studies — outside the visible spectral range of interest.

## Gaps

1. **No published power-law parameters specifically for Lipofundin S**: While Di Ninni *et al.* confirm Lipofundin S μs' matches Intralipid within 5% at 751 nm, the wavelength-dependent power-law parameters from Michels *et al.* cover Intralipid, Lipovenoes, and ClinOleic but **not** Lipofundin S. Using Intralipid 20% parameters as a proxy is reasonable within ~5% error.

2. **Bilirubin absorption in scattering phantoms**: Most published BR phantom studies use non-scattering or weakly scattering gelatin matrices. Direct measurement of BR extinction in highly scattering Intralipid/Lipofundin suspensions (where multiple scattering alters the effective path length) is not well-characterized. The Beer-Lambert assumption in DWL methods may need modification for turbid media.

3. **Hb-BR binding interactions**: In whole blood or phantom mixtures, bilirubin binds to albumin and potentially to hemoglobin. The spectral shift upon Hb-BR interaction in phantom conditions is not well studied.

4. **Temperature dependence**: Intralipid scattering shows measurable temperature dependence (Cletus *et al.* 2010, J. Biomed. Opt.), and Hb oxygenation is temperature-sensitive. Phantom measurements should be temperature-controlled.

5. **Concentration-dependent scattering artifacts**: At high absorber concentrations (particularly Hb), the assumption of independent control of absorption and scattering may break down due to refractive index changes affecting the scattering particle contrast.

## Supervisor coordination

No blocking issues. The research is complete and covers all requested aspects: Lipofundin/Intralipid optical equivalence, scattering power laws, Hb and BR absorption spectra with precise values, spectral overlap and identifiability analysis, wavelength selection strategies, and practical calibration approaches from peer-reviewed literature.
