# Background Model Research

## Goal

Determine how to change the current spectral unmixing model so that the **Background** term matters continuously, instead of acting like a binary switch (`0` vs nonzero).

## Current Situation In This Repo

The current overlap matrix builder in [app/core/processing.py](../app/core/processing.py) appends the background term as a constant column:

```python
if include_background:
    A[i, -1] = background_value
```

This means the background basis vector is:

- `[2500, 2500, 2500, ...]^T` when `background_value = 2500`
- `[100, 100, 100, ...]^T` when `background_value = 100`

Those are the same direction in the linear system. One is just a rescaled copy of the other.

In least-squares or NNLS, a rescaled column can be offset by an inversely rescaled coefficient, so the fitted signal does not change. The practical consequence is:

- `background_value = 0` changes the model
- any nonzero `background_value` acts like "background enabled"

So the current control is mathematically closer to **on/off** than a meaningful continuous parameter.

## Research Findings

### 1. Best Physical Interpretation: Background As Scattering

In tissue diffuse reflectance spectroscopy, wavelength dependence is commonly decomposed into:

- absorption from chromophores
- scattering from tissue structure

The reduced scattering coefficient is often modeled as a power law:

```text
μs'(λ) = A (λ / 500)^(-B)
```

where:

- `A` = scattering amplitude
- `B` = scattering power

This is important because `A` and `B` change the **shape** of the spectrum across wavelength. Unlike a constant background column, they are not trivially removable by coefficient rescaling.

Implication for this repo:

- the current "Background" should likely represent a **scattering term**
- the UI value should control a physically meaningful parameter such as scattering amplitude, not a constant OD offset

Relevant sources:

- Song et al., diffuse reflectance model with absorption and scattering power law  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC5231317/
- Comparative study of diffuse reflectance models in tissue  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7618019/
- Skin diffuse reflectance with scattering power-law model  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6975185/

### 2. Best Low-Risk Linear Fix: Background As A Small Basis, Not One Constant Column

Spectroscopy preprocessing literature treats nuisance background, pathlength, and scattering effects using a small model basis rather than one scalar constant. Extended multiplicative signal correction (EMSC) is a standard example.

Typical nuisance terms include:

- constant offset
- linear slope
- quadratic curvature
- known interferent spectra

This works because the nuisance/background model has actual spectral structure.

Implication for this repo:

Instead of one background column, use a background basis `B_bg`, for example:

- constant
- centered wavelength
- centered wavelength squared

Then solve:

```text
min ||A_chrom c + B_bg β - y||²
```

This is already better than the current model, because the nuisance space is no longer just one rescaled constant.

Relevant sources:

- Martens and Stark, original EMSC paper  
  https://pubmed.ncbi.nlm.nih.gov/1790182/
- EMSC tutorial-style review and constituent/interferent modeling  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8948808/

### 3. If You Want The UI Scalar To Matter Continuously, It Should Become A Penalty/Prior Strength

If the UI still needs a single scalar named something like `Background value`, it should not scale a basis vector directly.

A much better role is to use it as a **regularization strength** on the nuisance/background coefficients:

```text
min ||A_chrom c + B_bg β - y||² + λ_bg ||β||²
```

Then:

- small `λ_bg` allows the background model to explain more of the signal
- large `λ_bg` suppresses the background model

This makes the parameter genuinely continuous and identifiable in the optimization.

This is an inference from standard regularized least-squares modeling plus the spectroscopy literature above; the cited papers motivate the nuisance-basis approach more directly than the exact ridge form.

### 4. Alternative: Use Fully Constrained Unmixing

Another way to make a background/shade component matter is to impose abundance constraints:

- nonnegativity
- sum-to-one

In that setup, endmembers must compete for a fixed total abundance budget, so a background/shade term meaningfully affects the other abundances.

However, this changes the interpretation of the solution:

- from chromophore concentration-like coefficients
- to abundance fractions

That is a major modeling change and is probably not the right first step for this application.

Relevant source:

- Heinz and Chang, Fully Constrained Least Squares (FCLS)  
  https://researchoutput.ncku.edu.tw/en/publications/fully-constrained-least-squares-linear-spectral-mixture-analysis-

