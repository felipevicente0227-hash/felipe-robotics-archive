"""Phase 4 - the main closed-loop run, recording every spike of every neuron.

Outputs (outputs/phase4/):
  spikes.parquet      one row per spike: neuron_idx (int32), root_id (int64 FlyWire ID),
                      t_ms (float32). Sorted by neuron then time, zstd-compressed.
                      Split into spikes_partNN.parquet files if one would exceed 80 MB.
  neurons.parquet     all 138,639 neurons: IDs, cell type, region, neurotransmitter,
                      position, spike_count, rate_hz in this run
  behaviour.csv       every 5 ms: position, heading, senses, decoded drive, key rates
  video/              raw MuJoCo videos (tracking camera + top camera)
  run_info.json       duration, timings, file sizes

Run:  MUJOCO_GL=egl .venv/bin/python src/phase4_record.py --seconds 10
Read: pd.read_parquet("outputs/phase4/spikes.parquet")
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from closed_loop import run, Arena, ROOT  # noqa: E402

OUT = ROOT / "outputs" / "phase4"
MAX_PART_MB = 80


def save_spikes(t_ms, idx, root_ids, out: Path):
    order = np.lexsort((t_ms, idx))
    tbl = pa.table({"neuron_idx": idx[order].astype(np.int32),
                    "root_id": root_ids[idx[order]].astype(np.int64),
                    "t_ms": t_ms[order].astype(np.float32)})
    for f in out.glob("spikes*.parquet"):
        f.unlink()
    path = out / "spikes.parquet"
    pq.write_table(tbl, path, compression="zstd", compression_level=9)
    mb = path.stat().st_size / 1e6
    if mb <= MAX_PART_MB:
        return [path]
    # too big for git: split by neuron ranges into parts
    path.unlink()
    n_parts = int(np.ceil(mb / MAX_PART_MB)) + 1
    bounds = np.linspace(0, len(tbl), n_parts + 1).astype(int)
    paths = []
    for k in range(n_parts):
        p = out / f"spikes_part{k:02d}.parquet"
        pq.write_table(tbl.slice(bounds[k], bounds[k + 1] - bounds[k]), p,
                       compression="zstd", compression_level=9)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    spk_t, spk_i = [], []

    def on_chunk(t, i, row):
        spk_t.append(t.astype(np.float32))
        spk_i.append(i.astype(np.int32))

    t0 = time.time()
    res = run(a.seconds, vision=True, render=True, seed=a.seed, on_chunk=on_chunk, arena=Arena())
    t_ms, idx = np.concatenate(spk_t), np.concatenate(spk_i)
    neurons = res["brain"].neurons.copy()

    paths = save_spikes(t_ms, idx, neurons.root_id.to_numpy(), OUT)
    counts = np.bincount(idx, minlength=len(neurons))
    neurons["spike_count"] = counts
    neurons["rate_hz"] = counts / a.seconds
    neurons.to_parquet(OUT / "neurons.parquet", compression="zstd")
    beh = pd.DataFrame(res["log"])
    beh.to_csv(OUT / "behaviour.csv", index=False, float_format="%.4g")
    (OUT / "video").mkdir(exist_ok=True)
    rend = res["sim"].renderer
    rend.save_video(OUT / "video")

    info = dict(
        simulated_s=a.seconds, seed=a.seed, loop_ms=5.0, brain_dt_ms=0.1, physics_dt_ms=0.1,
        n_neurons=len(neurons), n_spikes=int(len(idx)),
        neurons_that_spiked=int((counts > 0).sum()),
        mean_rate_all_hz=float(counts.sum() / len(neurons) / a.seconds),
        wall_s=round(time.time() - t0, 1), timing_s={k: round(v, 1) for k, v in res["timing"].items()},
        video_playback_speed=rend.playback_speed, video_fps=rend.output_fps,
        video_frame_dt_ms=1000 * rend.playback_speed / rend.output_fps,
        n_frames=len(next(iter(rend.frames.values()))),
        spike_files={p.name: round(p.stat().st_size / 1e6, 2) for p in paths},
        first_taste_ms=float(beh.t_ms[beh.taste].min()) if beh.taste.any() else None,
        max_mn9_hz=float(beh.mn9_hz.max()),
    )
    (OUT / "run_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))

    # round-trip check: re-read and compare
    back = pd.concat([pd.read_parquet(p) for p in paths])
    assert len(back) == len(idx) and back.neuron_idx.value_counts().sum() == counts.sum()
    print("re-read OK:", len(back), "spikes")


if __name__ == "__main__":
    main()
