"""Fast whole-brain spiking engine (numba) - same model as Shiu et al. 2024.

Every neuron is a leaky integrate-and-fire unit with an exponentially decaying
synaptic conductance (Brian2 equations in Shiu's model.py):

    dv/dt = (v_0 - v + g) / t_mbr        dg/dt = -g / tau
    spike when v > v_th  ->  v = v_rst, g = 0, refractory 2.2 ms
    presynaptic spike    ->  g_post += w (after a 1.8 ms delay)
    w = 0.275 mV x synapse count x (+1 excitatory / -1 inhibitory)

External input (senses, optogenetic-style activation) is a Poisson spike train
that kicks v by w_syn * f_poi = 68.75 mV, i.e. each input event forces a spike,
exactly like Brian2's PoissonInput in the original code.

The equations are linear between spikes, so we integrate them exactly with
dt = 0.1 ms (same as Brian2's 'linear' method). Unlike Brian2, this engine can be
advanced a few milliseconds at a time, which is what the closed loop needs.
"""
from dataclasses import dataclass
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "work"


@dataclass
class Params:  # Shiu et al. 2024 default_params, in ms / mV / Hz
    dt: float = 0.1
    v_0: float = -52.0
    v_rst: float = -52.0
    v_th: float = -45.0
    t_mbr: float = 20.0
    tau: float = 5.0
    t_rfc: float = 2.2
    t_dly: float = 1.8
    w_syn: float = 0.275
    f_poi: float = 250.0


@nb.njit(cache=True)
def _run(n_steps, v, g, ref, buf, slot0, indptr, indices, weights,
         a_vv, a_vg, a_gg, v_0, v_th, v_rst, ref_steps, no_ref,
         in_idx, in_p, in_kick, rng_state, out_t, out_i):
    """Advance the network n_steps. Returns (number of spikes, new ring slot)."""
    np.random.seed(rng_state)
    n = v.shape[0]
    nbuf = buf.shape[0]
    n_out = 0
    slot = slot0
    for s in range(n_steps):
        row = buf[slot]
        # 1) exact linear update of every non-refractory neuron
        for i in range(n):
            if ref[i] > 0:
                ref[i] -= 1
                g[i] += row[i]      # input still arrives, but v/g are not integrated
                row[i] = 0.0
                continue
            u = v[i] - v_0
            gi = g[i]
            v[i] = v_0 + a_vv * u + a_vg * gi
            g[i] = a_gg * gi + row[i]
            row[i] = 0.0
        # 2) Poisson sensory / stimulation input (each event forces a spike)
        for k in range(in_idx.shape[0]):
            if in_p[k] > 0.0 and np.random.random() < in_p[k]:
                v[in_idx[k]] += in_kick
        # 3) threshold, reset, and scatter to the delayed-input ring buffer
        tgt = buf[(slot + nbuf - 1) % nbuf]  # slot reached after the delay
        for i in range(n):
            if v[i] > v_th:
                v[i] = v_rst
                g[i] = 0.0
                ref[i] = 0 if no_ref[i] else ref_steps
                if n_out < out_t.shape[0]:
                    out_t[n_out] = s
                    out_i[n_out] = i
                n_out += 1
                for p in range(indptr[i], indptr[i + 1]):
                    tgt[indices[p]] += weights[p]
        slot = (slot + 1) % nbuf
    return n_out, slot


