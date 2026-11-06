"""Phase 3 - whole-brain model in closed loop with the NeuroMechFly body.

Every LOOP_MS (5 ms) of simulated time:
  1. read the body's senses (odor at each antenna, sugar under the mouth, ommatidia,
     head touching a wall)
  2. turn them into Poisson rates of the matching sensory neurons
  3. advance the 138,639-neuron brain 5 ms (50 steps of 0.1 ms)
  4. read descending-neuron (and MN9) firing rates -> left/right walking drive
  5. advance the body 5 ms (50 MuJoCo steps of 0.1 ms) with FlyGym's walking controller

Run a quick test:  MUJOCO_GL=egl .venv/bin/python src/closed_loop.py --seconds 2
"""
import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import mujoco as mj
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from brain import Brain, ROOT  # noqa: E402
from sensors import SensoryMap  # noqa: E402

LOOP_MS = 5.0


# --------------------------------------------------------------------- arena
@dataclass
class Arena:
    half: float = 12.0                 # walls at +-12 mm  (fly body is ~2.5 mm long)
    wall_h: float = 1.5
    sugar_xy: tuple = (5.0, 3.0)       # sugar / food spot centre (mm)
    sugar_r: float = 2.0
    odor_d0: float = 6.0               # odor halves at 6 mm from the spot
    spawn_xy: tuple = (-3.0, -2.0)
    spawn_heading_deg: float = -10.0

    def odor(self, xy):
        d = np.linalg.norm(np.asarray(xy) - self.sugar_xy, axis=-1)
        return 1.0 / (1.0 + (d / self.odor_d0) ** 2)

    def on_sugar(self, xy):
        return np.linalg.norm(np.asarray(xy) - self.sugar_xy) < self.sugar_r


def build_sim(arena: Arena, vision=True, render=True):
    from flygym import Simulation
    from flygym.compose import FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import make_locomotion_fly

    fly = make_locomotion_fly(colorize=True)
    if vision:
        fly.add_vision()
    cam = fly.add_tracking_camera(pos_offset=(-0.5, -9, 7))
    world = FlatGroundWorld(half_size=50)
    wb = world.mjcf_root.worldbody
    h, t, z = arena.half, 0.2, arena.wall_h / 2
    for i, (pos, size) in enumerate([((0, h, z), (h + t, t, z)), ((0, -h, z), (h + t, t, z)),
                                     ((h, 0, z), (t, h, z)), ((-h, 0, z), (t, h, z))]):
        wall = wb.add_geom(name=f"wall{i}", type=mj.mjtGeom.mjGEOM_BOX, pos=pos, size=size,
                           rgba=(0.25, 0.3, 0.45, 1), contype=0, conaffinity=0)
        world.ground_geoms.append(wall)   # FlyGym creates fly<->geom contacts only for these
    wb.add_geom(name="sugar", type=mj.mjtGeom.mjGEOM_CYLINDER,
                pos=(*arena.sugar_xy, 0.002), size=(arena.sugar_r, 0.002, 0),
                rgba=(1.0, 0.75, 0.1, 1), contype=0, conaffinity=0)
    top = wb.add_camera(name="topcam", pos=(0, 0, 30), fovy=48)
    th = np.deg2rad(arena.spawn_heading_deg)
    world.add_fly(fly, (*arena.spawn_xy, 0.8),
                  Rotation3D("quat", (np.cos(th / 2), 0, 0, np.sin(th / 2))))
    sim = Simulation(world)
    if render:
        sim.set_renderer([cam, "topcam"], camera_res=(360, 480), playback_speed=0.25,
                         output_fps=25)
    return sim, fly, cam


