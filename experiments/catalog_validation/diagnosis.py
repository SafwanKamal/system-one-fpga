"""Observation-only conventional diagnosis and finite-menu probe selectors."""
from dataclasses import dataclass
import time
import numpy as np
from scipy.special import logsumexp

DT = .02
MENU = np.array([[0, 0], [.04, 0], [.25, 0], [.15, .5], [.15, -.5],
                 [.04, .5], [.04, -.5], [.25, .5], [.25, -.5]], float)
NORMALS = np.random.default_rng(20261117).normal(size=(4, 32, 6))


@dataclass(frozen=True)
class Observation:
    commands: np.ndarray
    pose: np.ndarray


def extract(commands, pose, context=False):
    """Profile least-squares kinematic bank plus broad response features.

    Every feature uses received data only. No mechanism-specific lag/dead-zone
    template is present. The bank contains healthy, gain, turn bias and XY offset.
    """
    u = np.asarray(commands, float); y = np.asarray(pose, float)
    if u.ndim == 2: u = u[None]; y = y[None]
    b, n, _ = u.shape
    t = np.arange(n+1)*DT
    omega = np.c_[np.zeros(b), np.cumsum(u[:, :, 1]*DT, axis=1)]
    healthy = np.column_stack([np.ones(190), omega[0, :190]])
    # Commands in the shared commissioning prefix are identical across branches.
    fit = np.linalg.lstsq(healthy, y[:, :190, 2].T, rcond=None)[0].T
    angle0, gw = fit[:, 0], fit[:, 1].clip(.8, 1.2)
    heading = y[:, :-1, 2]
    motion = np.stack([np.cos(heading), np.sin(heading)], axis=2)*u[:, :, :1]*DT
    integral = np.concatenate([np.zeros((b, 1, 2)), np.cumsum(motion, axis=1)], axis=1)
    centered = integral[:, :190]-integral[:, :190].mean(1, keepdims=True)
    target = y[:, :190, :2]-y[:, :190, :2].mean(1, keepdims=True)
    gv = (np.sum(centered*target, (1, 2))/np.maximum(np.sum(centered**2, (1, 2)), 1e-8)).clip(.8, 1.2)
    xy0 = (y[:, :190, :2]-gv[:, None, None]*integral[:, :190]).mean(1)
    prediction = np.concatenate([xy0[:, None, :]+gv[:, None, None]*integral,
                                  (angle0[:, None]+gw[:, None]*omega)[:, :, None]], axis=2)
    residual = y-prediction
    post = (np.arange(n+1) >= 201).astype(float)
    v_basis = np.concatenate([np.zeros((b, 201, 2)), integral[:, 201:]-integral[:, 200:201]], axis=1)
    w_basis = np.c_[np.zeros((b, 201)), omega[:, 201:]-omega[:, 200:201]]
    time_basis = np.maximum(t-4, 0)
    def coefficient(basis, error):
        return np.sum(basis*error, axis=tuple(range(1, basis.ndim)))/np.maximum(
            np.sum(basis*basis, axis=tuple(range(1, basis.ndim))), 1e-9)
    cv = coefficient(v_basis, residual[:, :, :2]).clip(-.6, -.08)
    cw = coefficient(w_basis, residual[:, :, 2]).clip(-.6, -.08)
    rbv = residual.copy(); rbv[:, :, :2] -= cv[:, None, None]*v_basis
    rbw = residual.copy(); rbw[:, :, 2] -= cw[:, None]*w_basis
    units = np.array([.02, .02, .03])
    sel = np.arange(201, n+1, 4)
    sv = np.mean((rbv[:, sel]/units)**2, (1, 2)); sw = np.mean((rbw[:, sel]/units)**2, (1, 2))
    gain_axis = (sw < sv).astype(int)
    rgain = np.where(gain_axis[:, None, None] == 0, rbv, rbw)
    cb = (np.sum(residual[:, :, 2]*time_basis, 1)/np.maximum(np.sum(time_basis**2), 1e-8)).clip(-.25, .25)
    cb = np.where(cb < 0, -1., 1.)*np.maximum(np.abs(cb), .05)
    rbias = residual.copy(); rbias[:, :, 2] -= cb[:, None]*time_basis
    co = residual[:, 201:, :2].mean(1).clip(-.25, .25)
    length = np.linalg.norm(co, axis=1)
    co = np.where(length[:, None] > 1e-10, co, np.array([1e-10, 0.]))
    co *= np.maximum(1., .04/np.maximum(np.linalg.norm(co, axis=1), 1e-12))[:, None]
    roffset = residual.copy(); roffset[:, :, :2] -= co[:, None, :]*post[None, :, None]
    rs = np.stack([residual, rgain, rbias, roffset], axis=1)
    rms = np.sqrt(np.mean((rs[:, :, sel]/units)**2, axis=2))
    recent = np.sqrt(np.mean((rs[:, :, max(201, n-49):]/units)**2, axis=2))
    scores = np.mean(rms*rms, axis=2)
    components = [rms.reshape(b, -1), recent.reshape(b, -1),
                  np.column_stack([cv, cw, cb, co]),
                  residual[:, 201:].mean(1)/units,
                  residual[:, 201:].std(1)/units]
    # Broad temporal features: block increments and generic cross-correlations.
    block = 10
    yy = y[:, :((n+1)//block)*block].reshape(b, -1, block, 3).mean(2)
    du = np.diff(yy, axis=1)/(.2)
    uu = u[:, :((n)//block)*block].reshape(b, -1, block, 2).mean(2)[:, :du.shape[1]]
    speed = du[:, :, 0]*np.cos(yy[:, :-1, 2])+du[:, :, 1]*np.sin(yy[:, :-1, 2])
    response = np.stack([speed, du[:, :, 2]], axis=2)
    for lag in [0, 1, 2]:
        aa = uu[:, :len(uu[0])-lag or None]; bb = response[:, lag:]
        aa = aa-aa.mean(1, keepdims=True); bb = bb-bb.mean(1, keepdims=True)
        components.append(np.mean(aa*bb, 1)/np.sqrt(np.maximum(np.mean(aa*aa, 1)*np.mean(bb*bb, 1), 1e-10)))
    components += [response.mean(1), response.std(1), np.mean(np.diff(response, axis=1)**2, 1)]
    # Absolute early step helps distinguish a cataloged sensor offset.
    components.append((residual[:, 201:211].mean(1)-residual[:, 185:195].mean(1))/units)
    features = np.concatenate(components, axis=1)
    assert np.isfinite(features).all()
    if not context: return features.astype(np.float32), scores.astype(np.float32)
    return dict(scores=scores[0], gv=gv[0], gw=gw[0], cv=cv[0], cw=cw[0], cb=cb[0],
                offset=co[0], gain_axis=gain_axis[0], last=y[0, -1], previous=u[0, -1])


def forecast(ctx):
    states = np.broadcast_to(ctx["last"], (len(MENU), 4, 3)).copy()
    states[:, 3, :2] -= ctx["offset"]
    saved = []
    for step in range(50):
        u = ctx["previous"]+min(1., (step+1)/5)*(MENU-ctx["previous"])
        v = np.broadcast_to(u[:, :1]*ctx["gv"], (len(MENU), 4)).copy()
        w = np.broadcast_to(u[:, 1:]*ctx["gw"], (len(MENU), 4)).copy()
        if ctx["gain_axis"] == 0: v[:, 1] += u[:, 0]*ctx["cv"]
        else: w[:, 1] += u[:, 1]*ctx["cw"]
        w[:, 2] += ctx["cb"]
        states[:, :, 0] += DT*v*np.cos(states[:, :, 2])
        states[:, :, 1] += DT*v*np.sin(states[:, :, 2])
        states[:, :, 2] += DT*w
        if step in [24, 49]:
            o = states.copy(); o[:, 3, :2] += ctx["offset"]; saved.append(o)
    return np.concatenate(saved, axis=2)


def select(observation, method, scale):
    """Only allowed observation state enters this API; no sibling branches."""
    begin = time.perf_counter()
    ctx = extract(observation.commands, observation.pose, context=True)
    mu = forecast(ctx)
    sigma = np.tile(scale, 2)
    if method == "eig":
        logp = -ctx["scores"]/max(1., float(np.min(ctx["scores"])))
        logp -= logsumexp(logp)
        # Conventional approximate EIG of a four-Gaussian hypothesis mixture.
        values = []
        for means in mu:
            samples = means[:, None, :]+NORMALS*sigma
            ll = -.5*np.sum(((samples[:, :, None, :]-means[None, None, :, :])/sigma)**2, axis=3)
            own = np.stack([ll[i, :, i] for i in range(4)])
            gain = own-logsumexp(ll+logp[None, None, :], axis=2)
            values.append(float(np.sum(np.exp(logp)*gain.mean(1))))
        action = int(np.argmax(values))
    elif method == "overlap":
        # Finite-menu output boxes, NOT a certified reachability implementation.
        values = np.zeros(len(MENU))
        for i in range(4):
            for j in range(i+1, 4):
                width = np.maximum(0., 1-np.abs(mu[:, i]-mu[:, j])/(6*sigma))
                values += np.prod(width, axis=1)
        action = int(np.argmin(values))
    else: raise ValueError(method)
    return action, time.perf_counter()-begin
