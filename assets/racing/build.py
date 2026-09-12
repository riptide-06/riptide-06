#!/usr/bin/env python3
"""Generate the pseudo-3D racing banners for the profile README.

One circuit is defined in 3D world units (x right, y up, z forward). Every
banner is the same circuit seen from a different camera, projected with real
perspective, drawn with a painter's algorithm, and populated with the same 20
cars. Cars are animated with SMIL along the projected paths, with keyPoints so
screen speed follows world speed, and a scale track so they shrink with depth.
Lap times differ per car, so the order changes and cars overtake. The footer
carries a timing tower computed from the same schedule.

Pure standard library. Run from the repository root:

    python3 assets/racing/build.py

Writes assets/racing/*.svg.
"""
import math
import os
import random

OUT = os.path.dirname(os.path.abspath(__file__))
W = 1000
N_CARS = 20
TRACK_W = 12.0
LOOP = 480.0            # timing tower loop, seconds
TOWER_STEP = 2.0        # seconds between tower updates
LAP_SAMPLES = 200       # samples per lap for car paths
random.seed(7)

LIVERIES = [
    ("#e10600", "#ffffff"), ("#1e1e1e", "#e10600"), ("#f4f4f4", "#111111"),
    ("#0f3fa8", "#ffffff"), ("#ff8000", "#111111"), ("#00a19c", "#ffffff"),
    ("#1b8a3a", "#f2e600"), ("#6b2fa0", "#ffffff"), ("#c0c0c0", "#e10600"),
    ("#ffd400", "#111111"), ("#2b2b2b", "#00d2ff"), ("#8b0000", "#ffd400"),
    ("#005aff", "#ff8000"), ("#ffffff", "#0f3fa8"), ("#111111", "#c0c0c0"),
    ("#ff3ea5", "#111111"), ("#3a5f0b", "#ffffff"), ("#00bcd4", "#111111"),
    ("#7a0000", "#ffffff"), ("#404040", "#ff8000"),
]
NUMBERS = [1, 3, 4, 10, 11, 14, 16, 18, 20, 22, 23, 27, 31, 33, 44, 55, 63, 77, 81, 99]


# --------------------------------------------------------------------------
# circuit
# --------------------------------------------------------------------------
def build_circuit():
    """Return a list of dicts: x, z, cmd (command index), turn (+1 right, -1 left, 0 straight)."""
    pts = []
    state = {"x": 0.0, "z": 60.0, "hx": 0.0, "hz": 1.0, "cmd": 0}

    def straight(length, step=4.0):
        n = max(1, int(length / step))
        for k in range(1, n + 1):
            pts.append({"x": state["x"] + state["hx"] * length * k / n,
                        "z": state["z"] + state["hz"] * length * k / n,
                        "cmd": state["cmd"], "turn": 0})
        state["x"] += state["hx"] * length
        state["z"] += state["hz"] * length
        state["cmd"] += 1

    def turn(r, deg, right, step_deg=5.0):
        hx, hz = state["hx"], state["hz"]
        if right:
            cx, cz = state["x"] + hz * r, state["z"] - hx * r
        else:
            cx, cz = state["x"] - hz * r, state["z"] + hx * r
        a0 = math.atan2(state["z"] - cz, state["x"] - cx)
        total = math.radians(deg) * (-1 if right else 1)
        n = max(1, int(deg / step_deg))
        for k in range(1, n + 1):
            a = a0 + total * k / n
            pts.append({"x": cx + r * math.cos(a), "z": cz + r * math.sin(a),
                        "cmd": state["cmd"], "turn": 1 if right else -1})
        state["x"], state["z"] = pts[-1]["x"], pts[-1]["z"]
        ca, sa = math.cos(total), math.sin(total)
        state["hx"], state["hz"] = hx * ca - hz * sa, hx * sa + hz * ca
        state["cmd"] += 1

    # cmd 0: main straight, with the bridge hump around z=300
    straight(540)
    turn(90, 90, True)      # 1  T1
    straight(240)           # 2
    turn(90, 90, True)      # 3  T2
    straight(180)           # 4
    turn(50, 90, False)     # 5  T3
    straight(90)            # 6
    turn(70, 90, True)      # 7  T4
    straight(150)           # 8  back straight
    turn(70, 90, True)      # 9  T5
    straight(260)           # 10
    turn(40, 90, True)      # 11 T6
    straight(140)           # 12
    turn(40, 90, False)     # 13 T7
    straight(340)           # 14 underpass, crosses x=0 at z=300
    turn(60, 90, False)     # 15 T8
    straight(180)           # 16
    turn(60, 90, False)     # 17 T9
    straight(60)            # 18
    turn(60, 90, False)     # 19 T10, back onto the main straight at (0, 60)

    # elevation: hump on the main straight only
    for p in pts:
        p["y"] = 0.0
        if p["cmd"] == 0:
            p["y"] = 9.0 * math.exp(-((p["z"] - 300.0) / 42.0) ** 2)
    # re-index so the lap origin is the start of cmd 18 (no sector wraps)
    start = next(i for i, p in enumerate(pts) if p["cmd"] == 18)
    pts = pts[start:] + pts[:start]
    # cumulative length and lap parameter
    total = 0.0
    for i, p in enumerate(pts):
        q = pts[i - 1]
        d = math.dist((p["x"], p["y"], p["z"]), (q["x"], q["y"], q["z"]))
        total += d
        p["s"] = total
    for p in pts:
        p["p"] = p["s"] / total
    return pts, total