# --------------------------------------------------------------------- motor
class MotorDecoder:
    """Descending-neuron rates -> [left, right] drive for FlyGym's turning controller.

    * walking speed  : mean rate of walking/steering DNs (DNa01, DNa02, DNb05, DNp09)
                       on top of a slow default pace from the nerve cord (VNC)
    * turning        : left-minus-right balance of the steering DNs DNa01 + DNa02
                       (they drive ipsilateral turns, Rayshubskiy et al. 2020). The VNC
                       adapts to sustained input (0.5 s time constant), so only changes
                       in the left/right balance steer; each side is normalised by its
                       own recent mean (left DNa01/02 fire far more than right ones in
                       this connectome model even for symmetric input), then scaled by
                       the summed mean of both sides.
    * backward       : MDN ("moonwalker") rate -> negative drive
    * stop & feed    : MN9 (proboscis motor neuron) rate -> drive goes to zero
    """
    WALK = ["DNa01", "DNa02", "DNb05", "DNp09"]
    STEER = ["DNa01", "DNa02"]

    def __init__(self, neurons, mn9_idx, base=0.4, tau_ms=100.0, adapt_ms=500.0):
        def group(types, side=None):
            s = neurons.cell_type.isin(types)
            if side:
                s &= neurons.side == side
            return neurons[s].idx.to_numpy()
        self.walk = group(self.WALK)
        self.steer_l, self.steer_r = group(self.STEER, "left"), group(self.STEER, "right")
        self.mdn = group(["MDN"])
        self.mn9 = np.array([mn9_idx])
        self.watch = np.r_[self.walk, self.steer_l, self.steer_r, self.mdn, self.mn9]
        self.rate = np.zeros(neurons.idx.max() + 1, np.float32)  # smoothed Hz, all neurons
        self.k = LOOP_MS / tau_ms
        self.ka = LOOP_MS / adapt_ms
        self.steer_avg = np.zeros(2)
        self.base = base

    def update(self, spike_idx):
        counts = np.bincount(spike_idx, minlength=len(self.rate)).astype(np.float32)
        self.rate += self.k * (counts * (1000.0 / LOOP_MS) - self.rate)
        r = self.rate
        walk = r[self.walk].mean()
        sl, sr = r[self.steer_l].sum(), r[self.steer_r].sum()
        self.steer_avg += self.ka * (np.array([sl, sr]) - self.steer_avg)
        # change of each side vs its own recent mean, on one shared scale (gain control)
        dl, dr = np.array([sl, sr]) - self.steer_avg
        turn = np.clip(1.5 * (dl - dr) / (self.steer_avg.sum() + 20.0), -1, 1)  # >0: left
        speed = self.base + (1 - self.base) * np.tanh(walk / 40.0)
        back = np.tanh(r[self.mdn].mean() / 30.0)
        feed = np.clip(r[self.mn9[0]] / 30.0, 0, 1)
        left = speed * (1 - max(turn, 0)) - back
        right = speed * (1 + min(turn, 0)) - back
        drive = np.array([left, right]) * (1 - feed)
        info = dict(walk_hz=walk, steer_l_hz=sl, steer_r_hz=sr, turn=turn, speed=speed,
                    mdn_hz=r[self.mdn].mean(), mn9_hz=r[self.mn9[0]], feed=feed)
        return drive, info


# --------------------------------------------------------------------- senses
class Senses:
    def __init__(self, sim, fly, arena, smap: SensoryMap, vision=True):
        self.sim, self.fly, self.arena, self.smap, self.vision = sim, fly, arena, smap, vision
        order = [s.name for s in fly.get_bodysegs_order()]
        self.i_ant = [order.index("l_funiculus"), order.index("r_funiculus")]
        self.i_mouth = order.index("c_haustellum")
        self.i_thorax = order.index("c_thorax")
        self.i_head = order.index("c_head")
        self.omm_slow = None
        self.omm_rates = np.zeros((2, 721))

    def read(self, update_vision):
        pos = self.sim.get_body_positions(self.fly.name)
        odor = self.arena.odor(pos[self.i_ant, :2])          # (left, right) 0..1
        taste = self.arena.on_sugar(pos[self.i_mouth, :2])
        # touch: head within 0.6 mm of a wall -> bristle neurons on the side facing it
        head, thorax = pos[self.i_head, :2], pos[self.i_thorax, :2]
        touch = np.zeros(2)
        h = self.arena.half
        for wall_dir in ([1, 0], [-1, 0], [0, 1], [0, -1]):
            wd = np.array(wall_dir, float)
            if h - head @ wd < 0.6:
                fwd = head - thorax
                side = 0 if fwd[0] * wd[1] - fwd[1] * wd[0] > 0 else 1   # wall on left/right
                touch[side] = 50.0
                if abs(fwd @ wd) > 0.8 * np.linalg.norm(fwd):             # head-on: both
                    touch[:] = 50.0
        if self.vision and update_vision:
            o = self.sim.get_ommatidia_readouts(self.fly.name).max(-1)  # (2, 721) 0..1
            if self.omm_slow is None:
                self.omm_slow = o.copy()
            # photoreceptors: small tonic response + strong response to changes in light
            self.omm_rates = np.clip(5 * o + 400 * np.abs(o - self.omm_slow), 0, 100)
            self.omm_slow += 0.2 * (o - self.omm_slow)
        rates = self.smap.rates(60.0 * odor, 100.0 * taste, self.omm_rates, touch)
        hd = pos[self.i_head, :2] - pos[self.i_thorax, :2]
        return rates, dict(odor_l=odor[0], odor_r=odor[1], taste=bool(taste),
                           touch_l=touch[0] > 0, touch_r=touch[1] > 0,
                           heading_deg=float(np.degrees(np.arctan2(hd[1], hd[0]))),
                           xy=pos[self.i_thorax, :2].copy())