### 5. Why A Simple Additive Constant Is Weak Physically

Beer-Lambert and modified Beer-Lambert formulations do allow additive geometry/intercept-like terms, but those are generally treated as nuisance constants rather than tunable biological components.

The literature also notes that scattering and geometry assumptions are a limitation of simplified Beer-Lambert models.

Implication:

- a constant additive background is not a strong physical model for tissue
- wavelength-dependent scattering is a better candidate

Relevant sources:

- Beer-Lambert limitations review  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8553265/
- Modified Beer-Lambert limitations  
  https://pubmed.ncbi.nlm.nih.gov/16481677/

## Recommendation For This Repo

### Recommended Path

#### Phase 1: Replace The Single Background Column

Replace:

```text
background column = constant * ones
```

with a small nuisance basis over LED wavelengths:

- `b0(λ) = 1`
- `b1(λ) = normalized wavelength`
- optionally `b2(λ) = normalized wavelength²`

Fit these nuisance coefficients jointly with chromophores.

This is the lowest-risk improvement because:

- it keeps the current linear least-squares structure
- it requires minimal UI disruption
- it gives background spectral flexibility

#### Phase 2: Reinterpret The UI Parameter

Rename or repurpose the UI field:

- current: `Background value`
- better: `Background penalty`

Use it as `λ_bg` in a regularized nuisance fit.

This makes the control truly continuous.

#### Phase 3: Move Toward A Scattering Model

Replace the generic nuisance basis with a scattering-inspired basis or directly fit a parameterized scattering term such as:

```text
μs'(λ) = A (λ / 500)^(-B)
```

Practical options:

- fit `A` only, keep `B` fixed
- fit `A` per pixel and `B` globally per sample
- precompute scattering bases for several `B` values and fit them in a low-dimensional model

This is the most physically meaningful direction.

## Concrete Design Options

### Option A: Polynomial Background Basis

Model:

```text
y ≈ A_chrom c + [1, λ, λ²] β
```

Pros:

- easiest to implement
- continuous background flexibility
- no major pipeline rewrite

Cons:

- not directly physical
- can absorb real chromophore structure if the basis is too flexible

### Option B: Regularized Background Basis

Model:

```text
min ||A_chrom c + B_bg β - y||² + λ_bg ||β||²
```

Pros:

- UI scalar becomes meaningful
- background contribution can be tuned smoothly
- still computationally cheap

Cons:

- `λ_bg` needs calibration
- still only semi-physical

### Option C: Scattering Power-Law Model

Model idea:

```text
OD(λ) ≈ chromophore_terms + scattering_terms
```

with scattering derived from a wavelength-dependent law rather than a constant column.

Pros:

- physically motivated
- background/scattering parameter has biological meaning
- strongest long-term direction

Cons:

- requires model redesign
- may need more careful identifiability checks with the limited number of LED bands

### Option D: Fully Constrained Abundance Model

Model idea:

- treat chromophores + background as competing mixture components
- enforce nonnegativity and sum-to-one

Pros:

- background necessarily matters

Cons:

- output semantics change substantially
- likely not appropriate if the goal is concentration-like maps

## Practical Constraint For This Dataset

Your system appears to use a small number of LED bands. That means the nuisance/background model must remain low-dimensional.

Recommended limit:

- 1 to 2 background degrees of freedom initially
- 3 at most without strong validation

Too many nuisance terms will simply absorb chromophore signal and make the inversion unstable.

## Suggested Next Step

Implement **Option B** first:

1. replace the single constant background column with a small wavelength basis
2. add ridge regularization on background coefficients
3. reinterpret the UI scalar as `Background penalty`
4. validate whether chromophore maps respond smoothly as the penalty changes

After that, if the behavior is promising, move toward **Option C** and make the parameter scattering-based instead of generic background-based.

## Summary

The current background term fails because it is a single constant column whose scale can always be canceled by the fitted coefficient. To make background matter, the model must change so that background has:

- wavelength structure
- constraints
- or a regularized role in the objective

The most practical near-term solution for this repo is:

- **small background basis + regularization**

The most physically meaningful long-term solution is:

- **explicit scattering model**
