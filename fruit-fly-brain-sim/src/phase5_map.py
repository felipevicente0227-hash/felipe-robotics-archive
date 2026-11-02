"""Phase 5 - neuron map of all 138,639 neurons, coloured by activity in the phase 4 run.

Outputs (outputs/phase5/):
  neuron_map.html         interactive (plotly): anatomy view, grouped grid, treemap
  map_anatomy.png         every neuron at its real position (front + top view)
  map_grid.png            one pixel per neuron, blocks = brain regions, sorted by cell type
  map_treemap.png         region -> cell class -> cell type, size = #neurons, colour = rate
  region_summary.csv      neurons / active neurons / mean rate per region

Run:  .venv/bin/python src/phase5_map.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import plotly.io as pio  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "outputs" / "phase4" / "neurons.parquet"
OUT = ROOT / "outputs" / "phase5"
GRID_W = 480  # neurons per row in the grid view
CMAP = "inferno"


def load():
    n = pd.read_parquet(IN)
    n["act"] = np.log10(1 + n.rate_hz)            # colour scale: log10(1 + Hz)
    n["cell_type"] = n.cell_type.replace("unknown", "(untyped)")
    # same rule as prepare_data.py: unassigned visual neurons (photoreceptors) -> optic lobe
    n.loc[(n.region == "Unassigned") & (n.cell_class == "visual"), "region"] = "Optic lobe"
    order = n.region.value_counts().index.tolist()
    if "Unassigned" in order:                       # keep 'Unassigned' last
        order.remove("Unassigned")
        order.append("Unassigned")
    n["region"] = pd.Categorical(n.region, categories=order, ordered=True)
    return n, order


def grid_layout(n, order):
    """Row/col of every neuron: region blocks stacked, neurons sorted by class & type."""
    rows, cols, labels, r0 = np.zeros(len(n), int), np.zeros(len(n), int), [], 0
    for reg in order:
        sub = n[n.region == reg].sort_values(["super_class", "cell_class", "cell_type", "rate_hz"],
                                             ascending=[True, True, True, False])
        k = np.arange(len(sub))
        rows[sub.index] = r0 + k // GRID_W
        cols[sub.index] = k % GRID_W
        nrows = int(np.ceil(len(sub) / GRID_W))
        labels.append((reg, r0, nrows, len(sub)))
        r0 += max(nrows, 9) + 3                      # min block height so labels fit
    return rows, cols, labels, r0


def png_anatomy(n, path, vmax):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor="black",
                             gridspec_kw=dict(width_ratios=[1.6, 1]))
    for ax, (a, b, title) in zip(axes, [("x", "y", "front view (x, y)"),
                                         ("x", "z", "top view (x, z)")]):
        s = n.sort_values("act")                      # active neurons drawn on top
        ax.scatter(s[a], -s[b] if b == "y" else s[b], c=s.act, s=0.3, cmap=CMAP,
                   vmin=0, vmax=vmax, linewidths=0, rasterized=True)
        ax.set_facecolor("black"); ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(title, color="w")
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(0, vmax))
    cb = fig.colorbar(sm, ax=axes, fraction=0.02, pad=0.01)
    cb.set_label("log10(1 + firing rate in Hz)", color="w"); cb.ax.tick_params(colors="w")
    fig.suptitle(f"All {len(n):,} FlyWire neurons at their real positions, coloured by activity",
                 color="w", fontsize=14)
    fig.savefig(path, dpi=150, facecolor="black"); plt.close(fig)


def png_grid(n, rows, cols, labels, H, path, vmax):
    img = np.full((H, GRID_W), np.nan)
    img[rows, cols] = n.act.to_numpy()
    fig, ax = plt.subplots(figsize=(11, 0.03 * H + 1), facecolor="white")
    cm = plt.get_cmap(CMAP).copy(); cm.set_bad("white")
    im = ax.imshow(img, cmap=cm, vmin=0, vmax=vmax, aspect="auto", interpolation="nearest")
    for reg, r0, nr, cnt in labels:
        act = (n.region == reg) & (n.rate_hz > 0)
        ax.text(-8, r0 + max(nr, 9) / 2, f"{reg}: {cnt:,} neurons, {act.sum():,} active",
                ha="right", va="center", fontsize=8)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01, label="log10(1 + Hz)")
    ax.set_title("Neuron map: one pixel per neuron, grouped by brain region, "
                 "sorted by cell class and cell type", fontsize=11)
    fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)


def treemap_df(n):
    n = n.assign(region=n.region.astype(str))
    g = n.groupby(["region", "cell_class", "cell_type"], observed=True).agg(
        count=("idx", "size"), rate=("rate_hz", "mean"), active=("rate_hz", lambda r: (r > 0).sum())
    ).reset_index()
    ids, parents, labels, values, colors, hover = [], [], [], [], [], []

    def add(i, p, lab, v, r, a):
        ids.append(i); parents.append(p); labels.append(lab); values.append(v)
        colors.append(np.log10(1 + r)); hover.append(f"{v:,} neurons · {a:,} active · mean {r:.2f} Hz")

    for reg, gr in g.groupby("region"):
        add(reg, "", reg, gr["count"].sum(), np.average(gr.rate, weights=gr["count"]), gr.active.sum())
        for cc, gc in gr.groupby("cell_class"):
            add(f"{reg}/{cc}", reg, cc, gc["count"].sum(),
                np.average(gc.rate, weights=gc["count"]), gc.active.sum())
            for _, row in gc.iterrows():
                add(f"{reg}/{cc}/{row.cell_type}", f"{reg}/{cc}", row.cell_type,
                    row["count"], row.rate, row.active)
    return ids, parents, labels, values, colors, hover


def html_map(n, rows, cols, labels, H, tm, path, vmax):
    """One compact lookup table (JSON) for all neurons; plots carry only neuron indices
    and a small JS tooltip reads the details, keeping the file small."""
    import json
    cats = {c: pd.Categorical(n[c].astype(str)) for c in
            ["cell_type", "cell_class", "region", "side", "nt_type"]}
    table = {c: {"names": list(v.categories), "codes": v.codes.tolist()} for c, v in cats.items()}
    table["rate"] = n.rate_hz.round(2).tolist()
    table["id"] = n.root_id.astype(str).tolist()
    cbar = dict(title="log10(1+Hz)")
    s = n.sort_values("act")
    f1 = go.Figure(go.Scattergl(
        x=s.x.round(1).to_numpy(), y=(-s.y).round(1).to_numpy(), mode="markers",
        customdata=s.index.to_numpy(np.int32), hoverinfo="none",
        marker=dict(size=2, color=s.act.round(3).to_numpy(), colorscale=CMAP.capitalize(),
                    cmin=0, cmax=vmax, colorbar=cbar)))
    f1.update_layout(title="1 · Anatomy: every neuron at its real position (front view). "
                           "Hover for details; drag to zoom.", template="plotly_dark", height=700,
                     yaxis=dict(scaleanchor="x", visible=False), xaxis=dict(visible=False))
    z = np.full((H, GRID_W), np.nan, np.float32)
    z[rows, cols] = n.act.round(3).to_numpy()
    ix = np.full((H, GRID_W), -1, np.int32)
    ix[rows, cols] = n.index.to_numpy()
    f2 = go.Figure(go.Heatmap(z=z, customdata=ix, hoverinfo="none", colorscale=CMAP.capitalize(),
                              zmin=0, zmax=vmax, colorbar=cbar, hoverongaps=False))
    for reg, r0, nr, cnt in labels:
        f2.add_annotation(x=-5, y=r0 + nr / 2, text=f"{reg} ({cnt:,})", xanchor="right",
                          showarrow=False, font=dict(size=10))
    f2.update_layout(title="2 · Grouped grid: one cell per neuron, blocks = brain regions, "
                           "sorted by cell class / cell type", height=max(700, 3 * H),
                     yaxis=dict(autorange="reversed", visible=False), xaxis=dict(visible=False),
                     margin=dict(l=230), plot_bgcolor="white")
    ids, parents, labs, values, colors, hov = tm
    f3 = go.Figure(go.Treemap(ids=ids, parents=parents, labels=labs, values=values,
                              branchvalues="total", customdata=hov,
                              hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
                              marker=dict(colors=colors, colorscale=CMAP.capitalize(), cmin=0,
                                          cmax=vmax, colorbar=cbar), maxdepth=2))
    f3.update_layout(title="3 · Treemap: region → cell class → cell type (click to zoom). "
                           "Size = number of neurons, colour = mean rate", height=800)
    divs = [pio.to_html(f, full_html=False, include_plotlyjs=(k == 0), div_id=f"fig{k}")
            for k, f in enumerate([f1, f2, f3])]
    tot, act = len(n), int((n.rate_hz > 0).sum())
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fly brain neuron map</title>
<style>body{{font-family:system-ui,sans-serif;margin:0 16px;background:#fafafa;color:#222}}
h1{{font-size:1.4em}} .note{{max-width:900px;color:#444}}
#tip{{position:fixed;pointer-events:none;background:#111d;color:#fff;padding:6px 8px;
border-radius:4px;font-size:12px;display:none;z-index:10;line-height:1.4}}</style></head><body>
<h1>Whole fly brain neuron map – FlyWire v783, closed-loop run</h1>
<p class="note">{tot:,} neurons; {act:,} fired at least once during the 10 s simulated
closed-loop run (phase 4). Colour = log10(1 + firing rate in Hz). Region = the neuropil
holding most of a neuron's synapses. Three views below; hover any neuron for its cell type,
region, side, neurotransmitter, rate and FlyWire ID.</p>
<div id="tip"></div>
{divs[0]}{divs[1]}{divs[2]}
<script>
const T = {json.dumps(table, separators=(",", ":"))};
const tip = document.getElementById("tip");
const nm = (c, i) => T[c].names[T[c].codes[i]];
function show(ev) {{
  const p = ev.points && ev.points[0]; if (!p) return;
  const i = p.customdata; if (i === undefined || i < 0) {{ tip.style.display = "none"; return; }}
  tip.innerHTML = `<b>${{nm("cell_type", i)}}</b> · ${{nm("cell_class", i)}}<br>${{nm("region", i)}}`
    + ` · ${{nm("side", i)}} · ${{nm("nt_type", i)}}<br>${{T.rate[i]}} Hz · id ${{T.id[i]}}`;
  tip.style.left = (ev.event.clientX + 14) + "px"; tip.style.top = (ev.event.clientY + 14) + "px";
  tip.style.display = "block";
}}
for (const id of ["fig0", "fig1"]) {{
  const el = document.getElementById(id);
  el.on("plotly_hover", show); el.on("plotly_unhover", () => tip.style.display = "none");
}}
</script></body></html>"""
    path.write_text(html)


