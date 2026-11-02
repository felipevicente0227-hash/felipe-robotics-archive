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
| 3 | Body in arena, senses → brain → legs | done |
| 4 | Record every spike (parquet) | done |
| 5 | Neuron map (HTML + PNG) | done |
| 6 | Video: fly + brain side by side | – |

---

## How to rerun everything

```bash
cd fruit-fly-brain-sim
bash scripts/setup.sh                 # Phase 1: venv + downloads (~2 min)
.venv/bin/python src/prepare_data.py  # Phase 1: build neuron table + connectome matrix (~20 s)
.venv/bin/python src/phase2_brain_only.py --trials 5 --brian2   # Phase 2 (~2 min; drop --brian2 for ~15 s)
MUJOCO_GL=egl .venv/bin/python src/closed_loop.py --seconds 3 --name demo_heading-10      # Phase 3 (~3 min)
MUJOCO_GL=egl .venv/bin/python src/closed_loop.py --seconds 1.5 --spawn 3.6 2.6 0 --name taste_test
MUJOCO_GL=egl .venv/bin/python src/phase4_record.py --seconds 10                         # Phase 4 main run (~7 min)
.venv/bin/python src/phase5_map.py                                                       # Phase 5 (~15 s)
```
Headless rendering needs EGL: `apt-get install libegl1 libgl1-mesa-dri libosmesa6 ffmpeg`.

## Folder layout

