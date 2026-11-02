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
        r0 += nrows + 2                              # 2 empty rows between regions
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
        ax.text(-8, r0 + nr / 2, f"{reg}\n{cnt:,} neurons, {act.sum():,} active",
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
    hover = (n.cell_type.astype(str) + " · " + n.cell_class.astype(str) + "<br>" + n.region.astype(str)
             + " · " + n.side.astype(str) + " · " + n.nt_type.astype(str) + "<br>"
             + n.rate_hz.round(1).astype(str) + " Hz · id " + n.root_id.astype(str))
    s = n.assign(h=hover).sort_values("act")
    cbar = dict(title="log10(1+Hz)")
    f1 = go.Figure(go.Scattergl(
        x=s.x, y=-s.y, mode="markers", text=s.h, hoverinfo="text",
        marker=dict(size=2, color=s.act, colorscale=CMAP.capitalize(), cmin=0, cmax=vmax,
                    colorbar=cbar)))
    f1.update_layout(title="Anatomy: every neuron at its position (front view). Hover for details; "
                           "drag to zoom.", template="plotly_dark", height=700,
                     yaxis=dict(scaleanchor="x", visible=False), xaxis=dict(visible=False))

    z = np.full((H, GRID_W), np.nan)
    z[rows, cols] = n.act.to_numpy()
    txt = np.full((H, GRID_W), "", dtype=object)
    txt[rows, cols] = hover.to_numpy()
    f2 = go.Figure(go.Heatmap(z=z, text=txt, hoverinfo="text", colorscale=CMAP.capitalize(),
                              zmin=0, zmax=vmax, colorbar=cbar, hoverongaps=False))
    for reg, r0, nr, cnt in labels:
        f2.add_annotation(x=-5, y=r0 + nr / 2, text=f"{reg} ({cnt:,})", xanchor="right",
                          showarrow=False, font=dict(size=10))
    f2.update_layout(title="Grouped grid: one cell per neuron, blocks = brain regions, "
                           "sorted by cell class / cell type", height=max(700, 3 * H),
                     yaxis=dict(autorange="reversed", visible=False), xaxis=dict(visible=False),
                     margin=dict(l=230), plot_bgcolor="white")

    ids, parents, labs, values, colors, hov = tm
    f3 = go.Figure(go.Treemap(ids=ids, parents=parents, labels=labs, values=values,
                              branchvalues="total", customdata=hov,
                              hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
                              marker=dict(colors=colors, colorscale=CMAP.capitalize(), cmin=0,
                                          cmax=vmax, colorbar=cbar), maxdepth=2))
    f3.update_layout(title="Treemap: region → cell class → cell type (click to zoom). "
                           "Size = number of neurons, colour = mean rate", height=800)

    parts = [pio.to_html(f, full_html=False, include_plotlyjs=(k == 0)) for k, f in enumerate([f1, f2, f3])]
    tot, act = len(n), int((n.rate_hz > 0).sum())
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fly brain neuron map</title>
<style>body{{font-family:system-ui,sans-serif;margin:0 16px;background:#fafafa;color:#222}}
h1{{font-size:1.4em}} .note{{max-width:900px;color:#444}}</style></head><body>
<h1>Whole fly brain neuron map – FlyWire v783, closed-loop run</h1>
<p class="note">{tot:,} neurons, {act:,} fired at least once during the
{n.attrs.get('seconds', 10)} s simulated run. Colour = log10(1 + firing rate in Hz).
Regions = the neuropil holding most of a neuron's synapses. Three views below.</p>
{parts[0]}{parts[1]}{parts[2]}</body></html>"""
    path.write_text(html)


def png_treemap(html_path, png_path):
    """Screenshot the treemap from the HTML with the pre-installed Chromium."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport=dict(width=1400, height=900))
        pg.goto(html_path.as_uri())
        pg.wait_for_timeout(4000)
        pg.locator(".js-plotly-plot").nth(2).screenshot(path=str(png_path))
        b.close()


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