class Brain:
    """Whole-brain LIF network. Times in ms."""

    def __init__(self, params: Params = Params(), seed: int = 0, fix_al_ln_sign: bool = False):
        """fix_al_ln_sign: make all antennal-lobe local neurons (cell_class 'ALLN')
        inhibitory. Their FlyWire neurotransmitter *prediction* is often ACh/DA/SER, so
        the plain Shiu model makes ~65% of their synapses excitatory; in real flies they
        are mostly GABAergic/glutamatergic. Without this, any odor input triggers a
        self-sustaining ~10,000-neuron runaway (see README, phase 3). Off by default so
        the plain model stays an exact Shiu et al. reproduction."""
        self.p = p = params
        self.neurons = pd.read_parquet(WORK / "neurons.parquet")
        self.n = n = len(self.neurons)
        W = sp.load_npz(WORK / "connectome.npz")          # W[post, pre]
        Wout = W.T.tocsr()                                # rows = presynaptic neuron
        self.indptr = Wout.indptr.astype(np.int64)
        self.indices = Wout.indices.astype(np.int32)
        self.weights = (Wout.data * p.w_syn).astype(np.float32)
        if fix_al_ln_sign:
            ln = np.zeros(n, bool)
            ln[self.neurons.idx[self.neurons.cell_class == "ALLN"]] = True
            m = np.repeat(ln, np.diff(self.indptr))
            self.weights[m] = -np.abs(self.weights[m])

        dt = p.dt
        e_m, e_s = np.exp(-dt / p.t_mbr), np.exp(-dt / p.tau)
        A = p.tau / (p.tau - p.t_mbr)                     # exact 2-variable solution
        self.a_vv, self.a_gg = e_m, e_s
        self.a_vg = A * (e_s - e_m)
        self.ref_steps = int(round(p.t_rfc / dt))
        self.delay_steps = int(round(p.t_dly / dt))

        self.v = np.full(n, p.v_0, np.float32)
        self.g = np.zeros(n, np.float32)
        self.ref = np.zeros(n, np.int32)
        self.buf = np.zeros((self.delay_steps + 1, n), np.float32)
        self.slot = 0
        self.no_ref = np.zeros(n, np.bool_)
        self.in_idx = np.zeros(0, np.int64)
        self.in_rate = np.zeros(0, np.float64)
        self.t = 0.0          # ms simulated so far
        self.step_count = 0
        self.rng = np.random.default_rng(seed)
        self.id2idx = pd.Series(self.neurons.idx.to_numpy(), index=self.neurons.root_id)

    # ---- input -----------------------------------------------------------
    def idx(self, root_ids):
        """FlyWire root IDs -> model indices (IDs absent from v783 are skipped)."""
        ids = [r for r in root_ids if r in self.id2idx.index]
        missing = set(root_ids) - set(ids)
        if missing:
            print(f"  note: {len(missing)} ID(s) not in v783, skipped: {sorted(missing)}")
        return self.id2idx.loc[ids].to_numpy()

    def set_inputs(self, idx, rates_hz):
        """Poisson input to neurons `idx` at `rates_hz` (array or scalar).
        Like Shiu's PoissonInput, stimulated neurons get no refractory period."""
        idx = np.asarray(idx, np.int64)
        self.in_idx = idx
        self.in_rate = np.broadcast_to(np.asarray(rates_hz, np.float64), idx.shape).copy()
        self.no_ref[:] = False
        self.no_ref[idx] = True

    # ---- simulation ------------------------------------------------------
    def run(self, duration_ms):
        """Advance; returns (spike_times_ms, neuron_idx) for this chunk."""
        n_steps = int(round(duration_ms / self.p.dt))
        cap = max(100_000, n_steps * 2000)
        out_t = np.empty(cap, np.int32)
        out_i = np.empty(cap, np.int32)
        p_in = self.in_rate * self.p.dt * 1e-3
        n_out, self.slot = _run(
            n_steps, self.v, self.g, self.ref, self.buf, self.slot,
            self.indptr, self.indices, self.weights,
            self.a_vv, self.a_vg, self.a_gg, self.p.v_0, self.p.v_th, self.p.v_rst,
            self.ref_steps, self.no_ref, self.in_idx, p_in, self.p.w_syn * self.p.f_poi,
            int(self.rng.integers(2**31 - 1)), out_t, out_i)
        if n_out > cap:
            raise RuntimeError(f"spike buffer overflow ({n_out} > {cap})")
        t = self.t + (out_t[:n_out].astype(np.float64) + 1) * self.p.dt
        self.t += n_steps * self.p.dt
        self.step_count += n_steps
        return t, out_i[:n_out].copy()