CIRCUIT, LAP_LEN = build_circuit()


def track_point(p, lateral=0.0):
    """World position on the centreline at lap parameter p (0..1), offset laterally."""
    p = p % 1.0
    n = len(CIRCUIT)
    # binary search on parameter
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if CIRCUIT[mid]["p"] < p:
            lo = mid + 1
        else:
            hi = mid
    b = CIRCUIT[lo]
    a = CIRCUIT[lo - 1]
    pa, pb = a["p"], b["p"]
    if lo == 0:
        pa = pa - 1.0
    t = 0.0 if pb == pa else (p - pa) / (pb - pa)
    x = a["x"] + (b["x"] - a["x"]) * t
    y = a["y"] + (b["y"] - a["y"]) * t
    z = a["z"] + (b["z"] - a["z"]) * t
    hx, hz = b["x"] - a["x"], b["z"] - a["z"]
    hl = math.hypot(hx, hz) or 1.0
    hx, hz = hx / hl, hz / hl
    nx, nz = hz, -hx          # right-hand normal
    return (x + nx * lateral, y, z + nz * lateral)


# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------
class Camera:
    def __init__(self, pos, target, f, cx, cy, up=(0.0, 1.0, 0.0)):
        self.pos = pos
        fwd = _norm(_sub(target, pos))
        right = _norm(_cross(fwd, up))
        upv = _cross(right, fwd)
        self.fwd, self.right, self.up = fwd, right, upv
        self.f, self.cx, self.cy = f, cx, cy

    def project(self, p):
        d = _sub(p, self.pos)
        zc = _dot(d, self.fwd)
        if zc < 1.0:
            return None
        xc = _dot(d, self.right)
        yc = _dot(d, self.up)
        return (self.cx + self.f * xc / zc, self.cy - self.f * yc / zc, zc)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    l = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def fit_camera(pos_offset, focus_pts, H, margin=40, min_f=None):
    """Camera looking at the centroid of focus_pts from pos_offset relative to it, scaled to fit."""
    cx = sum(p[0] for p in focus_pts) / len(focus_pts)
    cy = sum(p[1] for p in focus_pts) / len(focus_pts)
    cz = sum(p[2] for p in focus_pts) / len(focus_pts)
    target = (cx, cy, cz)
    pos = (cx + pos_offset[0], cy + pos_offset[1], cz + pos_offset[2])
    cam = Camera(pos, target, 1.0, 0.0, 0.0)
    proj = [cam.project(p) for p in focus_pts]
    proj = [q for q in proj if q]
    umin, umax = min(q[0] for q in proj), max(q[0] for q in proj)
    vmin, vmax = min(q[1] for q in proj), max(q[1] for q in proj)
    f = min((W - 2 * margin) / max(umax - umin, 1e-6), (H - 2 * margin) / max(vmax - vmin, 1e-6))
    if min_f:
        f = max(f, min_f)
    ccx = W / 2 - f * (umin + umax) / 2
    ccy = H / 2 - f * (vmin + vmax) / 2
    return Camera(pos, target, f, ccx, ccy)


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".") if abs(v) >= 0.05 else "0"


CLASSES = {}


