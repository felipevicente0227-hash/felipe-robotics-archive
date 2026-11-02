# Fruit-fly brain → body closed loop

A whole adult fruit-fly brain (FlyWire v783 connectome, **138,639 neurons, 15.1 M
connections, 54.5 M synapses**) runs as a spiking network and drives a
physics-simulated fly body (FlyGym 2 / NeuroMechFly in MuJoCo) inside a closed arena
with a sugar spot.

Built in phases. Each phase is finished, tested and committed before the next.

| Phase | What | Status |
|---|---|---|
| 1 | Setup: software + connectome download | done |
| 2 | Brain only, 1 s simulated | – |
| 3 | Body in arena, senses → brain → legs | – |
| 4 | Record every spike (parquet) | – |
| 5 | Neuron map (HTML + PNG) | – |
| 6 | Video: fly + brain side by side | – |

---

## How to rerun everything

```bash
cd fruit-fly-brain-sim
bash scripts/setup.sh                 # Phase 1: venv + downloads (~2 min)
.venv/bin/python src/prepare_data.py  # Phase 1: build neuron table + connectome matrix (~20 s)
```

## Folder layout

```
scripts/setup.sh        install + download (data goes to data/raw/, not committed)
src/prepare_data.py     merges the tables -> data/work/neurons.parquet + connectome.npz
data/raw/, data/work/   downloaded / generated data (git-ignored, see "Big files")
outputs/                small results that ARE committed
```

---

## Log

### Phase 1 – Setup (2026-11-02)

**Machine:** cloud container, 4 CPU cores, 15 GB RAM, no GPU. Python 3.13.

**Software installed** (`requirements.txt`): flygym 2.1.1, mujoco 3.16.0,
brian2 2.11.0, numba 0.68.1, pandas, pyarrow, h5py, plotly. Install took ~75 s with `uv`.

**Data sources**

| Data | From | Notes |
|---|---|---|
| Neuron list + connectivity (with excitatory/inhibitory sign) | `github.com/philshiu/Drosophila_brain_model` (`Completeness_783.csv`, `Connectivity_783.parquet`) | exactly the inputs of Shiu et al. 2024 |
| Cell types, super classes, side, predicted neurotransmitter | `github.com/flyconnectome/flywire_annotations` (Supplemental file 1) | Schlegel et al. 2024 |
| Neurotransmitter type, per-neuropil synapse counts, 3D positions | FlyWire Codex public bucket `storage.googleapis.com/flywire-data/codex/data/fafb/783/` | same files codex.flywire.ai serves |

**What `prepare_data.py` produces**
- `neurons.parquet` – one row per neuron: ID, super class, cell class, cell type,
  neurotransmitter, side, dominant neuropil, coarse brain region, x/y/z (µm).
  "Region" = the neuropil holding most of the neuron's synapses, grouped into 15 standard
  FlyWire super-regions (Optic lobe 90,120 · Ventrolateral 8,088 · Superior 6,952 ·
  SEZ/GNG 5,217 · Mushroom body 5,170 · … · Unassigned 4,462).
- `connectome.npz` – sparse matrix W[post, pre] = synapse count × sign (+1 for ACh,
  −1 for GABA/glutamate), same convention as Shiu et al.

**What worked / what failed**
- ✅ `git clone` from GitHub and the Codex Google-Cloud bucket work through the proxy.
- ❌ `codex.flywire.ai`, `zenodo.org` and the GitHub web pages are blocked here, so the
  Codex API download route could not be used — the bucket above holds the same files.
- ✅ 138,625 / 138,639 neurons have annotations; 286 have no neurotransmitter label.

## Big files (never committed)
- `Connectivity_783.parquet` is 100 MB and `connectome.npz` is 51 MB → both live in the
  git-ignored `data/` folder and are re-created by the two commands above.
