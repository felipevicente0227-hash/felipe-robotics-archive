# Fruit-fly brain → body closed loop

A whole adult fruit-fly brain (FlyWire v783 connectome, **138,639 neurons, 15.1 M
connections, 54.5 M synapses**) runs as a spiking network and drives a
physics-simulated fly body (FlyGym 2 / NeuroMechFly in MuJoCo) inside a closed arena
with a sugar spot.

Built in phases. Each phase is finished, tested and committed before the next.

| Phase | What | Status |
|---|---|---|
| 1 | Setup: software + connectome download | done |
| 2 | Brain only, 1 s simulated | done |
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
.venv/bin/python src/phase2_brain_only.py --trials 5 --brian2   # Phase 2 (~2 min; drop --brian2 for ~15 s)
```

## Folder layout

```
scripts/setup.sh        install + download (data goes to data/raw/, not committed)
src/brain.py            fast numba spiking engine (Shiu et al. model, steppable)
src/phase2_brain_only.py  1 s brain-only test + Brian2 comparison
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

### Phase 2 – Brain only, 1 simulated second (2026-11-02)

**Model.** Exactly the Shiu et al. 2024 leaky integrate-and-fire model: resting/reset −52 mV,
threshold −45 mV, membrane 20 ms, synapse 5 ms, refractory 2.2 ms, delay 1.8 ms,
0.275 mV per synapse, dt 0.1 ms. Inputs are Poisson spike trains that force a spike
(same as the paper's `PoissonInput`).

**Engine choice.** Brian2 works but is slow on this machine, and it cannot easily be
paused every few ms to talk to a body. So `src/brain.py` re-implements the same equations
in **numba** (compiled Python), integrated exactly between time steps, with a ring buffer
for the 1.8 ms synaptic delay. It can be advanced in small chunks → ready for the closed loop.

**Test.** 20 right-side sugar taste neurons driven at 100 Hz for 1 s (the paper's example
experiment). One sugar ID from the old v630 list is not in v783 and is skipped.

| | Brian2 (original `model.py`, cython) | numba engine (ours) |
|---|---|---|
| Build network | 5 s | 1.7 s (load) |
| **Run 1 s of brain time** | **70 s** | **1.7 s** (≈ 41× faster) |
| Active neurons | 354 | 391 (mean of 5 trials) |
| MN9 (proboscis motor neuron) rate | 71.0 Hz | 71.2 Hz |
| Rate correlation between engines | 0.96 | |

- ✅ MN9 fires when sugar neurons fire → reproduces the paper's key result (sugar → feeding).
- ✅ With no input the whole brain stays silent (0 spikes) – expected: the model has no
  spontaneous activity, so in the closed loop all activity must come from the senses.
- Results: `outputs/phase2/phase2_log.json`, `outputs/phase2/top30_sugar_100Hz.csv`.

## Big files (never committed)
- `Connectivity_783.parquet` is 100 MB and `connectome.npz` is 51 MB → both live in the
  git-ignored `data/` folder and are re-created by the two commands above.
