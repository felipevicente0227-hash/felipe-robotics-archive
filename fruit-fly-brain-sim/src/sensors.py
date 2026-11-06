"""Sensory wiring: which FlyWire neurons each simulated sense drives.

Senses implemented (body measurement -> neurons -> Poisson rate):
  * smell  : food odor concentration at each antenna  -> food-odor ORNs of that antenna
  * taste  : mouth (haustellum) over the sugar spot  -> sugar gustatory neurons (GRNs)
  * vision : 721 ommatidia per eye (FlyGym retina)    -> R1-6 / R7 / R8 photoreceptors,
             each photoreceptor fed by the ommatidium at its eye column (retinotopic)
  * touch  : head against a wall (left / right side)  -> head & antenna bristle
             mechanosensory neurons of that side
"""
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
RAW, WORK = ROOT / "data" / "raw", ROOT / "data" / "work"

# Sugar GRNs used by Shiu et al. 2024 (example.ipynb); one v630 ID is missing in v783.
SUGAR_GRN = [720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
             720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
             720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
             720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
             720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
             720575940611875570]
MN9 = 720575940660219265
# Olfactory receptor neuron types whose glomeruli respond to food odors (vinegar, fruit,
# yeast): DM1 (Or42b), DM4 (Or59b), DP1m (Ir64a), VA2 (Or92a).
FOOD_ORN_TYPES = ["ORN_DM1", "ORN_DM4", "ORN_DP1m", "ORN_VA2"]
PHOTORECEPTORS = ["R1-6", "R7", "R8"]
TOUCH_TYPES = ["BM_InOm", "BM_Ant", "BM_Fr"]   # eye, antenna and frontal head bristles


def _ommatidia_centres():
    from flygym.vision.retina import Retina
    m = Retina().ommatidia_id_map  # (rows, cols), 0 = outside, 1..721 = ommatidium id
    rr, cc = np.nonzero(m)
    ids = m[rr, cc] - 1
    n = ids.max() + 1
    row = np.bincount(ids, rr, n) / np.bincount(ids, None, n)
    col = np.bincount(ids, cc, n) / np.bincount(ids, None, n)
    return np.c_[row, col]


def _standardise(p):
    """Centre, rotate to principal axes (long axis first), scale to unit spread."""
    p = p - p.mean(0)
    _, _, vt = np.linalg.svd(p, full_matrices=False)
    q = p @ vt.T
    return q / q.std(0)


def build_retinotopy(neurons: pd.DataFrame) -> pd.DataFrame:
    """Map every photoreceptor to one FlyGym ommatidium of its own eye.

    * R7/R8 have eye-column coordinates in the FlyWire Codex column table.
    * R1-6 have none, so each inherits the column of the lamina neuron (L1/L2/L3)
      it sends most synapses to (taken from the connectome itself).
    * Column grid and FlyGym ommatidia grid are both rotated onto their principal
      axes (the eye's long dorsal-ventral axis) and matched by nearest neighbour.
      Left/right eye assignment is exact; within-eye orientation is approximate.
    """
    col = pd.read_csv(RAW / "codex_column_assignment.csv.gz")[["root_id", "x", "y"]]
    nrn = neurons[["idx", "root_id", "cell_type", "side"]].merge(col, on="root_id", how="left")

    # R1-6 -> strongest lamina partner's column
    W = sp.load_npz(WORK / "connectome.npz").tocsc()  # W[post, pre]
    lam = nrn[nrn.cell_type.isin(["L1", "L2", "L3"]) & nrn.x.notna()].set_index("idx")
    is_lam = np.zeros(len(nrn), bool)
    is_lam[lam.index] = True
    r16 = nrn.index[nrn.cell_type == "R1-6"]
    for i in r16:
        a, b = W.indptr[i], W.indptr[i + 1]
        post, w = W.indices[a:b], W.data[a:b]
        keep = is_lam[post]
        if keep.any():
            best = post[keep][np.argmax(np.abs(w[keep]))]
            nrn.loc[i, ["x", "y"]] = lam.loc[best, ["x", "y"]].to_numpy()

    pr = nrn[nrn.cell_type.isin(PHOTORECEPTORS) & nrn.x.notna() & nrn.side.isin(["left", "right"])].copy()
    omm = _standardise(_ommatidia_centres())
    tree = cKDTree(omm)
    pr["eye"] = (pr.side == "right").astype(int)       # 0 = left eye, 1 = right eye
    pr["ommatidium"] = -1
    for eye, side in [(0, "left"), (1, "right")]:
        s = pr.side == side
        xy = pr.loc[s, ["x", "y"]].to_numpy(float)
        uniq, inv = np.unique(xy, axis=0, return_inverse=True)
        pr.loc[s, "ommatidium"] = tree.query(_standardise(uniq))[1][inv.ravel()]
    return pr[["idx", "cell_type", "eye", "ommatidium"]].reset_index(drop=True)


class SensoryMap:
    """Neuron index lists for each sense, built once from the neuron table."""

    def __init__(self, neurons: pd.DataFrame):
        id2idx = pd.Series(neurons.idx.to_numpy(), index=neurons.root_id)
        self.sugar = id2idx.reindex(SUGAR_GRN).dropna().astype(int).to_numpy()
        self.mn9 = int(id2idx[MN9])
        orn = neurons[neurons.cell_type.isin(FOOD_ORN_TYPES)]
        self.orn_left = orn[orn.side == "left"].idx.to_numpy()
        self.orn_right = orn[orn.side == "right"].idx.to_numpy()
        touch = neurons[neurons.cell_type.isin(TOUCH_TYPES)]
        self.touch_left = touch[touch.side == "left"].idx.to_numpy()
        self.touch_right = touch[touch.side == "right"].idx.to_numpy()
        cache = WORK / "retinotopy.parquet"
        if not cache.exists():
            build_retinotopy(neurons).to_parquet(cache)
        self.retino = pd.read_parquet(cache)
        self.photo_idx = self.retino.idx.to_numpy()
        self.photo_eye = self.retino.eye.to_numpy()
        self.photo_omm = self.retino.ommatidium.to_numpy()
        # all driven neurons, in one fixed order
        self.all_idx = np.r_[self.orn_left, self.orn_right, self.sugar, self.touch_left,
                             self.touch_right, self.photo_idx]
        self.n_orn_l, self.n_orn_r = len(self.orn_left), len(self.orn_right)
        self.n_sugar = len(self.sugar)

    def rates(self, odor_lr, taste, omm_rates, touch_lr=(0.0, 0.0)):
        """Concatenate per-neuron Poisson rates (Hz) in `all_idx` order."""
        return np.r_[np.full(self.n_orn_l, odor_lr[0]), np.full(self.n_orn_r, odor_lr[1]),
                     np.full(self.n_sugar, taste),
                     np.full(len(self.touch_left), touch_lr[0]),
                     np.full(len(self.touch_right), touch_lr[1]),
                     omm_rates[self.photo_eye, self.photo_omm]]
