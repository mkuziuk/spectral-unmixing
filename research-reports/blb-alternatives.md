# Research: Alternatives to Beer-Lambert/Bouguer for Spectral Unmixing in Turbid Media

## Summary

The standard Beer-Lambert law fails in turbid media because it assumes negligible scattering — an assumption violated by Lipofundin/Intralipid phantoms containing hemoglobin and bilirubin. Five families of alternatives exist, spanning a spectrum from fast analytical approximations (Kubelka-Munk, diffusion theory) through rigorous numerical inversions (Inverse Adding-Doubling, Monte Carlo lookup tables) to fully data-driven empirical approaches (PLS). For Lipofundin-based phantoms with Hb/HbO₂/bilirubin, the Kubelka-Munk two-layer model with Saunderson correction has been directly validated for these exact chromophores in human skin studies, while Inverse Adding-Doubling and Monte Carlo lookup tables provide the highest accuracy for extracting bulk optical properties (mu_a, mu_s') that can then be linearly unmixed into chromophore concentrations. No single method dominates; the choice depends on required accuracy, computational budget, measurement geometry, and whether the goal is bulk optical property extraction or direct chromophore concentration estimation.

---

## Findings

### 1. Kubelka-Munk (KM) Theory

**Equations.** KM is a two-flux model describing forward (i) and backward (j) diffuse fluxes in a homogeneous layer of thickness h, with absorption coefficient K and backscattering coefficient S:

```
di/dz = -(K+S)·i(z) + S·j(z)
dj/dz = -S·i(z) + (K+S)·j(z)
```

The reflectance R and transmittance T are:
```
R = sinh(bSh) / [b·cosh(bSh) + a·sinh(bSh)]
T = b / [b·cosh(bSh) + a·sinh(bSh)]
where a = (K+S)/S, b = sqrt(a^2 - 1)
```

For a semi-infinite layer: R_inf = a - b = (K+S - sqrt(K^2+2KS))/S. For a layer on a background with reflectance rho_g, a more complex expression is used. The Saunderson correction accounts for the refractive index mismatch at the air-medium interface using Fresnel formulas. [Source](https://hal.science/hal-01458764/document)

**Assumptions.** Diffuse illumination only; homogeneous layers; K and S are phenomenological coefficients distinct from radiative-transfer mu_a and mu_s (though empirical relationships exist: K ~ 2mu_a, S ~ mu_s' in the diffuse regime). KM is a special solution of the RTE valid only when scattering dominates. [Source](https://pubmed.ncbi.nlm.nih.gov/23214177/)

**Application to Hb/HbO₂/Bilirubin.** KM has been directly applied to extract Hb, HbO₂, and bilirubin from skin reflectance spectra. Seroul et al. (2016) used a two-layer KM model with Saunderson correction. The dermis absorption coefficient was modeled as a linear additive mixture:
```
K_d(lambda) = c_b*K_b + c_Hb*K_Hb + c_HbO2*K_HbO2 + c_bi*K_bi
```
The model was inverted via Nelder-Mead optimization (least squares or spectral angle similarity), retrieving 5 parameters per pixel in ~3.4 ms, including bilirubin volume fraction (0.35+-0.15%, consistent with literature). [Source](https://hal.science/hal-01458764/document). Doi et al. (2004) independently validated KM with the same four pigments (melanin, Hb, HbO₂, bilirubin). [Source](https://library.imaging.org/admin/apis/public/api/ist/website/downloadArticle/cgiv/2/1/art00078)

A transformed, normalized KM function at three wavelengths (420, 460, 510 nm) was shown to be linearly related to serum bilirubin concentration with r=0.778-0.865, demonstrating clinical relevance. [Source](http://preview-www.nature.com/articles/pr1979472)

**Lipofundin applicability.** Lipofundin S has optical properties very similar to Intralipid: mu_s' of Lipofundin S 20% is within 5% of Intralipid 20% at 751 nm, scaling linearly with concentration. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-51-30-7176). KM-to-RTE coefficient conversion is validated with ~10% reflectance accuracy and 90-95% chromophore concentration accuracy. [Source](https://pubmed.ncbi.nlm.nih.gov/23214177/)

**Limitations.** Accuracy degrades for thin layers, low albedo, and near boundaries. The revised KM theory (with scattering-induced-path-variation factor) has been shown to yield significant errors; the original KM formulation should be used. [Source](https://opg.optica.org/abstract.cfm?uri=josaa-24-2-548)

---

### 2. Inverse Adding-Doubling (IAD)

**Method.** IAD, developed by Scott Prahl, inverts the exact Adding-Doubling solution of the RTE for plane-parallel slabs. Given integrating-sphere measurements of total reflectance (MR), total transmittance (MT), and optionally collimated transmittance (MU), the algorithm iteratively adjusts mu_a, mu_s, and anisotropy g until computed values match measurements. A Monte Carlo subroutine estimates light lost out sample edges, correcting integrating-sphere artifacts. Intrinsic error is under 3% with 4 quadrature points. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-32-4-559), [Source](https://omlc.org/software/iad/index.html)

**Assumptions.** Works for any albedo, any optical depth, any phase function. Requires: (a) homogeneous slab with parallel surfaces, (b) known refractive index of sample and surrounding medium, (c) known integrating-sphere geometry (port sizes, sphere wall reflectance). Fresnel boundary reflections are incorporated. [Source](https://omlc.org/software/iad/manual.pdf)

**Equations (conceptual).** The Adding-Doubling method represents reflection/transmission as matrices R and T over quadrature angles. For a thin initial layer (optical thickness delta-tau), single-scattering gives R_0 and T_0. Doubling produces:
```
R_{2d} = R_d + T_d * (I - R_d*R_d)^(-1) * R_d * T_d^(-1)
```
(where operations are matrix multiplications over angle). Layers with different properties are added similarly. The inverse step minimizes ||MR_measured - MR_calc|| + ||MT_measured - MT_calc|| using a constrained optimization. [Source](https://omlc.org/~prahl/pubs/pdf/prahl95c.pdf)

**Hb/HbO₂/Bilirubin relevance.** IAD extracts bulk mu_a(lambda) and mu_s'(lambda) from slab measurements. Chromophore concentrations are then obtained by linear spectral unmixing of mu_a(lambda):
```
mu_a(lambda) = sum_i [epsilon_i(lambda) * c_i]
```
where epsilon_i are known extinction coefficients. This two-step approach (IAD then unmixing) has been used for hemoglobin quantification in blood-lipid phantoms with Intralipid. [Source](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/11920/119200F/Hemoglobin-spectra-and-employed-wavelengths-affect-estimation-of-concentration-and/10.1117/12.2615220.full)

**Lipofundin applicability.** IAD is the gold standard for extracting optical properties from fat-emulsion phantoms. Prahl et al. demonstrated IAD on Intralipid-based phantoms, and the method applies identically to Lipofundin since it requires only integrating-sphere measurements. The open-source `iad` program (github.com/scottprahl/iad) handles spectral data and outputs mu_a(lambda), mu_s'(lambda). [Source](https://github.com/scottprahl/iad)

**Limitations.** Requires careful integrating-sphere measurements; sensitive to light-loss artifacts and sphere calibration; 1D geometry only; assumes known scattering anisotropy g (often fixed at 0.8-0.9 for tissue phantoms).

---

### 3. Radiative Transfer Equation (RTE) Approximations

#### 3a. Diffusion Approximation

**Equations.** The diffusion approximation simplifies the RTE by assuming radiance is nearly isotropic after sufficient scattering. For a homogeneous semi-infinite medium with a collimated source, the steady-state spatially-resolved diffuse reflectance at radial distance rho is:
```
R(rho) = C1*exp(-mu_eff*r1)/r1^2*(1/r1 + mu_eff) + C2*exp(-mu_eff*r2)/r2^2*(1/r2 + mu_eff)
```
where mu_eff = sqrt(3*mu_a*(mu_a + mu_s')), r1 = sqrt(rho^2 + z0^2), r2 = sqrt(rho^2 + (z0 + 2*z_b)^2), with z0 = 1/(mu_a + mu_s') and z_b the extrapolated boundary distance accounting for refractive index mismatch. [Source](https://opg.optica.org/josaa/abstract.cfm?uri=josaa-14-1-246), [Source](https://opg.optica.org/abstract.cfm?uri=ao-36-19-4587)

**Assumptions.** mu_s' >> mu_a (high albedo); distances >> 1/mu_s' (far from source); radiance nearly isotropic. Breaks down for: strongly absorbing media (common in visible range with high blood/bilirubin content), thin layers, and small source-detector separations (~under 1 transport mean free path). [Source](https://escholarship.org/uc/item/8rb0z9vj)

**Extensions.** The delta-P1 approximation improves accuracy at arbitrary albedo and spatial scales comparable to one transport mean free path, enabling separation of g from mu_s'. [Source](https://opg.optica.org/abstract.cfm?uri=ao-43-24-4677). Hybrid diffusion + two-flux models have been developed for multilayered tissues with both strongly and weakly scattering layers. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-50-21-4237)

**Hb/HbO₂/Bilirubin relevance.** Diffusion theory is widely used for extracting mu_a and mu_s' from spatially-resolved reflectance, followed by chromophore unmixing. However, it is unreliable in the visible range where hemoglobin absorption is strong. For bilirubin (peak absorption ~460 nm), the diffusion approximation may fail due to low albedo. Extended formulations (generalized diffusion by Prahl/Star) improve accuracy down to albedo ~0.25. [Source](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.58.2395)

#### 3b. Analytical RTE Solutions (P_N and Spherical Harmonics)

Analytical solutions of the full RTE for layered turbid media using P_N (spherical harmonics) methods provide exact benchmarks. For N >= 3, P_N solutions agree with Monte Carlo within ~1% for time-resolved reflectance from two-layer models, while the diffusion approximation shows significant errors at early times and for certain layer configurations. [Source](http://www.nature.com/articles/s41598-017-02979-4)

---

### 4. Monte Carlo Lookup / Inverse Modeling

**Method.** Monte Carlo (MC) simulations statistically model photon transport through turbid media. For inverse problems, two main approaches exist:

**(a) Lookup Table (LUT) approach.** A forward MC simulation generates a database mapping (mu_a, mu_s') to observable reflectance/transmittance for a specific probe geometry. The inverse problem reduces to table lookup and interpolation. LUTs can be generated from MC simulations or from calibrated experimental measurements. Valid for very short source-detector separations (~300 microns) and low albedo (~0.35). [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC2627585/)

**(b) Iterative MC inversion.** A forward MC model is called iteratively within an optimization loop. The "condensed Monte Carlo" method speeds up simulations. Validated on liquid phantoms containing hemoglobin as absorber and polystyrene spheres as scatterers, with average errors of 3% for hemoglobin and 12% for Nigrosin across mu_a = 0-20 cm^-1 and mu_s' = 7-33 cm^-1 over 350-850 nm. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-45-5-1062)

**Phase function considerations.** Standard LUTs assume the Henyey-Greenstein phase function with fixed g. However, the scattering phase function significantly influences reflectance, especially at sub-diffusive source-detector separations. The extended inverse MC model (e-IMC) incorporates a similarity parameter gamma (spanning 1.6-2.3 for biological variations) that captures phase function effects beyond the first similarity relation, improving accuracy significantly. [Source](https://www.spiedigitallibrary.org/journals/journal-of-biomedical-optics/volume-21/issue-09/095003/Estimation-of-optical-properties-by-spatially-resolved-reflectance-spectroscopy-in/10.1117/1.JBO.21.9.095003.full)

**Hb/HbO₂/Bilirubin relevance.** The MC inverse model has been directly applied to breast tissue diagnosis, extracting hemoglobin concentration, oxygen saturation, and scattering parameters from 400-600 nm diffuse reflectance. [Source](https://opg.optica.org/ao/abstract.cfm?uri=ao-45-5-1072). MC-based methods are the most accurate for extracting optical properties, especially at shorter wavelengths where hemoglobin absorption peaks. For bilirubin at ~460 nm, the high absorption makes accurate MC modeling particularly important.

**Lipofundin applicability.** MC models are well-suited to Lipofundin phantoms. The known Intralipid/Lipofundin scattering phase function can be incorporated. However, one limitation: Intralipid's phase function differs from the Henyey-Greenstein approximation commonly used in MC codes, which can introduce systematic errors in non-diffuse reflectance spectroscopy. [Source](https://opg.optica.org/abstract.cfm?uri=BIOMED-2012-BW3B.2)

---

### 5. Empirical / Partial Least Squares (PLS) Approaches

**Method.** PLS regression builds a statistical model relating measured spectra X to known analyte concentrations Y by projecting both into a latent variable space that maximizes covariance:
```
X = T*P' + E
Y = U*Q' + F
```
where T and U are score matrices, P and Q are loading matrices. The regression model predicts Y from new spectra without requiring a physical light-propagation model. [Source](https://www.sciencedirect.com/science/article/abs/pii/S0006291X12004032)

**Hb/HbO₂/Bilirubin applications.** PLS has been demonstrated for:

- **Hemoglobin in whole blood**: NIR transmission spectra (1100-2500 nm) with improved uninformative variable elimination (UVE) for wavelength selection, achieving RPD > 4.4. [Source](https://www.sciencedirect.com/science/article/abs/pii/S0006291X12004032)

- **Bilirubin in serum**: Visible-NIR spectroscopy (Vis-NIR) with EC-PLS wavelength optimization for indirect bilirubin (SEP = 0.90 micromol/L, R = 0.975), direct bilirubin (SEP = 0.71, R = 0.955), and total bilirubin (SEP = 0.82, R = 0.990). [Source](https://www.sciencedirect.com/science/article/abs/pii/S1386142520301931)

- **Unconstrained Moving-Window PLS**: For serum bilirubin indicators, achieving ratio of performance-to-deviation (RPD) of 3.0-5.8, demonstrating reagent-free simultaneous quantification. [Source](https://www.fxcsxb.com/en/article/doi/10.12452/j.fxcsxb.25021385/)

- **Non-invasive neonatal monitoring**: A device (SAMIRA) using spectroscopic analysis with machine learning simultaneously measures hemoglobin, bilirubin, and oxygen saturation from a single optical spectrum through the nail bed, achieving 98% accuracy. [Source](https://nature.com/articles/s41598-023-29041-w)

**Linear unmixing with least squares.** Zhou et al. (2012) demonstrated photoacoustic-based spectral unmixing for bilirubin-blood mixtures using weighted least squares fitting:
```
phi(lambda) = k_bi * epsilon_bi(lambda) * C_bi + k_ox * epsilon_ox(lambda) * C_ox + k_de * epsilon_de(lambda) * C_de
```
with RMSEP of 1.04 mg/dL for bilirubin in blood mixtures at 75% sO2. [Source](https://coilab.caltech.edu/documents/26232/ZhouY_2012_JBO_v17_126019.pdf)

**Advantages and limitations.** PLS requires no physical model of light transport, making it computationally efficient and robust to unknown experimental factors. However, it requires a comprehensive calibration dataset spanning all expected concentrations, is sensitive to instrumental drift and batch effects, and provides no physical insight into optical properties. Model transfer between instruments is challenging. [Source](https://scispace.com/pdf/beer-lambert-law-for-optical-tissue-diagnostics-current-2fu247r9x1.pdf)

---

### 6. Method Comparison for Lipofundin Phantoms with Hb/HbO₂/Bilirubin

| Method | Accuracy | Speed | Requirements | Hb/HbO₂/Bilirubin Validation |
|--------|----------|-------|--------------|------------------------------|
| **Kubelka-Munk** | ~10% reflectance; 90-95% concentrations | Very fast (ms/spectrum) | Diffuse reflectance, known K/S vs mu_a/mu_s' | Directly validated (skin) |
| **Inverse Adding-Doubling** | <3% intrinsic error | Fast (seconds/spectrum) | Integrating sphere; known g; careful calibration | Validated via two-step (IAD then linear unmixing) |
| **Diffusion approximation** | Good for high albedo, near-IR; degrades in visible | Fast (analytical) | mu_s' >> mu_a, large source-detector separation | Unreliable at bilirubin/Hb absorption peaks |
| **MC lookup table** | 3-12% error | Moderate (pre-computation heavy; lookup fast) | Known probe geometry; phase function; calibration | Validated for Hb (3% error) |
| **PLS / empirical** | R > 0.95 for individual analytes | Very fast (matrix multiply) | Comprehensive calibration dataset | Validated individually (not simultaneously in turbid phantoms) |

**Recommended strategy for Lipofundin + Hb/HbO₂ + bilirubin phantoms:**

1. **If integrating-sphere measurements are available**: Use IAD to extract mu_a(lambda) and mu_s'(lambda), then perform linear spectral unmixing of mu_a(lambda) into Hb, HbO₂, and bilirubin concentrations using known extinction coefficients. This is the most rigorous two-step approach.

2. **If only diffuse reflectance spectra are available**: Use KM with Saunderson correction and the empirical KM-to-RTE coefficient mapping, then invert via nonlinear optimization (Nelder-Mead or Levenberg-Marquardt) to directly recover chromophore concentrations. This has been validated for the exact chromophores of interest.

3. **If probe-based reflectance measurements**: Use a Monte Carlo lookup table calibrated for the specific probe geometry, combined with linear spectral unmixing or iterative fitting.

4. **For rapid screening or when calibration standards are comprehensive**: PLS provides a fast, model-free alternative but requires careful wavelength selection and may not generalize across phantom compositions.

---

## Sources

### Kept

- Seroul et al. (2016), "Model-based skin pigment cartography by high-resolution hyperspectral imaging," J. Imaging Sci. Technol. — https://hal.science/hal-01458764/document — Directly validates KM for Hb/HbO₂/bilirubin with equations.
- Doi et al. (2004), "Spectral Reflectance-Based Modeling of Human Skin and Its Application," CGIV 2004 — https://library.imaging.org/admin/apis/public/api/ist/website/downloadArticle/cgiv/2/1/art00078 — KM applied to same four pigments.
- Prahl et al. (1993), "Determining the optical properties of turbid media by using the adding-doubling method," Appl. Opt. 32, 559-568 — https://opg.optica.org/ao/abstract.cfm?uri=ao-32-4-559 — Foundational IAD paper.
- Prahl (1995), "The adding-doubling method," in Optical-Thermal Response of Laser Irradiated Tissue — https://omlc.org/~prahl/pubs/pdf/prahl95c.pdf — Detailed AD theory.
- IAD software and manual — https://omlc.org/software/iad/index.html, https://github.com/scottprahl/iad — Reference implementation.
- Empirical KM-RTE relationship — https://pubmed.ncbi.nlm.nih.gov/23214177/ — Critical for converting KM coefficients to real optical properties.
- Diffusion approximation reflectance solutions — https://opg.optica.org/josaa/abstract.cfm?uri=josaa-14-1-246 — Improved steady-state and time-resolved solutions.
- Extended diffusion for high absorption — https://journals.aps.org/pre/abstract/10.1103/PhysRevE.58.2395 — Generalized diffusion valid to albedo ~0.25.
- MC inverse model Part I — https://opg.optica.org/ao/abstract.cfm?uri=ao-45-5-1062 — Validated on hemoglobin phantoms (3% error).
- MC LUT for low albedo — https://pmc.ncbi.nlm.nih.gov/articles/PMC2627585/ — Valid at 300 micron separation, albedo ~0.35.
- Extended IMC with similarity parameter gamma — https://www.spiedigitallibrary.org/journals/journal-of-biomedical-optics/volume-21/issue-09/095003/ — Phase function effects in sub-diffusive regime.
- Lipofundin optical properties — https://opg.optica.org/ao/abstract.cfm?uri=ao-51-30-7176 — Confirms Lipofundin S is equivalent to Intralipid for phantom use.
- Intralipid phase function limitations — https://opg.optica.org/abstract.cfm?uri=BIOMED-2012-BW3B.2 — Critical for non-diffuse reflectance.
- PLS for bilirubin — https://www.sciencedirect.com/science/article/abs/pii/S1386142520301931 — EC-PLS wavelength optimization, high accuracy.
- PLS for hemoglobin — https://www.sciencedirect.com/science/article/abs/pii/S0006291X12004032 — UVE-PLS for whole blood Hb.
- PAM bilirubin-blood unmixing — https://coilab.caltech.edu/documents/26232/ZhouY_2012_JBO_v17_126019.pdf — Weighted least squares, RMSEP 1.04 mg/dL.
- Beer-Lambert limitations review — https://scispace.com/pdf/beer-lambert-law-for-optical-tissue-diagnostics-current-2fu247r9x1.pdf — Comprehensive review of why BLB fails.
- Revised KM theory critique — https://opg.optica.org/abstract.cfm?uri=josaa-24-2-548 — Shows revised KM is wrong; use original.
- Analytical RTE solutions — http://www.nature.com/articles/s41598-017-02979-4 — P_N solutions as benchmarks.

### Dropped

- Several photoacoustic-specific papers (eMSOT, learned spectral decoloring) — modality-specific; not directly applicable to CW reflectance/transmission spectroscopy.
- General MC code comparison papers — not specific to spectral unmixing.
- Papers on pulse oximetry and clinical bilirubinometers using simple dual-wavelength approaches — too simplified for the turbid phantom unmixing problem.

---

## Gaps

1. **No direct head-to-head comparison** of all five methods on the exact same Lipofundin + Hb/HbO₂ + bilirubin phantom dataset was found. Such a benchmark study would be valuable.

2. **KM coefficient conversion for Lipofundin specifically**: The empirical K↔mu_a, S↔mu_s' relationships have been validated for Intralipid but not specifically for Lipofundin S. While the scattering properties are nearly identical, explicit validation would strengthen confidence.

3. **Bilirubin extinction coefficients in turbid media**: Bilirubin's absorption spectrum in the 400-500 nm range overlaps strongly with hemoglobin. Accurate spectral unmixing requires precise knowledge of extinction coefficients, and small variations in these coefficients significantly impact concentration estimates. The optimal extinction coefficient dataset for simultaneous Hb/HbO₂/bilirubin unmixing in turbid phantoms has not been systematically evaluated.

4. **Phase function effects**: The influence of Lipofundin's specific scattering phase function (which differs from Henyey-Greenstein) on the accuracy of each method for bilirubin quantification is not quantified.

5. **Nonlinearity at high absorber concentrations**: Both KM and diffusion theory assume linear additive absorption (Beer-Lambert for the absorption coefficient). At very high bilirubin or hemoglobin concentrations, this linearity may break down. The concentration ranges over which each method remains valid are not well-characterized for these specific chromophores.

### Suggested Next Steps

- Design a benchmark phantom set with systematically varied Hb, HbO₂, and bilirubin concentrations in Lipofundin.
- Measure both integrating-sphere (for IAD) and fiber-probe diffuse reflectance (for KM and MC-LUT).
- Compare extracted concentrations from IAD+linear unmixing vs. KM direct inversion vs. MC-LUT vs. PLS.
- Quantify the minimum detectable concentration and cross-talk between chromophores for each method.