def png_treemap(html_path, png_path):
    """Screenshot the treemap with the pre-installed (Node) Playwright + Chromium."""
    import subprocess
    js = f"""const {{chromium}} = require('playwright');
(async () => {{ const b = await chromium.launch();
  const p = await b.newPage({{viewport: {{width: 1400, height: 900}}}});
  await p.goto('{html_path.as_uri()}'); await p.waitForTimeout(5000);
  await p.locator('#fig2').screenshot({{path: '{png_path}'}}); await b.close(); }})();"""
    subprocess.run(["node", "-e", js], check=True, timeout=180)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n, order = load()
    vmax = float(np.quantile(n.act[n.act > 0], 0.99))
    rows, cols, labels, H = grid_layout(n, order)
    png_anatomy(n, OUT / "map_anatomy.png", vmax)
    png_grid(n, rows, cols, labels, H, OUT / "map_grid.png", vmax)
    tm = treemap_df(n)
    html_map(n, rows, cols, labels, H, tm, OUT / "neuron_map.html", vmax)
    try:
        png_treemap(OUT / "neuron_map.html", OUT / "map_treemap.png")
    except Exception as e:  # screenshot is a nice-to-have
        print("treemap PNG skipped:", e)
    summ = n.groupby("region", observed=True).agg(
        neurons=("idx", "size"), active=("rate_hz", lambda r: int((r > 0).sum())),
        mean_rate_hz=("rate_hz", "mean"), max_rate_hz=("rate_hz", "max"))
    summ.to_csv(OUT / "region_summary.csv", float_format="%.3f")
    print(summ.to_string())
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:22s} {f.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    sys.exit(main())