def cls(fill):
    if fill not in CLASSES:
        CLASSES[fill] = "c%d" % len(CLASSES)
    return CLASSES[fill]


def quad_svg(cam, pts, fill, opacity=None, stroke=None):
    proj = [cam.project(p) for p in pts]
    if any(q is None for q in proj):
        return None, None
    us = [q[0] for q in proj]
    vs = [q[1] for q in proj]
    if max(us) - min(us) < 1.2 and max(vs) - min(vs) < 1.2:
        return None, None
    depth = sum(q[2] for q in proj) / len(proj)
    d = " ".join("%s,%s" % (fmt(q[0]), fmt(q[1])) for q in proj)
    return depth, '<polygon points="%s" class="%s"/>' % (d, cls(fill))


def box_quads(x0, x1, y0, y1, z0, z1, top, side, side2=None):
    """Axis-aligned box as six faces (world)."""
    side2 = side2 or side
    faces = [
        ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], top, "prop"),
        ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], side, "prop"),
        ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], side, "prop"),
        ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], side2, "prop"),
        ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], side2, "prop"),
    ]
    return faces


def stand_rows(x, z0, z1, heights, fill="#5c5c68"):
    return [([(x, h, z0), (x, h, z1), (x, h + 0.45, z1), (x, h + 0.45, z0)], fill, "prop") for h in heights]