```
scripts/setup.sh        install + download (data goes to data/raw/, not committed)
src/brain.py            fast numba spiking engine (Shiu et al. model, steppable)
src/phase2_brain_only.py  1 s brain-only test + Brian2 comparison
src/sensors.py          senses -> sensory neuron IDs (smell, taste, vision, touch)
src/closed_loop.py      arena + body + brain loop + motor decoder
src/phase4_record.py    main 10 s closed-loop run, saves every spike
src/phase5_map.py       neuron map (HTML + PNG)
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

### Phase 3 – Body in a closed arena, closed loop (2026-11-02)

**Arena** (`src/closed_loop.py`): flat floor, four walls at ±12 mm (the fly is ~2.5 mm
long), one yellow sugar disc (radius 2 mm at x=5, y=3) that also emits a food odor
(concentration = 1 / (1 + (distance / 6 mm)²)). Body = NeuroMechFly (FlyGym 2.1.1),
legs position-controlled, adhesion on, MuJoCo step 0.1 ms.

**The loop** (every 5 ms of simulated time): read senses → set sensory neuron rates →
brain 5 ms (50 × 0.1 ms) → read descending neurons → body 5 ms (50 physics steps).

**Senses → sensory neurons** (`src/sensors.py`)

| Sense | Body measurement | Neurons driven (FlyWire v783) | Rate |
|---|---|---|---|
| Smell | odor at the left / right antenna (funiculus) | 207 food-odor ORNs (glomeruli DM1, DM4, DP1m, VA2) of that antenna | 60 Hz × concentration |
| Taste | mouth (haustellum) over the sugar disc | 20 sugar GRNs (Shiu et al. list) | 100 Hz |
| Vision | FlyGym compound eyes, 721 ommatidia/eye, every 20 ms | 8,712 photoreceptors (R1-6, R7, R8), each fed by the ommatidium at its eye column | 5 Hz × light + 400 × change in light (max 100 Hz) |
| Touch | head within 0.6 mm of a wall (side facing it) | head / antenna bristle neurons BM_InOm, BM_Ant, BM_Fr | 50 Hz |

Retinotopy: R7/R8 eye columns come from the Codex `column_assignment` table; R1-6 inherit
the column of the lamina neuron (L1/L2/L3) they synapse onto most. Columns and
ommatidia are matched by nearest neighbour after aligning both grids on their long
axis — left/right eye is exact, orientation inside an eye is approximate.

**Descending neurons → body** (FlyGym's `HybridTurningController` = CPG + leg reflexes,
playing the role of the ventral nerve cord; it takes a left and a right drive):

| Brain signal | Effect |
|---|---|
| mean rate of DNa01, DNa02, DNb05, DNp09 | walking speed (on top of a slow default pace 0.4) |
| left − right change of DNa01 + DNa02 (they cause ipsilateral turns) | turning |
| MDN ("moonwalker") | backward walking |
| MN9 (proboscis / feeding motor neuron) | stop walking and feed |

**Tests**
- ✅ Taste test (`outputs/phase3/taste_test`): fly placed with mouth on sugar → MN9 fires
  32–39 Hz → drive goes to 0 → the fly stops and stays on the sugar.
- ✅ Demo (`outputs/phase3/demo_heading-10`, 3 s): fly starts at (−3, −2) heading −10°,
  walks up the odor gradient (odor 0.33 → 0.97), mouth reaches the sugar at ~1.0 s,
  MN9 rises to 35–88 Hz and it stops to feed for the rest of the run.
- ✅ Walls block the fly (they had to be registered as contact geoms – first try the fly
  walked straight through them).
- Speed: **~57 s of computer time per simulated second** (body/physics 70 %, senses 12 %
  incl. eye rendering, brain only ~6 %).

**What failed / what we changed (important)**
1. ❌ **Odor runaway.** With the plain Shiu model, *any* odor input (even 5 Hz into 32 ORNs)
   switched on the same ~10,000 neurons (4,000 Kenyon cells) and the activity kept
   going after the odor was removed. MN9 was suppressed to ~2 Hz, so the fly could not
   feed. Cause: antennal-lobe local neurons (lLN1_bc, v2LN30 …) – mostly GABAergic in real
   flies – have predicted neurotransmitters of ACh/dopamine/serotonin in FlyWire, so 65 %
   of their synapses were excitatory, turning the smell circuit's brakes into an
   accelerator. **Fix:** `Brain(fix_al_ln_sign=True)` makes all 429 `ALLN` neurons
   inhibitory. Result: graded odor responses (1,000–1,500 active neurons), sparse Kenyon
   cells (4–186), activity fades when the odor stops, MN9 back to 70–82 Hz with sugar.
   Phase 2 numbers use the unmodified model.
   (Cutting Kenyon-cell→Kenyon-cell synapses was tried first – it did not help.)
2. ⚠️ **Steering is weak and biased.** Smell neurons project to both brain sides, so a
   left/right odor difference barely changes DNa01/DNa02. These neurons are also very
   asymmetric (left ~80 Hz, right ~4 Hz for symmetric input). The decoder therefore
   uses changes relative to each side's recent mean (0.5 s adaptation) plus a 0.5 s
   brain warm-up. There is still a mild left drift. The fly reaches the sugar from the
   chosen start (heading −10°); from headings 0° and +5° it passes ~3 mm left of the
   sugar and ends at the north wall (`outputs/phase3/heading0_console.log`).
   **The start pose was chosen so the path crosses the sugar; this is not robust odor
   tracking.**
3. ⚠️ **Vision and touch are wired but have no motor effect.** Photoreceptor input
   activates ~4,000 optic-lobe neurons but no descending neuron; head-bristle input
   reaches no MDN/steering neuron. So at a wall the fly keeps pushing instead of
   turning/backing up. This is how the brain-only model behaves (no visual motion →
   steering pathway emerges with these LIF parameters); no hand-made reflex was added.
4. ❌ MuJoCo EGL/OSMesa libraries were missing in the container → installed with apt.

### Phase 4 – Recording every neuron (2026-11-02)

Main run: 10 simulated seconds, seed 0, default arena and start pose (−3, −2, heading −10°),
with smell, taste, vision and touch on. Took **6.7 min** (body 309 s, senses 43 s, brain 30 s),
well under the 1-hour budget, so the duration was not shortened.

| File (`outputs/phase4/`) | Content | Size |
|---|---|---|
| `spikes.parquet` | **every spike**: `neuron_idx`, `root_id` (FlyWire ID), `t_ms`; sorted by neuron then time; zstd | 2.6 MB |
| `neurons.parquet` | all 138,639 neurons + `spike_count`, `rate_hz` for this run | 3.0 MB |
| `behaviour.csv` | every 5 ms: position, heading, odor L/R, taste, touch, DN rates, MN9, drive | 0.2 MB |
| `video/topcam.mp4`, `video/nmf_trackcam.mp4` | raw body videos (0.25× speed, 1 frame per 10 ms) | 5.3 MB |
| `run_info.json`, `console.log` | settings, timings, summary | – |

Results: **1,033,833 spikes**; 11,281 neurons (8.1 %) fired at least once; mean 0.75 Hz over
the whole brain. The fly walked up the odor gradient, its mouth reached the sugar at
**0.96 s**, MN9 rose to 35–110 Hz and it stopped to feed for the rest of the run (small
shuffle at ~8.3 s).

Read the spikes back:
```python
import pandas as pd
spk = pd.read_parquet("outputs/phase4/spikes.parquet")
spk[spk.root_id == 720575940660219265].t_ms   # MN9 spike times (ms)
```
The script re-reads the file after writing and checks the spike count matches (✅).
If a future longer run makes the file >80 MB, it is automatically split into
`spikes_partNN.parquet` files (same columns).

### Phase 5 – Neuron map (2026-11-02)

`outputs/phase5/` – all 138,639 neurons, coloured by log10(1 + firing rate) in the phase 4 run.

| File | What it shows |
|---|---|
| `neuron_map.html` (20 MB, open in a browser) | three interactive views; hover any neuron → cell type, class, region, side, neurotransmitter, rate, FlyWire ID |
| `map_anatomy.png` | every neuron at its real 3D position (front + top view) |
| `map_grid.png` | one pixel per neuron; blocks = 15 brain regions; inside a block sorted by super class → cell class → cell type |
| `map_treemap.png` | region → cell class → cell type; box size = number of neurons, colour = mean rate |
| `region_summary.csv` | neurons / active / mean / max rate per region |

What the map shows for this run: the optic lobes hold most active neurons (9,052 – the
photoreceptors and their first partners, driven by vision); antennal lobe (mean 5.6 Hz),
lateral complex (4.4 Hz), lateral horn (3.3 Hz) and inferior neuropils (3.1 Hz) are the
most active central regions (smell → taste → feeding pathways). The ocellar ganglion is
silent (ocelli are not simulated).

Notes
- 2,451 R1-6 + ~600 R7/R8 photoreceptors had no annotated neuropil ("Unassigned"); they are
  now counted as **Optic lobe** (rule added to `prepare_data.py` and `phase5_map.py`;
  the `region` column in `outputs/phase4/neurons.parquet` predates this rule).
- First HTML version was 47 MB (hover text repeated for 139k points × 2 plots). Now one
  compact lookup table + a small JS tooltip → 20 MB (4.8 MB of it is plotly.js itself).
- Treemap PNG is a screenshot taken with the pre-installed Chromium via Node Playwright.
- Checked in headless Chromium: 3 plots render, no JS errors, tooltips show.

## Big files (never committed)
- `Connectivity_783.parquet` is 100 MB and `connectome.npz` is 51 MB → both live in the
  git-ignored `data/` folder and are re-created by the two commands above.
