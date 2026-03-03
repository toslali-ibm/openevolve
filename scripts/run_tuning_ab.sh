#!/bin/bash
# Run tuning A/B experiment with rotating treatment/control order.
# Usage: bash scripts/run_tuning_ab.sh <task_name> <output_dir> [iterations]
set -e

TASK="$1"
OUTDIR="$2"
ITERS="${3:-25}"

echo "=== Tuning A/B: $TASK ==="
echo "Order: treatment_300 → control_300 → treatment_301 → control_301"
echo "Iterations per run: $ITERS"
echo ""

# Run 1: treatment seed 300
echo "[1/4] treatment seed=300"
python scripts/run_experiment.py --task "$TASK" --condition treatment --runs 1 --seed-start 300 --iterations "$ITERS" --output-dir "$OUTDIR"

# Run 2: control seed 300
echo "[2/4] control seed=300"
python scripts/run_experiment.py --task "$TASK" --condition control --runs 1 --seed-start 300 --iterations "$ITERS" --output-dir "$OUTDIR"

# Run 3: treatment seed 301
echo "[3/4] treatment seed=301"
python scripts/run_experiment.py --task "$TASK" --condition treatment --runs 1 --seed-start 301 --iterations "$ITERS" --output-dir "$OUTDIR"

# Run 4: control seed 301
echo "[4/4] control seed=301"
python scripts/run_experiment.py --task "$TASK" --condition control --runs 1 --seed-start 301 --iterations "$ITERS" --output-dir "$OUTDIR"

# Merge convergence data from all run directories into a single CSV
echo ""
echo "Merging convergence data..."
python3 -c "
import json, csv
from pathlib import Path

outdir = Path('$OUTDIR')
rows = []
for run_dir in sorted(outdir.glob('*_run_*')):
    if not run_dir.is_dir():
        continue
    parts = run_dir.name.rsplit('_run_', 1)
    condition = parts[0]
    seed = int(parts[1])
    cp_dir = run_dir / 'checkpoints'
    if not cp_dir.exists():
        continue
    for cp in sorted(cp_dir.iterdir()):
        if not cp.is_dir():
            continue
        info = cp / 'best_program_info.json'
        if info.exists():
            data = json.loads(info.read_text())
            metrics = data.get('metrics', data)
            iteration = int(cp.name.split('_')[-1]) if '_' in cp.name else 0
            score = metrics.get('combined_score', metrics.get('overall_score', 0))
            rows.append({
                'condition': condition, 'seed': seed,
                'iteration': iteration, 'best_combined_score': score,
            })

csv_path = outdir / 'convergence.csv'
with open(csv_path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['condition','seed','iteration','best_combined_score'])
    w.writeheader()
    w.writerows(rows)
print(f'Merged {len(rows)} rows -> {csv_path}')
"

echo ""
echo "=== $TASK A/B experiment complete ==="
echo "Run: python scripts/analyze_experiment.py --data $OUTDIR/convergence.csv --output $OUTDIR"
