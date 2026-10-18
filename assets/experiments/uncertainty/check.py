"""Bounded candidate audit, not an application adapter or a GUM compliance test.

Only fixed, trusted models below reach the libraries. No user expression is evaluated.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
import os
import platform
import subprocess
import sys
import warnings
from pathlib import Path

import GTC
import mcerp
import numpy as np
from scipy import stats
from suncal import Model
from uncertainties import correlated_values, covariance_matrix, ufloat

ROOT = Path(__file__).resolve().parents[2]
SEEDS = [101, 202, 303]
# Normal entries contain standard deviations; uniform entries contain half-widths.
MASS = [('m', 100000., .050, 'normal'), ('d', 1.234, .020, 'normal'),
        ('a', 1.20, .10, 'uniform'), ('w', 8000., 1000., 'uniform'),
        ('r', 8000., 50., 'uniform')]
LINE = [('x', 10., 1., 'normal'), ('y', 20., 2., 'normal')]
CASES = {
    'independent': (LINE, None, 'x+2*y', lambda x, y: x+2*y, (50., math.sqrt(17))),
    'positive-correlation': (LINE, [[1., .75], [.75, 1.]], 'x+2*y', lambda x, y: x+2*y, (50., math.sqrt(23))),
    'negative-correlation': (LINE, [[1., -.75], [-.75, 1.]], 'x+2*y', lambda x, y: x+2*y, (50., math.sqrt(11))),
    'shared-cancellation': (LINE + [('c', 0., 5., 'normal')], None, '(x+c)-(y+c)', lambda x, y, c: (x+c)-(y+c), (-10., math.sqrt(5))),
    'square-at-zero': ([('x', 0., 1., 'normal')], None, 'x**2', lambda x: x*x, (0., 0.)),
    'mass-calibration': (MASS, None, '(m+d)*(1+(a-1.2)*(1/w-1/r))-100000', lambda m, d, a, w, r: (m+d)*(1+(a-1.2)*(1/w-1/r))-100000, (1.234, math.sqrt(.05**2+.02**2))),
}


def sun_model(inputs, correlation, expression):
    model = Model('f=' + expression)
    for name, mean, scale, dist in inputs:
        var = model.var(name)
        if var is None:  # Symbolic simplification removes cancelling/unused inputs.
            continue
        var.measure(mean)
        var.typeb(dist=dist, **({'std': scale} if dist == 'normal' else {'a': scale}))
    if correlation is not None:
        for i in range(len(inputs)):
            for j in range(i):
                if model.var(inputs[i][0]) is not None and model.var(inputs[j][0]) is not None:
                    model.variables.correlate(inputs[i][0], inputs[j][0], correlation[i][j])
    return model


def linearized(engine, inputs, correlation, expression, function):
    means = [x[1] for x in inputs]
    sd = np.array([x[2] if x[3] == 'normal' else x[2]/math.sqrt(3) for x in inputs])
    corr = np.eye(len(inputs)) if correlation is None else np.array(correlation)
    if engine == 'GTC':
        values = [GTC.ureal(mu, u, independent=False) for mu, u in zip(means, sd)]
        for i in range(len(values)):
            for j in range(i):
                GTC.set_correlation(corr[i, j], values[i], values[j])
        result = function(*values)
        return {'estimate': result.x, 'u': result.u}
    if engine == 'uncertainties':
        values = correlated_values(means, corr * np.outer(sd, sd))
        result = function(*values)
        return {'estimate': result.nominal_value, 'u': result.std_dev}
    result = sun_model(inputs, correlation, expression).calculate_gum()
    return {'estimate': float(result.expected['f']), 'u': float(result.uncertainty['f'])}


def sampled(engine, inputs, correlation, expression, function, count, seed):
    # Both tested versions use NumPy's legacy global RNG. Isolate process in an adapter.
    np.random.seed(seed)
    extra = {}
    if engine == 'Suncal':
        result = sun_model(inputs, correlation, expression).monte_carlo(samples=count)
        samples = np.asarray(result.samples['f'], dtype=float)
        estimate, u = float(result.expected['f']), float(result.uncertainty['f'])
        extra['library_warnings'] = result.warns
        extra['input_samples'] = {k: len(v) for k, v in result.varsamples.items()}
        if len(samples) and np.isfinite(samples).all():
            interval = result.expand('f', shortest=True, conf=.95)
            extra['shortest_95'] = [float(interval.low), float(interval.high)]
    else:
        mcerp.npts = count
        values = [mcerp.N(mu, scale) if dist == 'normal' else mcerp.U(mu-scale, mu+scale)
                  for _, mu, scale, dist in inputs]
        if correlation is not None:
            mcerp.correlate(values, correlation)
        result = function(*values)
        samples = np.asarray(result._mcpts, dtype=float)  # Version-pinned audit introspection.
        estimate, u = float(result.mean), float(result.std)
        extra['input_samples'] = {v[0]: len(x._mcpts) for v, x in zip(inputs, values)}
        if correlation is not None:
            extra['observed_input_correlation'] = np.corrcoef([x._mcpts for x in values]).tolist()
    finite = np.isfinite(samples)
    return dict(estimate=estimate, u=u, requested=count, returned=len(samples),
                nonfinite_returned=int((~finite).sum()), seed=seed,
                sample_sha256=hashlib.sha256(samples.astype('<f8').tobytes()).hexdigest(),
                equal_tailed_95=np.quantile(samples, [.025, .975]).tolist() if finite.all() and len(samples) else None,
                **extra)


def probe(name, function):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            out = {'outcome': 'returned', 'value': function()}
        except Exception as exc:
            out = {'outcome': 'raised', 'exception': type(exc).__name__, 'message': str(exc)}
    return {'name': name, **out, 'warnings': list(dict.fromkeys(str(x.message) for x in caught))}


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return str(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay-probe', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.replay_probe:
        print(json.dumps({engine: sampled(engine, *CASES['mass-calibration'][:4], 10000, 101)
                          for engine in ['Suncal', 'mcerp']}))
        return
    if args.output is None:
        parser.error('--output is required')
    if os.environ.get('PYTHONHASHSEED') != '0':
        parser.error('Launch with PYTHONHASHSEED=0 to pin Suncal symbolic input ordering')
    checks, results, failures = [], [], []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            failures.append(name)

    for name, (inputs, corr, expr, func, reference) in CASES.items():
        for engine in ['GTC', 'uncertainties', 'Suncal']:
            result = linearized(engine, inputs, corr, expr, func)
            results.append(dict(case=name, engine=engine, method='first-order', **result))
            check(f'{engine}/{name}/first-order', np.allclose([result['estimate'], result['u']], reference, atol=1e-9, rtol=1e-9), reference=reference)
        target = (1., math.sqrt(2)) if name == 'square-at-zero' else (1.2341, .0754) if name == 'mass-calibration' else reference
        # Fixed acceptance thresholds; finite-run agreement, not adaptive convergence.
        tolerance = (.001, .001) if name == 'mass-calibration' else (.03, .04) if name == 'square-at-zero' else (.10, .06)
        for engine in ['Suncal', 'mcerp']:
            result = sampled(engine, inputs, corr, expr, func, 100000, 101)
            results.append(dict(case=name, engine=engine, method='IID Gaussian-copula' if engine == 'Suncal' else 'Latin hypercube / rank correlation', **result))
            check(f'{engine}/{name}/sampled-moments', all(abs(result[k]-v) < t for k, v, t in zip(['estimate', 'u'], target, tolerance)), reference=target, absolute_tolerance=tolerance)
            check(f'{engine}/{name}/sample-accounting', result['returned'] == 100000 and result['nonfinite_returned'] == 0 and all(n == 100000 for n in result['input_samples'].values()))
            if name == 'square-at-zero':
                check(f'{engine}/chi-square-interval', np.allclose(result['equal_tailed_95'], stats.chi2.ppf([.025, .975], 1), atol=.10, rtol=0))

    # Independently derived analytic Jacobian for the published GUM H2 inputs.
    V, I, p = 4.999, .019661, 1.04446
    inputs = [('v', V, .0032, 'normal'), ('i', I, .0000095, 'normal'), ('p', p, .00075, 'normal')]
    corr = np.array([[1, -.36, .86], [-.36, 1, -.65], [.86, -.65, 1]])
    sd = np.array([.0032, .0000095, .00075])
    jac = np.array([[math.cos(p)/I, -V*math.cos(p)/I**2, -V*math.sin(p)/I],
                    [math.sin(p)/I, -V*math.sin(p)/I**2, V*math.cos(p)/I], [1/I, -V/I**2, 0.]])
    expected_u = np.sqrt(np.diag(jac @ (corr*np.outer(sd, sd)) @ jac.T))
    from uncertainties import umath
    for engine in ['GTC', 'uncertainties', 'Suncal']:
        trig = GTC if engine == 'GTC' else umath
        for j, (expr, func) in enumerate([('v*cos(p)/i', lambda v, i, p: v*trig.cos(p)/i), ('v*sin(p)/i', lambda v, i, p: v*trig.sin(p)/i), ('v/i', lambda v, i, p: v/i)]):
            result = linearized(engine, inputs, corr, expr, func)
            results.append(dict(case=f'GUM-H2-{j}', engine=engine, method='first-order', **result))
            check(f'{engine}/GUM-H2-{j}/jacobian', math.isclose(result['u'], expected_u[j], rel_tol=1e-10), reference_u=float(expected_u[j]))

    x, y = GTC.ureal(10, 1, df=9), GTC.ureal(20, 2, df=19)
    z = x+2*y
    df = 17**2/(1/9+16**2/19)
    check('GTC/effective-df-independent', math.isclose(z.df, df, rel_tol=1e-12), actual=z.df, reference=df)
    check('GTC/coverage-factor-independent', math.isclose(GTC.reporting.k_factor(z.df, 95), stats.t.ppf(.975, df), rel_tol=1e-10), actual=GTC.reporting.k_factor(z.df, 95))

    stability = []
    mass = CASES['mass-calibration'][:4]
    for engine in ['Suncal', 'mcerp']:
        for count in [100000, 400000]:
            for seed in SEEDS:
                result = sampled(engine, *mass, count, seed)
                stability.append(dict(engine=engine, **result))
                check(f'{engine}/mass-stability/{count}/{seed}', abs(result['estimate']-1.2341)<.001 and abs(result['u']-.0754)<.001)
        repeat = sampled(engine, *mass, 100000, 101)
        first = next(r for r in stability if r['engine'] == engine and r['requested'] == 100000 and r['seed'] == 101)
        second = next(r for r in stability if r['engine'] == engine and r['requested'] == 100000 and r['seed'] == 202)
        check(f'{engine}/repeat-seed', repeat['sample_sha256'] == first['sample_sha256'])
        check(f'{engine}/different-seed', second['sample_sha256'] != first['sample_sha256'])

    # Suncal constructs input symbols from a set. A NumPy seed alone is insufficient
    # for replay in another Python process. Probe fresh processes, not just reseeding.
    replays = []
    for hash_seed in ['0', '0', '1']:
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        output = subprocess.check_output([sys.executable, __file__, '--replay-probe'], env=env, text=True, timeout=120)
        replays.append({'python_hash_seed': hash_seed, 'results': json.loads(output)})
    for engine in ['Suncal', 'mcerp']:
        check(f'{engine}/fresh-process-replay', replays[0]['results'][engine]['sample_sha256'] == replays[1]['results'][engine]['sample_sha256'])

    raw = []
    invalid_corr = [[1, .9, .9], [.9, 1, -.9], [.9, -.9, 1]]
    three = LINE + [('z', 0., 1., 'normal')]
    for engine in ['GTC', 'uncertainties', 'Suncal']:
        raw.append(probe(engine+'/non-PSD', lambda e=engine: linearized(e, three, invalid_corr, 'x+y+z', lambda x, y, z: x+y+z)))
        constructors = {'GTC': lambda: str(GTC.ureal(0, -1)), 'uncertainties': lambda: str(ufloat(0, -1)), 'Suncal': lambda: float(sun_model([('x', 0., -1., 'normal')], None, 'x').var('x').uncertainty)}
        raw.append(probe(engine+'/negative-sd', constructors[engine]))
        raw.append(probe(engine+'/NaN-mean', lambda e=engine: linearized(e, [('x', float('nan'), 1., 'normal')], None, 'x*x', lambda x: x*x)))
        raw.append(probe(engine+'/perfect-correlation', lambda e=engine: linearized(e, [('x', 0., 1., 'normal'), ('y', 0., 1., 'normal')], [[1, 1], [1, 1]], 'x-y', lambda x, y: x-y)))
    for engine in ['Suncal', 'mcerp']:
        raw.append(probe(engine+'/sample-non-PSD', lambda e=engine: sampled(e, three, invalid_corr, 'x+y+z', lambda x, y, z: x+y+z, 10000, 101)))
        raw.append(probe(engine+'/sample-perfect-correlation', lambda e=engine: sampled(e, [('x', 0., 1., 'normal'), ('y', 0., 1., 'normal')], [[1, 1], [1, 1]], 'x-y', lambda x, y: x-y, 10000, 101)))
        raw.append(probe(engine+'/invalid-domain', lambda e=engine: sampled(e, [('x', 0., 1., 'normal')], None, 'sqrt(x)', lambda x: x**.5, 10000, 101)))
    raw.append(probe('uncertainties/non-PSD-reconstructed-covariance', lambda: covariance_matrix(correlated_values([0., 0., 0.], invalid_corr))))
    versions = {d.metadata['Name']: d.version for d in metadata.distributions()}
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.iterdir()) if p.is_file()}
    report = dict(schema=1, scope='Numerical candidate audit only; no constructor admission or standards certification',
                  environment=dict(python=platform.python_version(), system=platform.system(), machine=platform.machine(), packages=versions,
                                   python_hash_seed=os.environ['PYTHONHASHSEED'], numpy_rng=np.random.get_state()[0]),
                  source_hashes=source_hashes, references=dict(mass='JCGM 101:2008 section 9.3, equation 24, Tables 5 and 6', h2='GTC GUM_H2 example; analytical Jacobian comparison'),
                  results=results, stability=stability, fresh_process_replays=replays, raw_failure_probes=raw,
                  checks=checks, passed=not failures, failed_checks=failures,
                  limitations=['No editor integration, cancellation, journal, migration or omission qualification.',
                               'Fixed seeds and thresholds do not certify adaptive convergence or arbitrary joint distributions.',
                               'First-order square-at-zero result is an applicability failure, not an arithmetic defect.',
                               'MC equal-tailed intervals must not be compared to published shortest intervals.',
                               'Raw failure probes record library behavior; they are not passing adapter safety checks.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(clean(report), indent=2, allow_nan=False)+'\n')
    print(json.dumps({'checks': len(checks), 'passed': not failures, 'failed': failures, 'failure_probes': len(raw)}))
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
