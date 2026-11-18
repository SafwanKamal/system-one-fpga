"""Evaluator-side unicycle physics. Never imported by a probe selector."""
from dataclasses import dataclass
import numpy as np

DT = .02
PASSIVE = 400
SLOT = 50
MENU = np.array([[0, 0], [.04, 0], [.25, 0], [.15, .5], [.15, -.5],
                 [.04, .5], [.04, -.5], [.25, .5], [.25, -.5]], float)
PAIRS = np.array([(a, b) for a in range(len(MENU)) for b in range(len(MENU))])
KINDS = ["healthy", "gain", "bias", "offset", "lag", "deadzone", "latency"]


@dataclass
class World:
    gain: np.ndarray
    start: np.ndarray
    commands: np.ndarray
    noise: np.ndarray
    severity: float
    axis: int
    direction: float
    rho: float
    sigma: np.ndarray


def world(config, replicate, kind, duration=500):
    # Configuration and disturbance seeds do not depend on the fault label.
    c = np.random.default_rng(config)
    r = np.random.default_rng(np.random.SeedSequence([config, replicate, 991]))
    gain = c.uniform(.95, 1.05, 2)
    frequency, phase = c.uniform(.55, 1.3), c.uniform(-np.pi, np.pi)
    start = np.r_[r.uniform(-.2, .2, 2), r.uniform(-.6, .6)]
    if config % 5 == 0:
        start = np.array([2.55, 2.35, -2.35]) + r.normal(0, .025, 3)
    t = np.arange(duration) * DT
    commands = np.column_stack([.15 + .035*np.sin(frequency*t+phase),
                                .22*np.sin(.8*frequency*t+phase)])
    # Independent configurations include nearly steady post-alarm operation.
    if config % 3 == 0:
        commands[200:] = commands[199]
    rho = float(c.choice([0., .6, .9]))
    sigma = np.r_[c.uniform(.008, .012, 2), c.uniform(.012, .020)]
    noise_rng = np.random.default_rng(np.random.SeedSequence([config, replicate, 992]))
    noise = noise_rng.normal(size=(duration+1, 3))*sigma
    for i in range(1, len(noise)):
        noise[i] = rho*noise[i-1] + np.sqrt(1-rho*rho)*noise[i]
    severity = {"healthy": 0., "gain": r.uniform(.2, .4), "bias": r.uniform(.08, .16),
                "offset": r.uniform(.06, .14), "lag": r.uniform(.08, .20),
                "deadzone": r.uniform(.03, .07), "latency": r.uniform(.10, .30),
                "quantized": r.uniform(.04, .07), "held": r.uniform(.12, .24)}[kind]
    return World(gain, start, commands, noise, severity, int(r.integers(0, 2)),
                 float(r.choice([-1, 1])), rho, sigma)


