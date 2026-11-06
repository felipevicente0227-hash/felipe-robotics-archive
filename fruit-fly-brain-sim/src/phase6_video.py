"""Phase 6 - side-by-side MP4: the fly in the arena + live whole-brain activity.

Left : top camera (arena) above the tracking camera (close-up of the fly).
Right: all 138,639 neurons at their real positions (front view of the brain); each
       neuron lights up when it spikes and fades with a 20 ms time constant.
       Below it: per-region activity bars and live readouts (odor, taste, MN9, drive).

Video frames come from phase 4 (one frame per 10 ms of simulated time, played at
0.25x real time). Brain activity is rebuilt from outputs/phase4/spikes*.parquet.

Run:  .venv/bin/python src/phase6_video.py
"""
import json
from pathlib import Path

import imageio.v2 as imageio
import matplotlib
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
P4 = ROOT / "outputs" / "phase4"
OUT = ROOT / "outputs" / "phase6"
BW, BH = 760, 520          # brain panel size (px)
TAU_MS = 20.0              # glow decay


def font(sz):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    info = json.loads((P4 / "run_info.json").read_text())
    neurons = pd.read_parquet(P4 / "neurons.parquet")
    # same rule as prepare_data.py: unassigned visual neurons (photoreceptors) -> optic lobe
    neurons.loc[(neurons.region == "Unassigned") & (neurons.cell_class == "visual"), "region"] = "Optic lobe"
    spikes = pd.concat([pd.read_parquet(p) for p in sorted(P4.glob("spikes*.parquet"))])
    beh = pd.read_csv(P4 / "behaviour.csv")
    top = imageio.mimread(P4 / "video" / "topcam.mp4", memtest=False)
    trk = imageio.mimread(P4 / "video" / "nmf_trackcam.mp4", memtest=False)
    n_frames = min(len(top), len(trk))
    dt = info["video_frame_dt_ms"]
    print(f"{n_frames} frames, {dt} ms simulated per frame, {len(spikes):,} spikes")

    # --- neuron -> pixel in the brain panel (front view: x right, y down)
    x, y = neurons.x.to_numpy(), neurons.y.to_numpy()
    ok = np.isfinite(x) & np.isfinite(y)
    pad = 12
    sx = (BW - 2 * pad) / (x[ok].max() - x[ok].min())
    sy = (BH - 2 * pad) / (y[ok].max() - y[ok].min())
    s = min(sx, sy)
    px = np.clip(((x - x[ok].min()) * s + pad + (BW - 2 * pad - (x[ok].max() - x[ok].min()) * s) / 2),
                 0, BW - 1).astype(int)
    py = np.clip(((y - y[ok].min()) * s + pad), 0, BH - 1).astype(int)
    pix = np.where(ok, py * BW + px, -1)
    base = np.bincount(pix[ok], minlength=BW * BH).reshape(BH, BW)
    base_img = (np.log1p(base) / np.log1p(base).max() * 55).astype(np.uint8)  # dim silhouette
    cmap = matplotlib.colormaps["inferno"]
    lut = (cmap(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)

    regions = neurons.region.value_counts().index.tolist()
    reg_code = pd.Categorical(neurons.region, categories=regions).codes
    reg_n = np.bincount(reg_code, minlength=len(regions))

    # spikes binned per frame
    fidx = np.minimum((spikes.t_ms.to_numpy() / dt).astype(int), n_frames - 1)
    order = np.argsort(fidx, kind="stable")
    sp_n = spikes.neuron_idx.to_numpy()[order]
    bounds = np.searchsorted(fidx[order], np.arange(n_frames + 1))

    decay = np.exp(-dt / TAU_MS)
    trace = np.zeros(len(neurons), np.float32)
    f_big, f_med, f_small = font(22), font(16), font(13)
    writer = imageio.get_writer(OUT / "fly_brain_side_by_side.mp4", fps=info["video_fps"],
                                codec="libx264", quality=7, macro_block_size=1)
    H_left = top[0].shape[0] + trk[0].shape[0]
    W_total = top[0].shape[1] + BW
    beh_t = beh.t_ms.to_numpy()
    for k in range(n_frames):
        ids = sp_n[bounds[k]:bounds[k + 1]]
        trace *= decay
        np.add.at(trace, ids, 1.0)
        # brain image: max glow per pixel
        glow = np.zeros(BW * BH, np.float32)
        act = trace > 0.02
        np.maximum.at(glow, pix[act & ok], np.minimum(trace[act & ok], 1.5) / 1.5)
        g = glow.reshape(BH, BW)
        v = np.maximum(base_img, (g * 255).astype(np.uint8))
        rgb = lut[v]
        rgb[g == 0] = np.stack([base_img] * 3, -1)[g == 0]          # silhouette in grey
        brain = Image.fromarray(rgb)

        canvas = Image.new("RGB", (W_total, max(H_left, BH + 330)), (12, 12, 16))
        canvas.paste(Image.fromarray(top[k]), (0, 0))
        canvas.paste(Image.fromarray(trk[k]), (0, top[0].shape[0]))
        canvas.paste(brain, (top[0].shape[1], 0))
        d = ImageDraw.Draw(canvas)
        t_ms = (k + 1) * dt
        row = beh.iloc[min(np.searchsorted(beh_t, t_ms), len(beh) - 1)]
        X0 = top[0].shape[1] + 14
        d.text((X0, 8), f"Whole fly brain · {len(neurons):,} neurons · t = {t_ms / 1000:5.2f} s",
               fill="white", font=f_big)
        d.text((X0, 36), f"{len(ids):,} spikes in this {dt:.0f} ms frame", fill=(200, 200, 200), font=f_med)

        # region activity bars (fraction of the region's neurons spiking in ~last 20 ms)
        frac = np.bincount(reg_code[trace > 0.3], minlength=len(regions)) / np.maximum(reg_n, 1)
        y0 = BH + 10
        d.text((X0, y0), "fraction of each region active (last ~20 ms)", fill="white", font=f_med)
        for j, reg in enumerate(regions):
            yy = y0 + 24 + j * 15
            w = int(min(frac[j] / 0.2, 1) * 300)
            d.rectangle([X0 + 190, yy + 2, X0 + 190 + w, yy + 12], fill=tuple(lut[200]))
            d.text((X0, yy), f"{reg[:26]}", fill=(210, 210, 210), font=f_small)
            d.text((X0 + 500, yy), f"{100 * frac[j]:4.1f}%", fill=(210, 210, 210), font=f_small)
        # behaviour readouts under the camera views
        yb = H_left + 8 if canvas.height - H_left > 100 else y0 + 24 + len(regions) * 15 + 6
        xb = 14 if canvas.height - H_left > 100 else X0
        lines = [f"odor  L {row.odor_l:.2f}  R {row.odor_r:.2f}",
                 f"taste (mouth on sugar): {'YES' if row.taste else 'no'}",
                 f"MN9 feeding motor neuron: {row.mn9_hz:5.1f} Hz",
                 f"drive L {row.drive_l:+.2f}  R {row.drive_r:+.2f}   (DN walk {row.walk_hz:4.0f} Hz)"]
        for j, ln in enumerate(lines):
            col = (255, 210, 60) if (j == 1 and row.taste) or (j == 2 and row.mn9_hz > 15) else (230, 230, 230)
            d.text((xb, yb + j * 20), ln, fill=col, font=f_med)
        writer.append_data(np.asarray(canvas))
        if k % 100 == 0:
            print(f"frame {k}/{n_frames}", flush=True)
    writer.close()
    out = OUT / "fly_brain_side_by_side.mp4"
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
