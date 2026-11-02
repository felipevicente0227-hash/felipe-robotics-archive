"""Phase 1b - merge the downloaded FlyWire v783 tables into two tidy files.

Outputs (in data/work/, regenerated, not committed):
  neurons.parquet   one row per neuron, in Shiu-model index order:
                    idx, root_id, super_class, cell_class, cell_type, nt_type,
                    side, neuropil (dominant), region (coarse brain region), x, y, z
  connectome.npz    sparse weight matrix W[post, pre] (signed synapse counts,
                    + excitatory / - inhibitory, exactly as in Shiu et al. 2024)

Run:  .venv/bin/python src/prepare_data.py
"""
from pathlib import Path
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
WORK = ROOT / "data" / "work"

# Neuropil -> coarse brain region (standard FlyWire "super-neuropil" grouping)
REGION_OF = {
    **{n: "Optic lobe" for n in ["LA", "ME", "AME", "LO", "LOP"]},
    **{n: "Mushroom body" for n in ["MB_CA", "MB_PED", "MB_VL", "MB_ML"]},
    **{n: "Central complex" for n in ["EB", "FB", "PB", "NO"]},
    "AL": "Antennal lobe",
    "LH": "Lateral horn",
    **{n: "Lateral complex" for n in ["BU", "GA", "LAL"]},
    "AOTU": "Optic tubercle",
    **{n: "Superior neuropils" for n in ["SLP", "SIP", "SMP"]},
    **{n: "Inferior neuropils" for n in ["CRE", "ICL", "IB", "ATL", "SCL"]},
    **{n: "Ventromedial neuropils" for n in ["VES", "EPA", "GOR", "SPS", "IPS"]},
    **{n: "Ventrolateral neuropils" for n in ["AVLP", "PVLP", "PLP", "WED"]},
    **{n: "Periesophageal neuropils" for n in ["SAD", "AMMC", "FLA", "CAN", "PRW"]},
    "GNG": "Gnathal ganglion (SEZ)",
    "OCG": "Ocellar ganglion",
}


def dominant_neuropil(path: Path) -> pd.DataFrame:
    """For every neuron, the neuropil holding most of its synapses (in + out)."""
    t = pd.read_csv(path)
    cols = [c for c in t.columns if " in " in c]
    names = sorted({c.split(" in ")[1] for c in cols})
    tot = np.zeros((len(t), len(names)), dtype=np.float32)
    for c in cols:
        tot[:, names.index(c.split(" in ")[1])] += t[c].fillna(0).to_numpy()
    best = np.array(names)[tot.argmax(1)]
    best[tot.sum(1) == 0] = "UNASGD"
    return pd.DataFrame({"root_id": t.root_id, "neuropil": best})


def main():
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    shiu = RAW / "Drosophila_brain_model"

    comp = pd.read_csv(shiu / "Completeness_783.csv", index_col=0)
    df = pd.DataFrame({"idx": np.arange(len(comp)), "root_id": comp.index.to_numpy()})

    ann = pd.read_csv(RAW / "flywire_annotations/supplemental_files/"
                      "Supplemental_file1_neuron_annotations.tsv",
                      sep="\t", low_memory=False,
                      usecols=["root_id", "super_class", "cell_class", "cell_type",
                               "hemibrain_type", "top_nt", "side"])
    ann["cell_type"] = ann.cell_type.fillna(ann.hemibrain_type)
    df = df.merge(ann.drop(columns="hemibrain_type"), on="root_id", how="left")

    neu = pd.read_csv(RAW / "codex_neurons.csv.gz", usecols=["root_id", "nt_type"])
    df = df.merge(neu, on="root_id", how="left")
    nt_map = {"acetylcholine": "ACH", "glutamate": "GLUT", "gaba": "GABA",
              "dopamine": "DA", "serotonin": "SER", "octopamine": "OCT"}
    df["nt_type"] = df.nt_type.fillna(df.top_nt.map(nt_map)).fillna("unknown")

    df = df.merge(dominant_neuropil(RAW / "codex_neuropil_synapse_table.csv.gz"),
                  on="root_id", how="left")
    df["neuropil"] = df.neuropil.fillna("UNASGD")
    base = df.neuropil.str.replace(r"_(L|R)$", "", regex=True)
    df["region"] = base.map(REGION_OF).fillna("Unassigned")

    coords = pd.read_csv(RAW / "codex_coordinates.csv.gz").drop_duplicates("root_id")
    xyz = np.stack(coords.position.str.strip("[]").str.split().apply(
        lambda v: np.array(v, dtype=float)).to_numpy())
    coords = pd.DataFrame({"root_id": coords.root_id, "x": xyz[:, 0] / 1000,
                           "y": xyz[:, 1] / 1000, "z": xyz[:, 2] / 1000})  # nm -> um
    df = df.merge(coords, on="root_id", how="left")

    for c in ["super_class", "cell_class", "cell_type", "side"]:
        df[c] = df[c].fillna("unknown")
    df = df.drop(columns="top_nt").sort_values("idx").reset_index(drop=True)
    assert len(df) == len(comp) and (df.idx.to_numpy() == np.arange(len(df))).all()
    df.to_parquet(WORK / "neurons.parquet", compression="zstd")

    con = pd.read_parquet(shiu / "Connectivity_783.parquet",
                          columns=["Presynaptic_Index", "Postsynaptic_Index",
                                   "Excitatory x Connectivity"])
    n = len(df)
    W = sp.csr_matrix((con["Excitatory x Connectivity"].to_numpy(np.float32),
                       (con.Postsynaptic_Index.to_numpy(), con.Presynaptic_Index.to_numpy())),
                      shape=(n, n))
    W.sum_duplicates()
    sp.save_npz(WORK / "connectome.npz", W)

    print(f"neurons: {n:,}  connections: {W.nnz:,}  "
          f"synapses: {int(np.abs(W.data).sum()):,}  ({time.time() - t0:.1f}s)")
    print(df.region.value_counts().to_string())
    print(df.nt_type.value_counts().to_string())


if __name__ == "__main__":
    main()