def run(w, kind, sequence=None, extended=False, natural=False):
    """Vectorized counterfactual branches; only the evaluator sees this object.

    Normal mode saves the shared 8 s prefix once and all lawful 2 s continuations.
    Extended mode has a single predeclared 8-slot identification sequence.
    """
    if extended:
        sequence = [7, 6, 2, 4, 1, 3, 8, 0]
        count, steps = 1, PASSIVE+SLOT*len(sequence)
    elif natural:
        count, steps = 1, PASSIVE+2*SLOT
    elif sequence is None:
        count, steps = len(PAIRS), PASSIVE+2*SLOT
    else:
        count, steps = 1, PASSIVE+SLOT*len(sequence)
    # Prefix is simulated once; suffix branches start with exactly the same state.
    x = w.start[None].copy()
    actual = w.commands[0:1]*w.gain
    true = np.empty((1, steps+1, 3)); measured = np.empty_like(true)
    requested = np.empty((1, steps, 2)); executed = np.empty_like(requested)
    true[:, 0] = x; measured[:, 0] = x+w.noise[0]
    clips = np.zeros(1, int)
    clips8 = clips.copy(); clips9 = clips.copy()
    for k in range(steps):
        if k == PASSIVE and count > 1:
            true = np.repeat(true, count, axis=0); measured = np.repeat(measured, count, axis=0)
            requested = np.repeat(requested, count, axis=0); executed = np.repeat(executed, count, axis=0)
            x = np.repeat(x, count, axis=0); actual = np.repeat(actual, count, axis=0)
            clips = np.repeat(clips, count)
        if k < PASSIVE or natural:
            command = np.broadcast_to(w.commands[k], (len(x), 2)).copy()
        else:
            slot = (k-PASSIVE)//SLOT
            action = PAIRS[:, slot] if sequence is None else np.array([sequence[slot]])
            target = MENU[action]
            previous = w.commands[PASSIVE-1] if slot == 0 else MENU[
                PAIRS[:, slot-1] if sequence is None else np.array([sequence[slot-1]])]
            ramp = min(1., ((k-PASSIVE)%SLOT+1)/5)
            command = previous + ramp*(target-previous)
        requested[:, k] = command
        # A common causal measured-pose supervisor, never a true-state mask.
        next_xy = measured[:, k, :2] + .2*command[:, :1]*np.column_stack(
            [np.cos(measured[:, k, 2]), np.sin(measured[:, k, 2])])
        stop = (np.abs(next_xy) > 2.8).any(1)
        command = command.copy(); command[stop, 0] = 0
        clips += stop
        if k == 399: clips8 = clips.copy()
        if k == 449: clips9 = clips.copy()
        executed[:, k] = command
        target = command*w.gain
        if k >= 200:
            if kind == "gain": target[:, w.axis] *= 1-w.severity
            if kind == "bias": target[:, 1] += w.direction*w.severity
            if kind == "deadzone":
                target[:, 0] = np.sign(target[:, 0])*np.maximum(np.abs(target[:, 0])-w.severity, 0)
        tau = w.severity if kind == "lag" and k >= 200 else DT
        actual += min(1., DT/tau)*(target-actual)
        x = x.copy()
        x[:, :2] += DT*actual[:, :1]*np.column_stack([np.cos(x[:, 2]), np.sin(x[:, 2])])
        x[:, 2] += DT*actual[:, 1]
        true[:, k+1] = x
        observed = x.copy()
        if k >= 200:
            if kind == "offset": observed[:, w.axis] += w.direction*w.severity
            if kind == "latency":
                delay = w.severity/DT; left = max(0, int(np.floor(k+1-delay)))
                fraction = k+1-delay-left
                observed = true[:, left]*(1-fraction)+true[:, left+1]*fraction
            if kind == "quantized": observed[:, :2] = np.round(observed[:, :2]/w.severity)*w.severity
            if kind == "held" and (k-200) % max(2, round(w.severity/DT)) != 0:
                observed = measured[:, k]-w.noise[k]
        measured[:, k+1] = observed+w.noise[k+1]
    prefix = dict(pose=measured[0, :PASSIVE+1].astype(np.float32),
                  commands=executed[0, :PASSIVE].astype(np.float32))
    return dict(prefix=prefix, pose=measured[:, PASSIVE+1:].astype(np.float32),
                commands=executed[:, PASSIVE:].astype(np.float32),
                requested=requested[:, PASSIVE:].astype(np.float32),
                violations=(np.abs(true[:, :, :2]) > 3).any((1, 2)), clips=clips,
                violations8=(np.abs(true[:, :401, :2]) > 3).any((1, 2)),
                violations9=(np.abs(true[:, :451, :2]) > 3).any((1, 2)),
                clips8=np.broadcast_to(clips8, (len(x),)).copy(), clips9=clips9,
                effort9=(executed[:, PASSIVE:450]**2).sum((1, 2))*DT,
                disruption9=((executed[:, PASSIVE:450]-w.commands[None, PASSIVE:450])**2).sum((1, 2))*DT,
                effort=(executed[:, PASSIVE:, 0]**2+executed[:, PASSIVE:, 1]**2).sum(1)*DT,
                disruption=((executed[:, PASSIVE:]-w.commands[None, PASSIVE:steps])**2).sum((1, 2))*DT)


def histories(data, end=500):
    n = len(data["pose"])
    pose = np.concatenate([np.broadcast_to(data["prefix"]["pose"], (n, PASSIVE+1, 3)), data["pose"]], axis=1)
    commands = np.concatenate([np.broadcast_to(data["prefix"]["commands"], (n, PASSIVE, 2)), data["commands"]], axis=1)
    return commands[:, :end], pose[:, :end+1]
