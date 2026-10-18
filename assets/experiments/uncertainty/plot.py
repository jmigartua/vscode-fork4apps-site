"""Render the captured mass-calibration results; does not repeat the calculations."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt

root = Path(__file__).resolve().parents[2]
report = json.loads((root / 'audit/uncertainty-candidate-check.json').read_text())
rows = [r for r in report['results'] if r['case'] == 'mass-calibration']
labels = [r['engine'] + (' · first order' if r['method'] == 'first-order' else ' · sampling') for r in rows]
plt.rcParams.update({'font.size': 11, 'svg.fonttype': 'none'})
fig, ax = plt.subplots(figsize=(8, 4.6), layout='constrained')
ax.barh(labels, [r['u'] for r in rows], color=['#91999b']*3+['#287475']*2, height=.6)
ax.invert_yaxis()
ax.axvline(.0754, color='#a06914', linestyle='--', label='Published MCM reference: 0.0754 mg')
for i, row in enumerate(rows):
    ax.text(row['u']+.001, i, f"{row['u']:.5f}", va='center', fontsize=10)
ax.set(xlim=(0, .091), xlabel='Standard uncertainty / mg')
fig.suptitle('Mass calibration: first-order and sampling results', fontsize=12)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), frameon=False, fontsize=9)
destination = root / 'ecosystem/site/assets/examples'
for extension in ['svg', 'png']:
    fig.savefig(destination / ('uncertainty-comparison.'+extension), dpi=160)
plt.close(fig)
