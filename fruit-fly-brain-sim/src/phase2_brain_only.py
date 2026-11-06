"""Phase 2 - whole brain, no body, 1 simulated second.

Same experiment as the Shiu et al. example notebook: the 21 right-side sugar
gustatory neurons are driven at 100 Hz Poisson. Without any input the model is
silent (it has no spontaneous activity), so we also run a 'no input' control.

Checks:
  * runs and finishes for 1 s of brain time, logs wall-clock time
  * MN9 (proboscis motor neuron, 720575940660219265) fires - the paper's key result
  * optional: the original Brian2 model, for speed and rate comparison (--brian2)

Run:  .venv/bin/python src/phase2_brain_only.py [--brian2]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from brain import Brain, ROOT, WORK  # noqa: E402

SUGAR_R = [720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
           720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
           720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
           720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
           720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
           720575940611875570]
MN9 = 720575940660219265
OUT = ROOT / "outputs" / "phase2"


def run_numba(rate_hz, t_ms, n_trials, seed0=0):
    t0 = time.time()
    b = Brain(seed=seed0)
    load_s = time.time() - t0
    b.run(1.0)  # JIT compile (first call) - not counted
    rates = np.zeros(b.n)
    walls = []
    for k in range(n_trials):
        b = Brain(seed=seed0 + k) if k else Brain(seed=seed0)
        if rate_hz > 0:
            b.set_inputs(b.idx(SUGAR_R), rate_hz)
        t0 = time.time()
        _, i = b.run(t_ms)
        walls.append(time.time() - t0)
        rates += np.bincount(i, minlength=b.n) / (t_ms / 1000)
    return b, rates / n_trials, load_s, walls


def run_brian2(rate_hz, t_ms):
    """Original Shiu et al. model.py (Brian2), one trial."""
    sys.path.insert(0, str(ROOT / "data/raw/Drosophila_brain_model"))
    import model as shiu
    from brian2 import Network, Hz, ms, prefs
    prefs.codegen.target = "cython"
    p = dict(shiu.default_params, r_poi=rate_hz * Hz, t_run=t_ms * ms)
    comp = pd.read_csv(ROOT / "data/raw/Drosophila_brain_model/Completeness_783.csv", index_col=0)
    flyid2i = {f: i for i, f in enumerate(comp.index)}
    t0 = time.time()
    neu, syn, mon = shiu.create_model(
        ROOT / "data/raw/Drosophila_brain_model/Completeness_783.csv",
        ROOT / "data/raw/Drosophila_brain_model/Connectivity_783.parquet", p)
    poi, neu = shiu.poi(neu, [flyid2i[f] for f in SUGAR_R if f in flyid2i], [], p)
    net = Network(neu, syn, mon, *poi)
    build_s = time.time() - t0
    t0 = time.time()
    net.run(p["t_run"])
    run_s = time.time() - t0
    rates = np.bincount(np.asarray(mon.i), minlength=len(comp)) / (t_ms / 1000)
    return rates, build_s, run_s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brian2", action="store_true", help="also time the original Brian2 model")
    ap.add_argument("--trials", type=int, default=5)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    log = {}

    b, r0, load_s, w0 = run_numba(0, 1000, 1)
    log["no_input"] = {"total_spikes": int(r0.sum()), "wall_s": round(w0[0], 2)}
    print(f"[numba] load {load_s:.1f}s | no input: {int(r0.sum())} spikes, {w0[0]:.2f}s wall")

    b, r, _, walls = run_numba(100, 1000, a.trials)
    mn9 = r[b.idx([MN9])[0]]
    log["sugar_100Hz"] = {
        "trials": a.trials, "wall_s_per_trial": [round(w, 2) for w in walls],
        "active_neurons": int((r > 0).sum()), "mean_rate_active_hz": float(r[r > 0].mean()),
        "MN9_rate_hz": float(mn9), "load_s": round(load_s, 1)}
    print(f"[numba] sugar 100 Hz: {a.trials} x 1 s, wall {np.mean(walls):.2f}s/trial, "
          f"{(r > 0).sum()} active neurons, MN9 = {mn9:.1f} Hz")

    nrn = b.neurons.assign(rate_hz=r)
    top = nrn.sort_values("rate_hz", ascending=False).head(30)
    top[["root_id", "cell_type", "super_class", "region", "rate_hz"]].to_csv(
        OUT / "top30_sugar_100Hz.csv", index=False)
    print(top[["root_id", "cell_type", "super_class", "rate_hz"]].head(15).to_string(index=False))

    if a.brian2:
        rb, build_s, run_s = run_brian2(100, 1000)
        both = (r > 0) | (rb > 0)
        corr = float(np.corrcoef(r[both], rb[both])[0, 1])
        log["brian2"] = {"build_s": round(build_s, 1), "run_s": round(run_s, 1),
                         "active_neurons": int((rb > 0).sum()),
                         "MN9_rate_hz": float(rb[b.idx([MN9])[0]]),
                         "rate_corr_vs_numba": corr}
        print(f"[brian2] build {build_s:.0f}s, run {run_s:.0f}s, active {(rb > 0).sum()}, "
              f"MN9 {rb[b.idx([MN9])[0]]:.1f} Hz, rate correlation vs numba {corr:.3f}")

    (OUT / "phase2_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