# --------------------------------------------------------------------- loop
def run(seconds=2.0, vision=True, render=True, seed=0, on_chunk=None, arena=Arena(),
        warmup_ms=500.0):
    from flygym_demo.complex_terrain import (HybridTurningController,
                                             HybridControllerObservation,
                                             apply_locomotion_action)
    t_start = time.time()
    brain = Brain(seed=seed, fix_al_ln_sign=True)
    smap = SensoryMap(brain.neurons)
    brain.set_inputs(smap.all_idx, np.zeros(len(smap.all_idx)))
    sim, fly, cam = build_sim(arena, vision=vision, render=render)
    ctrl = HybridTurningController(timestep=sim.timestep)
    ctrl.reset(seed=seed)
    sim.warmup()
    senses = Senses(sim, fly, arena, smap, vision)
    decoder = MotorDecoder(brain.neurons, smap.mn9)
    n_phys = int(round(LOOP_MS * 1e-3 / sim.timestep))
    n_chunks = int(round(seconds * 1000 / LOOP_MS))
    # brain warm-up: 0.5 s with the starting senses while the body stands still, so the
    # rate filters / VNC adaptation start from a settled state (not from silence)
    for _ in range(int(warmup_ms / LOOP_MS)):
        brain.in_rate[:] = senses.read(update_vision=True)[0]
        decoder.update(brain.run(LOOP_MS)[1])
    brain.t = 0.0
    print(f"setup {time.time() - t_start:.1f}s; {n_chunks} loops x ({n_phys} physics + "
          f"{int(LOOP_MS / brain.p.dt)} brain steps)")

    log, t_brain, t_body, t_sense = [], 0.0, 0.0, 0.0
    drive = np.zeros(2)
    for c in range(n_chunks):
        t0 = time.time()
        rates, sinfo = senses.read(update_vision=(c % 4 == 0))   # vision at 50 Hz
        brain.in_rate[:] = rates
        t1 = time.time()
        st, si = brain.run(LOOP_MS)
        t2 = time.time()
        drive, minfo = decoder.update(si)
        for _ in range(n_phys):
            obs = HybridControllerObservation.from_sim(sim, fly.name)
            apply_locomotion_action(sim, fly.name, ctrl.step(drive, obs))
            sim.step()
            if render:
                sim.render_as_needed()
        t3 = time.time()
        t_sense, t_brain, t_body = t_sense + t1 - t0, t_brain + t2 - t1, t_body + t3 - t2
        row = dict(t_ms=brain.t, n_spikes=len(si), drive_l=drive[0], drive_r=drive[1],
                   x=sinfo["xy"][0], y=sinfo["xy"][1], **{k: v for k, v in sinfo.items() if k != "xy"},
                   **minfo)
        log.append(row)
        if on_chunk is not None:
            on_chunk(st, si, row)
        if c % int(500 / LOOP_MS) == 0:
            print(f"t={brain.t:6.0f} ms  pos=({row['x']:5.1f},{row['y']:5.1f})  spikes/5ms={len(si):5d}"
                  f"  odor=({row['odor_l']:.2f},{row['odor_r']:.2f}) taste={row['taste']:d}"
                  f"  drive=({drive[0]:+.2f},{drive[1]:+.2f})  MN9={row['mn9_hz']:.0f}Hz"
                  f"  wall={time.time() - t_start:.0f}s", flush=True)
    timing = dict(total_s=time.time() - t_start, sense_s=t_sense, brain_s=t_brain, body_s=t_body)
    return dict(sim=sim, cam=cam, log=log, timing=timing, brain=brain, smap=smap, decoder=decoder)


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--spawn", type=float, nargs=3, metavar=("X", "Y", "HEADING_DEG"))
    ap.add_argument("--name", default="closed_loop_test")
    a = ap.parse_args()
    out = ROOT / "outputs" / "phase3"
    out.mkdir(parents=True, exist_ok=True)
    arena = Arena()
    if a.spawn:
        arena = Arena(spawn_xy=tuple(a.spawn[:2]), spawn_heading_deg=a.spawn[2])
    res = run(a.seconds, vision=not a.no_vision, arena=arena)
    (out / a.name).mkdir(exist_ok=True)
    pd.DataFrame(res["log"]).to_csv(out / a.name / "log.csv", index=False, float_format="%.4g")
    res["sim"].renderer.save_video(out / a.name)   # one MP4 per camera
    print({k: round(v, 1) for k, v in res["timing"].items()})


if __name__ == "__main__":
    main()
