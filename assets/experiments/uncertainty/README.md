# Uncertainty engine audit

This is a numerical qualification experiment, not a constructor package. No
uncertainty dependencies are added to generated applications. Four installed
candidates are exercised: GTC 1.5.1, uncertainties 3.2.3, Suncal 1.7.1 and mcerp
1.1.1. METAS UncLib is a documentation/distribution review only.

## Reproduce

From the repository root, with Python 3.12:

```sh
python3.12 -m venv artifacts/toolchains/uncertainty-audit-python
artifacts/toolchains/uncertainty-audit-python/bin/python -m pip install -r experiments/uncertainty/requirements.txt
PYTHONHASHSEED=0 MPLBACKEND=Agg MPLCONFIGDIR=artifacts/toolchains/uncertainty-mpl-cache artifacts/toolchains/uncertainty-audit-python/bin/python experiments/uncertainty/check.py --output artifacts/experiments/uncertainty-candidates/results.json
```

The first Matplotlib import can build a font cache. Suncal's headless core is used;
its optional Qt GUI is not installed. The requirements lock includes transitive
dependencies. `provenance.json` records retrieved distribution hashes and installed
source/license hashes; platform-specific wheels differ on other operating systems.
The report records its actual environment and experiment source hashes. Each run
is a separate process because both sampling APIs use NumPy's global legacy MT19937 RNG.
Suncal constructs symbolic input order from a set: pin Python's hash seed too.
The harness launches two fresh processes at hash seed 0 to check replay and a
third at hash seed 1 to expose ordering sensitivity. It records each input order.
Never run arbitrary project expressions through this trusted fixed-model harness.

## Cases and tolerances

- Linear normals: independent, correlations +0.75 and -0.75, and cancellation of
  a shared additive input. Means and variances follow analytical formulae.
- GUM H2: resistance, reactance and impedance use the input estimates and
  correlations in the [GTC example](https://gtc.readthedocs.io/en/stable/API/GUM_H2.html).
  Standard uncertainties are checked against an independently written analytic
  Jacobian and matrix covariance product. This does not test correlated finite
  degrees of freedom or expanded uncertainties for that example.
- Independent finite degrees of freedom: GTC is checked against the
  Welch–Satterthwaite expression and SciPy's Student-t coverage factor.
- Squaring a standard normal: first order gives nominal zero and uncertainty
  zero, while the exact output has mean 1 and standard deviation sqrt(2).
  Sampling moments and equal-tailed quantiles are compared with chi-square(1).
  A correct first-order result is an inadequate approximation in this case.
- Mass calibration: [JCGM 101:2008](https://www.bipm.org/documents/20126/2071204/JCGM_101_2008_E.pdf),
  section 9.3, equation 24 and Tables 5–6. Masses are in mg and densities in
  kg/m³. The model is implemented directly in `check.py`; rectangular inputs
  retain the specified half-widths. Reference PDF SHA-256:
  `6d8548af875df112dfc5cf14eb974f5544341f4a31cbbdfc19fc5ed155d8fa20`.
  The full standard is not redistributed here.

First-order checks use 1e-9 absolute/relative tolerance (H2: relative 1e-10).
At 100,000 draws, linear sampling means/u have absolute tolerances 0.10/0.06;
the square case uses 0.03/0.04 and 0.10 for quantile endpoints. Mass means/u
must be within 0.001 mg of the rounded published MCM values 1.2341/0.0754 mg.
These deliberately bounded regression thresholds are fixed in the script,
not fitted to individual runs and not standards accuracy claims.

For mass calibration, seeds 101, 202 and 303 are each run at 100,000 and 400,000
draws per engine. Repeated seed/sample-count runs must reproduce sample hashes;
different seeds must differ. This is a finite stability study, **not** the
JCGM adaptive stopping procedure. Suncal's native shortest interval is recorded
separately from equal-tailed quantiles. Table 6 contains shortest intervals;
the harness does not compare its equal-tailed endpoints to them. mcerp uses
Latin hypercube sampling and rank rearrangement; it is not an IID sampler.

## Failure probes and decisions

The 19 raw probes are observations, not passing adapter safety tests. They
exercise non-positive-semidefinite covariance, negative standard deviation,
NaN estimates, perfect correlation and sqrt of a normal input crossing zero.
Expected library limitations do not turn a numerical comparison green by
silently discarding a case. Unexpected exceptions in the reference suite fail
the process; raw probes preserve returned values, exceptions and warnings.

The authoritative captured results are `audit/uncertainty-candidate-check.json`;
decisions and remaining gates are in `audit/uncertainty-candidate-decisions.json`
and the website's uncertainty guide. No engine has yet passed generated-editor,
cancellation, history, stale-result or constructor omission qualification.
