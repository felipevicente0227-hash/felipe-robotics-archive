#!/usr/bin/env bash
# Phase 1 - install the software and download the FlyWire v783 connectome.
# Run from the fruit-fly-brain-sim folder:  bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1) Python environment (uv is fast; falls back to python -m venv + pip)
if command -v uv >/dev/null; then
  uv venv -q .venv --python 3.13 || true
  uv pip install --python .venv/bin/python -r requirements.txt
else
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

mkdir -p data/raw
cd data/raw

# 2) Shiu et al. 2024 brain model (code + v783 connectivity with E/I signs)
if [ ! -d Drosophila_brain_model ]; then
  git clone --depth 1 https://github.com/philshiu/Drosophila_brain_model.git
fi

# 3) FlyWire neuron annotations (cell types, super classes, neurotransmitters, side)
if [ ! -d flywire_annotations ]; then
  git clone --depth 1 https://github.com/flyconnectome/flywire_annotations.git
fi

# 4) FlyWire Codex v783 tables (public Google Cloud bucket used by codex.flywire.ai)
CODEX=https://storage.googleapis.com/flywire-data/codex/data/fafb/783
for f in neurons.csv.gz classification.csv.gz neuropil_synapse_table.csv.gz coordinates.csv.gz; do
  [ -f "codex_$f" ] || curl -fsSL -o "codex_$f" "$CODEX/$f"
done
echo "Setup done. Data in data/raw/"