def track_quads():
    """All static track geometry as (points, fill, kind)."""
    quads = []
    n = len(CIRCUIT)
    hw = TRACK_W / 2
    i = 0
    while i < n:
        a = CIRCUIT[i]
        j = i + 1
        if a["turn"] == 0 and a["y"] < 0.25 and not (a["cmd"] == 0 and 90 <= a["z"] <= 110):
            while (j < i + 6 and j < n and CIRCUIT[j]["turn"] == 0 and CIRCUIT[j]["y"] < 0.25
                   and CIRCUIT[j]["cmd"] == a["cmd"] and not (a["cmd"] == 0 and 90 <= CIRCUIT[j]["z"] <= 110)):
                j += 1
        b = CIRCUIT[j % n]
        step = j - i
        i = j
        hx, hz = b["x"] - a["x"], b["z"] - a["z"]
        hl = math.hypot(hx, hz) or 1.0
        nx, nz = hz / hl, -hx / hl
        ay, by = a["y"], b["y"]

        def edge(pt, y, off):
            return (pt["x"] + nx * off, y, pt["z"] + nz * off)

        shade = "#3b3b3f" if int(a["s"] // 12) % 2 == 0 else "#38383c"
        quads.append(([edge(a, ay, -hw), edge(b, by, -hw), edge(b, by, hw), edge(a, ay, hw)], shade, "road"))
        # bridge embankment sides
        if ay > 0.25 or by > 0.25:
            for off in (-hw, hw):
                quads.append(([edge(a, 0.0, off), edge(b, 0.0, off), edge(b, by, off), edge(a, ay, off)], "#2a2a2e", "wall"))
        # kerbs and walls in corners
        if a["turn"] != 0:
            col = "#e10600" if int(a["s"] // 8) % 2 == 0 else "#f4f4f4"
            for off in (-hw, hw):
                o2 = off - 1.6 if off < 0 else off + 1.6
                quads.append(([edge(a, ay, off), edge(b, by, off), edge(b, by, o2), edge(a, ay, o2)], col, "kerb"))
            outer = -hw - 3.2 if a["turn"] > 0 else hw + 3.2
            quads.append(([edge(a, ay, outer), edge(b, by, outer), edge(b, by + 1.4, outer), edge(a, ay + 1.4, outer)], "#d9d9dc", "wall"))
            quads.append(([edge(a, ay + 1.4, outer), edge(b, by + 1.4, outer), edge(b, by + 1.55, outer), edge(a, ay + 1.55, outer)], "#e10600", "wall"))
        # start/finish line on the main straight near z=100
        if a["cmd"] == 0 and 98 <= a["z"] < 102:
            for k in range(6):
                for j in range(2):
                    col = "#111111" if (k + j) % 2 == 0 else "#ffffff"
                    o0 = -hw + k * TRACK_W / 6
                    o1 = o0 + TRACK_W / 6
                    ya = ay
                    quads.append(([edge(a, ya, o0), (a["x"] + nx * o0 + hx / hl * (1.2 * j + 1.2), ya, a["z"] + nz * o0 + hz / hl * (1.2 * j + 1.2)),
                                   (a["x"] + nx * o1 + hx / hl * (1.2 * j + 1.2), ya, a["z"] + nz * o1 + hz / hl * (1.2 * j + 1.2)), edge(a, ya, o1)], col, "kerb"))
    return quads


def ground_bands(x0, x1, z0, z1, step=32.0):
    quads = []
    z = z0
    k = 0
    while z < z1:
        col = "#4f7d3f" if k % 2 == 0 else "#487439"
        quads.append(([(x0, 0.0, z), (x1, 0.0, z), (x1, 0.0, z + step), (x0, 0.0, z + step)], col, "ground"))
        z += step
        k += 1
    return quads


# --------------------------------------------------------------------------
# cars
# --------------------------------------------------------------------------
SPEED_RANK = list(range(N_CARS))
random.shuffle(SPEED_RANK)
LAP_TIME = [20.0 + 0.2 * SPEED_RANK[i] for i in range(N_CARS)]
LATERAL = [(-3.6, -1.2, 1.2, 3.6)[i % 4] for i in range(N_CARS)]
# grid at t=0: car i sits at slot i on the main straight, 8 units apart, from z=120 back to z=272
GRID_PARAM = []
for i in range(N_CARS):
    z = 120.0 + 8.0 * i
    # parameter of the main straight point at this z
    cand = [p for p in CIRCUIT if p["cmd"] == 0]
    best = min(cand, key=lambda p: abs(p["z"] - z))
    GRID_PARAM.append(best["p"])
# the grid is ordered with slot 0 at the front, so slot 0 has the largest parameter
OFFSET = [GRID_PARAM[i] * LAP_TIME[i] for i in range(N_CARS)]


def car_sprite(i):
    main, accent = LIVERIES[i]
    num = NUMBERS[i]
    return (
        '<g id="car%d">'
        '<ellipse cx="0.15" cy="0.35" rx="2.7" ry="1.35" fill="#000" opacity="0.32"/>'
        '<rect x="-1.9" y="-1.15" width="0.75" height="0.5" rx="0.12" fill="#141414"/>'
        '<rect x="-1.9" y="0.65" width="0.75" height="0.5" rx="0.12" fill="#141414"/>'
        '<rect x="1.0" y="-1.1" width="0.65" height="0.45" rx="0.12" fill="#141414"/>'
        '<rect x="1.0" y="0.65" width="0.65" height="0.45" rx="0.12" fill="#141414"/>'
        '<rect x="-2.35" y="-1.05" width="0.42" height="2.1" rx="0.1" fill="%s" stroke="#000" stroke-width="0.06"/>'
        '<rect x="1.95" y="-1.05" width="0.36" height="2.1" rx="0.1" fill="%s" stroke="#000" stroke-width="0.06"/>'
        '<rect x="-1.3" y="-0.8" width="1.7" height="1.6" rx="0.35" fill="%s" stroke="#000" stroke-width="0.07"/>'
        '<rect x="-2.0" y="-0.42" width="4.05" height="0.84" rx="0.42" fill="%s" stroke="#000" stroke-width="0.07"/>'
        '<rect x="-2.0" y="-0.1" width="4.05" height="0.2" fill="%s" opacity="0.9"/>'
        '<circle cx="-0.25" cy="0" r="0.3" fill="#111"/>'
        '<circle cx="-0.25" cy="0" r="0.17" fill="%s"/>'
        '<text x="-0.55" y="-0.95" font-family="Arial, Helvetica, sans-serif" font-size="0.62" font-weight="700" fill="%s" text-anchor="middle">%d</text>'
        '</g>'
    ) % (i, accent, accent, main, main, accent, accent, accent, num)


def car_paths(cam, i, H, bands=None):
    """Visible windows for car i under this camera.

    Returns list of dicts: layer ('far'|'near'), path d, keyTimes, keyPoints, scales.
    """
    samples = []
    for k in range(LAP_SAMPLES + 1):
        p = k / LAP_SAMPLES
        wp = track_point(p, LATERAL[i])
        q = cam.project(wp)
        vis = q is not None and -80 <= q[0] <= W + 80 and -80 <= q[1] <= H + 80 and q[2] > 4.0
        layer = "near"
        if bands and q is not None:
            far_b, near_b = bands
            if q[2] > far_b or (near_b <= q[2] <= far_b and wp[1] < 3.0):
                layer = "far"
        samples.append((p, q, vis, layer))
    windows = []
    run = []
    for s in samples:
        if s[2] and (not run or run[-1][3] == s[3]):
            run.append(s)
        else:
            if len(run) >= 3:
                windows.append(run)
            run = [s] if s[2] else []
    if len(run) >= 3:
        windows.append(run)
    out = []
    for run in windows:
        pts = [s[1] for s in run]
        # cumulative screen length
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        tot = cum[-1] or 1.0
        p0, p1 = run[0][0], run[-1][0]
        p0 = max(p0, 0.0005)
        p1 = min(p1, 0.9995)
        if p1 <= p0:
            continue
        # decimate path points on near-straight runs to keep files small
        keep = [0]
        for k in range(1, len(pts) - 1):
            a, b, c = pts[keep[-1]], pts[k], pts[k + 1]
            ang = abs(math.atan2(b[1] - a[1], b[0] - a[0]) - math.atan2(c[1] - b[1], c[0] - b[0]))
            if ang > 0.02 or (k - keep[-1]) >= 6:
                keep.append(k)
        keep.append(len(pts) - 1)
        d = "M" + " L".join("%s,%s" % (fmt(pts[k][0]), fmt(pts[k][1])) for k in keep)
        kt = [0.0, p0] + [p0 + (p1 - p0) * (cum[k] / tot if False else (run[k][0] - run[0][0]) / (run[-1][0] - run[0][0])) for k in range(1, len(run) - 1)] + [p1, 1.0]
        kp = [0.0, 0.0] + [cum[k] / tot for k in range(1, len(run) - 1)] + [1.0, 1.0]
        sc = [cam.f / pts[0][2], cam.f / pts[0][2]] + [cam.f / pts[k][2] for k in range(1, len(run) - 1)] + [cam.f / pts[-1][2], cam.f / pts[-1][2]]
        # thin out keyTimes to every other sample when long
        if tot < 40.0:
            continue
        if len(kt) > 24:
            idx = [0, 1] + list(range(2, len(kt) - 2, 3)) + [len(kt) - 2, len(kt) - 1]
            kt = [kt[j] for j in idx]
            kp = [kp[j] for j in idx]
            sc = [sc[j] for j in idx]
        out.append({"layer": run[0][3], "d": d, "kt": kt, "kp": kp, "sc": sc, "p0": p0, "p1": p1})
    return out


def car_instances(cam, H, bands=None):
    """Return (defs, far_layer_svg, near_layer_svg)."""
    defs = []
    far, near = [], []
    for i in range(N_CARS):
        defs.append(car_sprite(i))
        for w, win in enumerate(car_paths(cam, i, H, bands)):
            pid = "p%d_%d" % (i, w)
            defs.append('<path id="%s" d="%s"/>' % (pid, win["d"]))
            T = LAP_TIME[i]
            begin = -OFFSET[i]
            kt = ";".join("%.4f" % v for v in win["kt"])
            kp = ";".join("%.4f" % v for v in win["kp"])
            sc = ";".join("%.3f" % v for v in win["sc"])
            g = (
                '<g opacity="0">'
                '<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;%.4f;%.4f;1" calcMode="discrete" dur="%.2fs" begin="%.3fs" repeatCount="indefinite"/>'
                '<animateMotion dur="%.2fs" begin="%.3fs" repeatCount="indefinite" rotate="auto" calcMode="linear" keyTimes="%s" keyPoints="%s"><mpath href="#%s" xlink:href="#%s"/></animateMotion>'
                '<g><animateTransform attributeName="transform" type="scale" values="%s" keyTimes="%s" dur="%.2fs" begin="%.3fs" repeatCount="indefinite"/>'
                '<use href="#car%d" xlink:href="#car%d"/></g></g>'
            ) % (win["p0"], win["p1"], T, begin, T, begin, kt, kp, pid, pid, sc, kt, T, begin, i, i)
            (far if win["layer"] == "far" else near).append(g)
    return "\n".join(defs), "\n".join(far), "\n".join(near)


# --------------------------------------------------------------------------
# timing tower
# --------------------------------------------------------------------------
def tower_svg(x, y, rows=6):
    steps = int(LOOP / TOWER_STEP)
    orders = []
    for k in range(steps):
        t = k * TOWER_STEP
        dist = [(t + OFFSET[i]) / LAP_TIME[i] for i in range(N_CARS)]
        order = sorted(range(N_CARS), key=lambda i: -dist[i])
        orders.append(order[:rows])
    out = ['<g transform="translate(%d,%d)">' % (x, y)]
    out.append('<rect x="0" y="0" width="150" height="%d" rx="6" fill="#0d0d0f" opacity="0.88"/>' % (rows * 24 + 30))
    out.append('<rect x="0" y="0" width="150" height="24" rx="6" fill="#e10600"/>')
    out.append('<text x="10" y="17" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" fill="#fff">LIVE TIMING</text>')
    for r in range(rows):
        yy = 30 + r * 24
        out.append('<text x="10" y="%d" font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700" fill="#9a9a9a">P%d</text>' % (yy + 16, r + 1))
        for i in range(N_CARS):
            vals = ["1" if orders[k][r] == i else "0" for k in range(steps)]
            if "1" not in vals:
                continue
            main, accent = LIVERIES[i]
            out.append(
                '<g opacity="0"><animate attributeName="opacity" values="%s" calcMode="discrete" dur="%.0fs" repeatCount="indefinite"/>'
                '<rect x="40" y="%d" width="6" height="18" fill="%s"/>'
                '<text x="54" y="%d" font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" fill="#f2f2f2">#%d</text>'
                '<text x="140" y="%d" font-family="Arial, Helvetica, sans-serif" font-size="11" fill="#c8c8c8" text-anchor="end">%.1fs</text></g>'
                % (";".join(vals), LOOP, yy + 3, main, yy + 16, NUMBERS[i], yy + 16, LAP_TIME[i])
            )
    out.append("</g>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# banner assembly
# --------------------------------------------------------------------------
def render(name, H, cam, bands=None, sky=False, extras_world=None, extras_screen="", ground=None, title=None):
    CLASSES.clear()
    quads = track_quads()
    if ground:
        quads = ground_bands(*ground) + quads
    if extras_world:
        quads += extras_world
    drawn = []
    for pts, fill, kind in quads:
        depth, svg = quad_svg(cam, pts, fill)
        if svg is None:
            continue
        # cull quads entirely off screen
        proj = [cam.project(p) for p in pts]
        us = [q[0] for q in proj]
        vs = [q[1] for q in proj]
        if max(us) < -50 or min(us) > W + 50 or max(vs) < -50 or min(vs) > H + 50:
            continue
        drawn.append((depth, kind, svg))
    for depth, svg in tree_items(cam):
        drawn.append((depth, "prop", svg))
    drawn.sort(key=lambda d: -d[0])
    ground_svg = [s for d, k, s in drawn if k == "ground"]
    rest = [(d, k, s) for d, k, s in drawn if k != "ground"]
    if bands:
        far_b, near_b = bands
        far_q = [s for d, k, s in rest if d > far_b]
        band_q = [s for d, k, s in rest if near_b <= d <= far_b]
        near_q = [s for d, k, s in rest if d < near_b]
    else:
        far_q, band_q, near_q = [], [], [s for d, k, s in rest]
    defs, far_cars, near_cars = car_instances(cam, H, bands)

    out = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">' % (W, H, W, H, title or "Racing")]
    out.append("<defs>")
    out.append("")  # placeholder for the style block
    out.append('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c9dcef"/><stop offset="1" stop-color="#f3f6f9"/></linearGradient>')
    out.append('<linearGradient id="haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9eef2" stop-opacity="0.9"/><stop offset="1" stop-color="#e9eef2" stop-opacity="0"/></linearGradient>')
    out.append('<linearGradient id="vig" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.18"/><stop offset="0.35" stop-color="#000" stop-opacity="0"/></linearGradient>')
    out.append(defs)
    out.append("</defs>")
    if sky:
        out.append('<rect width="%d" height="%d" fill="url(#sky)"/>' % (W, H))
    else:
        out.append('<rect width="%d" height="%d" fill="#4a7639"/>' % (W, H))
    out.extend(ground_svg)
    if sky:
        hz = cam.cy - cam.f * (0.0 - cam.pos[1]) / 100000.0
        out.append('<rect x="0" y="%s" width="%d" height="60" fill="url(#haze)"/>' % (fmt(hz - 2), W))
    out.extend(far_q)
    out.append(far_cars)
    out.extend(band_q)
    out.extend(near_q)
    out.append(near_cars)
    out.append(extras_screen)
    if not sky:
        out.append('<rect width="%d" height="%d" fill="url(#vig)"/>' % (W, H))
    out.append("</svg>")
    style = "<style>" + "".join(".%s{fill:%s;stroke:%s;stroke-width:0.7;stroke-linejoin:round}" % (c, f, f) for f, c in CLASSES.items()) + "</style>"
    out[2] = style
    path = os.path.join(OUT, name)
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    print("%-16s %6.1f KB  cars(far/near)=%d/%d" % (name, os.path.getsize(path) / 1024, far_cars.count("<animateMotion"), near_cars.count("<animateMotion")))


TREES = []
_rng = random.Random(11)
_pts2d = [(p["x"], p["z"]) for p in CIRCUIT]
while len(TREES) < 70:
    tx = _rng.uniform(-330.0, 780.0)
    tz = _rng.uniform(-120.0, 840.0)
    dmin = min(math.hypot(tx - a, tz - b) for a, b in _pts2d[::3])
    if 26.0 < dmin < 140.0 and not (-40.0 < tx < 45.0 and 90.0 < tz < 540.0):
        TREES.append((tx, tz, _rng.uniform(5.0, 8.5)))


def tree_items(cam):
    """Return list of (depth, svg) for trees visible to this camera."""
    items = []
    for tx, tz, h in TREES:
        base = cam.project((tx, 0.0, tz))
        top = cam.project((tx, h, tz))
        if base is None or top is None:
            continue
        if base[0] < -40 or base[0] > W + 40 or top[1] > 2000 or base[1] < -40:
            continue
        r = cam.f * (h * 0.55) / top[2]
        if r < 0.8:
            continue
        trunk_w = max(0.6, cam.f * 0.5 / base[2])
        svg = ('<rect x="%s" y="%s" width="%s" height="%s" fill="#4a3320"/>'
               '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#2f5e2a"/>'
               '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#3d7a35"/>'
               % (fmt(base[0] - trunk_w / 2), fmt(top[1]), fmt(trunk_w), fmt(max(0.5, base[1] - top[1])),
                  fmt(top[0]), fmt(top[1]), fmt(r), fmt(r * 0.95),
                  fmt(top[0] - r * 0.2), fmt(top[1] - r * 0.2), fmt(r * 0.6), fmt(r * 0.55)))
        items.append((base[2], svg))
    return items


def sector_points(cmds):
    return [(p["x"], p["y"], p["z"]) for p in CIRCUIT if p["cmd"] in cmds]


def header():
    H = 300
    cam = Camera((0.0, 15.0, 40.0), (0.0, 3.0, 420.0), 640.0, W / 2, 112.0)
    # occluder band: the crest of the bridge (z 260..340 from a camera at z=40)
    bands = (300.0, 215.0)
    extras = []
    # grandstands and pit building
    extras += box_quads(-34.0, -16.0, 0.0, 9.0, 130.0, 520.0, "#3a3a42", "#26262c", "#2f2f36")
    extras += stand_rows(-15.95, 130.0, 520.0, [1.6, 3.2, 4.8, 6.4, 8.0])
    extras += box_quads(16.0, 40.0, 0.0, 6.5, 125.0, 300.0, "#3d3d45", "#28282e", "#32323a")
    extras += stand_rows(15.95, 125.0, 300.0, [1.6, 3.2, 4.8], fill="#e10600")
    extras += box_quads(8.0, 9.2, 0.0, 1.1, 110.0, 330.0, "#e6e6e6", "#cfcfcf")   # pit wall
    # gantry posts and beam at z=95
    extras += box_quads(-9.5, -8.5, 0.0, 7.5, 94.5, 95.5, "#d0d0d0", "#8a8a8a")
    extras += box_quads(8.5, 9.5, 0.0, 7.5, 94.5, 95.5, "#d0d0d0", "#8a8a8a")
    extras += box_quads(-9.5, 9.5, 7.5, 8.6, 94.2, 95.8, "#c8c8c8", "#6e6e6e")
    # start lights cluster hanging under the beam
    lights = ""
    for k in range(5):
        wp = (-3.2 + 1.6 * k, 6.9, 95.0)
        q = cam.project(wp)
        r = cam.f * 0.5 / q[2]
        lights += ('<circle cx="%s" cy="%s" r="%s" fill="#3a0000" stroke="#111" stroke-width="0.6">'
                   '<animate attributeName="fill" values="#3a0000;#3a0000;#ff1a1a;#ff1a1a;#3a0000;#3a0000" keyTimes="0;%.3f;%.3f;0.42;0.43;1" calcMode="discrete" dur="20s" repeatCount="indefinite"/></circle>'
                   % (fmt(q[0]), fmt(q[1]), fmt(r), 0.05 + 0.06 * k, 0.05 + 0.06 * k + 0.001))
    screen = (
        '<text x="500" y="62" text-anchor="middle" font-family="Segoe UI, Helvetica Neue, Helvetica, Arial, sans-serif" font-size="54" font-weight="800" letter-spacing="2" fill="#0b0b0b">TARUN CHANDRA</text>'
        '<text x="500" y="90" text-anchor="middle" font-family="Segoe UI, Helvetica Neue, Helvetica, Arial, sans-serif" font-size="19" font-weight="600" letter-spacing="3" fill="#0b0b0b">AI-NATIVE PRODUCT BUILDER</text>'
        '<rect x="440" y="98" width="120" height="3" fill="#e10600"/>'
    ) + lights
    render("header.svg", H, cam, bands=bands, sky=True, extras_world=extras, extras_screen=screen,
           ground=(-420.0, 420.0, 40.0, 1600.0, 24.0), title="Race start on the main straight")


def divider(name, cmds, offset, H=190, title="Sector"):
    pts = sector_points(cmds)
    cam = fit_camera(offset, pts, H, margin=22)
    bbox = (min(p["x"] for p in CIRCUIT) - 200, max(p["x"] for p in CIRCUIT) + 200,
            min(p["z"] for p in CIRCUIT) - 200, max(p["z"] for p in CIRCUIT) + 200, 24.0)
    render(name, H, cam, ground=bbox, title=title)


def underpass():
    H = 210
    pts = sector_points([13, 14]) + [(0.0, 9.0, 300.0), (0.0, 0.0, 250.0), (0.0, 0.0, 350.0)]
    cam = fit_camera((30.0, 75.0, -280.0), pts, H, margin=22)
    # bands around the bridge deck: deck points project near depth of (0, 9, 300)
    d = cam.project((0.0, 9.0, 300.0))[2]
    bands = (d + 12.0, d - 12.0)
    bbox = (min(p["x"] for p in CIRCUIT) - 200, max(p["x"] for p in CIRCUIT) + 200,
            min(p["z"] for p in CIRCUIT) - 200, max(p["z"] for p in CIRCUIT) + 200, 24.0)
    render("underpass.svg", H, cam, bands=bands, ground=bbox, title="Turns 6 and 7 into the underpass beneath the main straight")


def footer():
    H = 280
    cam = Camera((30.0, 18.0, 280.0), (-20.0, 2.0, 20.0), 520.0, W / 2 + 40, 105.0)
    extras = []
    extras += box_quads(-34.0, -16.0, 0.0, 9.0, 130.0, 520.0, "#3a3a42", "#26262c", "#2f2f36")
    extras += stand_rows(-15.95, 130.0, 520.0, [1.6, 3.2, 4.8, 6.4, 8.0])
    extras += box_quads(8.0, 9.2, 0.0, 1.1, 110.0, 330.0, "#e6e6e6", "#cfcfcf")
    screen = tower_svg(20, 20, rows=8)
    render("footer.svg", H, cam, sky=True, extras_world=extras, extras_screen=screen,
           ground=(-500.0, 500.0, -300.0, 1600.0, 24.0), title="Final corner onto the main straight, with live timing")


if __name__ == "__main__":
    print("lap length %.0f units, %d centreline points" % (LAP_LEN, len(CIRCUIT)))
    header()
    divider("t1-t2.svg", [1, 2, 3], (20.0, 120.0, -320.0), title="Turns 1 and 2")
    divider("t3-esses.svg", [4, 5, 6], (300.0, 110.0, 30.0), title="Turn 3 esses")
    divider("t4-back-straight.svg", [7, 8], (300.0, 100.0, -40.0), title="Turn 4 and the back straight")
    divider("t5.svg", [9, 10], (-30.0, 120.0, -300.0), title="Turn 5 onto the lower straight")
    underpass()
    divider("t8-t9.svg", [15, 16, 17], (-300.0, 110.0, 30.0), title="Turns 8 and 9")
    footer()
