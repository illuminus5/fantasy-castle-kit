"""The castle kit's pieces: one dict per piece. Shapes come from kit.py (chamfered boxes, lathes,
prisms); numbers come from castle_grid.py; the look follows inspiration/ref_*.png (timber & moss).

The Col mask has four tint areas: red A, green B, blue C, and a clear mask (alpha 0) D. A mask dimmer than 1 darkens
that face: stone "skins" of thin block quads sit just proud of a darker (mortar) body, each block a little lighter or
darker, so walls read as masonry for two triangles a block and still recolour with any theme.

Keys:
  id, name          id is [a-z0-9_] (engines rename nodes otherwise)
  category          the GLB it goes into: export/<category>.glb
  roles             four theme roles for tint areas A, B, C, D (themes.json maps roles to colours)
  cells             footprint cells [x, y, z] in catalog axes (glTF: x = Blender x, z = -Blender y); the first is the origin's
  faces             per cell, {face: socket}; n e s w u d in catalog axes (castle_grid docstring); missing = open
  sym               how many of the 4 quarter turns look different (1, 2 or 4)
  layer             "main", or "ground" for tiles under the first level
  gen               generator hints: weight w, allowed levels y [lo, hi], tags
  build             a function returning the finished mesh object, or a dict {"base": object, part: object, ...}
  parts             {part: [condition, ...]} or {part: {"cell": i, "when": [...]}}: a part shows when every condition
                    holds for footprint cell i (default 0). A condition is "<face>[-]:[!]<what>": the neighbour across
                    that face (one level down too with "-"); <what> is the socket it shows us, "#tag" for its tags, or
                    "empty". Exported as mesh <id>__<part>; the engine merges base + the parts that hold.
"""
import math
import random

import castle_grid as G
import kit
from castle_grid import H, MERLON, TOWER_R, WALL
from kit import ball, box, cyl, joined, lathe, mirrored, move, prism, turn

A, B, C, D = 0, 1, 2, 3
STONE, MOSS, WOOD, IRON = A, B, C, D  # the areas on stone pieces (roles stone, moss, timber, iron)
MASK = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1), (0, 0, 0, 0)]
MORTAR = 0.74  # a body's shade behind its block skin
CELL_THIRD = G.CELL / 3  # the merlon rhythm
W2 = WALL / 2
R = TOWER_R


# ---- paint

def tint(ob, area, shade=1.0, where=None):
    """Paint faces with an area at a shade (1 = full colour): all of them, or those where(centre, normal) holds."""
    col = kit._layers(ob.data)[0]
    m = MASK[area]
    rgba = (m[0] * shade, m[1] * shade, m[2] * shade, m[3])
    for p in ob.data.polygons:
        if where is None or where(p.center, p.normal):
            for li in p.loop_indices:
                col.data[li].color = rgba
    return ob


def build(*parts):
    """Join parts into one piece: each part is a painted object, or (area, object), or (area, shade, object)."""
    obs = []
    for p in parts:
        if isinstance(p, tuple):
            ob = tint(p[-1], p[0], p[1] if len(p) == 3 else 1.0)
        else:
            ob = p
        obs.append(ob)
    return joined(*obs)


def moss_tops(ob, rng, chance):
    """Paint some upward faces moss (merlon caps, ledges)."""
    return tint(ob, MOSS, 1.0, lambda c, n: n.z > 0.9 and rng.random() < chance)


# ---- looks: a base and optional parts (see "parts" in the module docstring)

# Blender yaw that turns something built on the east side (+X) to each face (n is Blender -Y, s is +Y)
FROM_E = {"e": 0, "n": -90, "w": 180, "s": 90}
# and something built on the north side (Blender -Y)
FROM_N = {"n": 0, "e": 90, "s": 180, "w": -90}


def turned(look, degrees):
    for ob in look.values():
        turn(ob, "z", degrees)
    return look


def merged(*looks):
    """Looks joined part by part."""
    keys = dict.fromkeys(k for lk in looks for k in lk)
    return {k: joined(*[lk[k] for lk in looks if k in lk]) for k in keys}


# ---- skins

def _skin_object(name, quads, looks):
    verts, faces = [], []
    for q in quads:
        i = len(verts)
        verts += q
        faces.append((i, i + 1, i + 2, i + 3))
    ob = kit.new_object(name, verts, faces)
    col = kit._layers(ob.data)[0]
    for p, (area, shade) in zip(ob.data.polygons, looks):
        m = MASK[area]
        for li in p.loop_indices:
            col.data[li].color = (m[0] * shade, m[1] * shade, m[2] * shade, m[3])
    return ob


def skin_plane(name, x0, x1, z0, z1, y, facing, seed, block=0.5, course=0.32, skip=None, moss_low=0.0, row0=0):
    """Stone blocks on a wall face in the x-z plane at y, facing -Y (facing -1) or +Y (+1): quads 12 mm proud,
    offset courses, mortar gaps between. skip(x, z) leaves a block out (doors, windows); blocks lower than
    moss_low above z0 are mossy half the time. row0 is the first course's number, so a skin that carries on another
    (a wall's top course over its body) keeps the courses' alternating offsets."""
    rng = random.Random(seed)
    quads, looks, gap = [], [], 0.025
    yy = y + facing * 0.012
    z, row = z0, row0
    while z < z1 - 0.05:
        h = min(course, z1 - z)
        x = x0 - (block / 2 if row % 2 else 0)
        while x < x1 - 0.05:
            xa, xb = max(x, x0), min(x + block, x1)
            if xb - xa > 0.08 and not (skip and skip((xa + xb) / 2, z + h / 2)):
                a, b = xa + gap / 2, xb - gap / 2
                lo, hi = z + gap / 2, z + h - gap / 2
                q = [(a, yy, lo), (b, yy, lo), (b, yy, hi), (a, yy, hi)]
                quads.append(q if facing < 0 else q[::-1])
                mossy = z - z0 < moss_low and rng.random() < 0.5
                looks.append((MOSS, 1.0) if mossy else (STONE, rng.uniform(0.86, 1.0)))
            x += block
        z += h
        row += 1
    return _skin_object(name, quads, looks)


def skin_ring(name, r, z0, z1, seed, segments=16, course=0.32, skip=None, moss_low=0.0):
    """Stone blocks round a tower of radius r: one quad per segment per course, every other course offset by half."""
    rng = random.Random(seed)
    quads, looks = [], []
    rr = r + 0.012
    z, row = z0, 0
    while z < z1 - 0.05:
        h = min(course, z1 - z)
        shift = 0.5 * (row % 2)
        g = 0.0125 / rr
        for s in range(segments):
            a0 = 2 * math.pi * (s + shift) / segments + g
            a1 = 2 * math.pi * (s + 1 + shift) / segments - g
            lo, hi = z + 0.0125, z + h - 0.0125
            mid = (a0 + a1) / 2
            if skip and skip(math.cos(mid) * rr, math.sin(mid) * rr, (lo + hi) / 2):
                continue
            c0, s0, c1, s1 = math.cos(a0) * rr, math.sin(a0) * rr, math.cos(a1) * rr, math.sin(a1) * rr
            quads.append([(c0, s0, lo), (c1, s1, lo), (c1, s1, hi), (c0, s0, hi)])
            mossy = z - z0 < moss_low and rng.random() < 0.5
            looks.append((MOSS, 1.0) if mossy else (STONE, rng.uniform(0.86, 1.0)))
        z += h
        row += 1
    return _skin_object(name, quads, looks)


# ---- walls

WALL_TOP = 1.8  # a curtain wall's coping; its walk


COURSE = 0.32  # a stone course; a wall's plinth is one course high


def wall_skins(name, x0, x1, z0, z1, row0, skip_front=None, skip_back=None, moss_low=0.0):
    """A wall's mortar body from z0 to z1 with block skins on both faces."""
    cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
    return [
        (STONE, MORTAR, box(f"{name}_body", (cx, 0, (z0 + z1) / 2), (hx, W2, (z1 - z0) / 2), bevel=0.0)),
        skin_plane(name + "_front", x0, x1, z0, z1, -W2, -1, name + "f", skip=skip_front, moss_low=moss_low, row0=row0),
        skin_plane(name + "_back", x0, x1, z0, z1, W2, 1, name + "b", skip=skip_back, moss_low=moss_low, row0=row0),
    ]


def wall_body(name, x0, x1, skip_front=None, skip_back=None, top=WALL_TOP):
    """A curtain wall along X from x0 to x1: a mortar body with block skins on both faces, from one course up to the
    walk, and four parts, so that a wall standing on a wall reads as one taller wall:
      plinth  the footing course and its moss, on the ground          sole  the bottom course of body, on a wall
      crown   coping and merlons (on a 2/3 m rhythm fixed to the grid, so runs from different pieces line up)
      fill    the body and skins carried up to the next level, under a wall standing on this one."""
    rng = random.Random(name)
    cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
    above = math.ceil((top - COURSE) / COURSE - 1e-6)  # the courses from the plinth to the walk
    plinth = [(STONE, 0.9, box(name + "_plinth", (cx, 0, COURSE / 2), (hx, W2 + 0.07, COURSE / 2), bevel=0.05))]
    for i in range(2):
        x = rng.uniform(x0 + 0.3, x1 - 0.3)
        plinth.append((MOSS, box(f"{name}_moss{i}", (x, -(W2 + 0.07), COURSE + 0.01), (rng.uniform(0.12, 0.25), 0.03, 0.025), bevel=0.01)))
    cap = moss_tops(tint(box(name + "_coping", (cx, 0, top + 0.06), (hx, W2 + 0.04, 0.06), bevel=0.02), STONE, 0.95), rng, 0.25)
    crown = []
    mw, mh = MERLON
    k = math.ceil((x0 + mw / 2) / CELL_THIRD - 1e-6)
    while k * CELL_THIRD + mw / 2 <= x1 + 1e-6:
        for side in (-1, 1):
            m = box(f"{name}_m{k}{side}", (k * CELL_THIRD, side * (W2 - 0.12), top + 0.12 + mh / 2), (mw / 2, 0.11, mh / 2), bevel=0.03)
            crown.append(moss_tops(tint(m, STONE, rng.uniform(0.88, 1.0)), rng, 0.3))
        k += 1
    return {
        "base": build(*wall_skins(name, x0, x1, COURSE, top, 0, skip_front, skip_back, moss_low=0.4)),
        "plinth": build(*plinth),
        "sole": build(*wall_skins(name + "_sole", x0, x1, 0.0, COURSE, 1)),
        "cap": cap,
        "crown": build(*crown),
        "fill": build(*wall_skins(name + "_fill", x0, x1, top, G.LEVEL, above)),
    }


def arch_door(name, at_x, y, bottom, width, height, facing=-1):
    """An oak door with a round top and iron bands, framed by stone jambs and a ring of voussoirs, on a face at y."""
    hw = width / 2
    door = box(name + "_door", (at_x, y + facing * 0.01, bottom + (height - hw) / 2), (hw, 0.035, (height - hw) / 2), bevel=0.01)
    top = cyl(name + "_doortop", (at_x, y + facing * 0.01, bottom + height - hw), hw, 0.07, axis="y", segments=12)
    parts = [(WOOD, door), (WOOD, top)]
    for z in (bottom + 0.28, bottom + 0.62):
        parts.append((IRON, box(f"{name}_band{z:.2f}", (at_x, y + facing * 0.05, z), (hw + 0.01, 0.012, 0.03), bevel=0.0)))
    for side in (-1, 1):
        parts.append((STONE, 1.0, box(f"{name}_jamb{side}", (at_x + side * (hw + 0.07), y + facing * 0.02, bottom + (height - hw) / 2),
                                      (0.07, 0.05, (height - hw) / 2), bevel=0.015)))
    for i in range(7):
        a = math.pi * (i + 0.5) / 7
        v = box(f"{name}_vous{i}", (0, 0, 0), (0.06, 0.05, 0.1), bevel=0.015)
        turn(v, "y", -math.degrees(a) + 90)
        move(v, (at_x + math.cos(a) * (hw + 0.08), y + facing * 0.02, bottom + height - hw + math.sin(a) * (hw + 0.08)))
        parts.append((STONE, 1.0, v))
    return build(*parts)


def wall_straight():
    return wall_body("wall_straight", -H, H)


def wall_corner():
    """Arms to the east (+X) and to the front (n, Blender -Y). Asymmetric on purpose: it also checks the engine's
    axis conversion (the arms must point where the catalog's e and n faces say)."""
    east = wall_body("wall_corner", -W2, H)
    front = turned(wall_body("wall_corner_n", W2, H), -90)
    return merged(east, front)


def wall_t():
    run = wall_body("wall_t", -H, H)
    arm = turned(wall_body("wall_t_n", W2, H), -90)
    return merged(run, arm)


def wall_end():
    """A wall from the west edge ending in a small round turret at the cell's centre: a plinth, a block-skinned
    drum a little wider than the wall and, as its crown, a corbelled ring of merlons standing just above the wall's."""
    run = wall_body("wall_end", -H, 0.0)
    rng = random.Random("wall_end")
    tr = 0.56
    base = [
        run["base"],
        (STONE, MORTAR, lathe("wall_end_drum", [(0, COURSE), (tr, COURSE), (tr, G.LEVEL), (0, G.LEVEL)], segments=12)),
        skin_ring("wall_end_skin", tr, COURSE, G.LEVEL, "wall_end", segments=12, moss_low=0.4),
    ]
    plinth = [run["plinth"], (STONE, 0.9, lathe("wall_end_plinth", [(0, 0), (tr + 0.08, 0), (tr + 0.08, 0.16), (tr, COURSE), (0, COURSE)], segments=12))]
    sole = [run["sole"], (STONE, MORTAR, lathe("wall_end_sdrum", [(0, 0), (tr, 0), (tr, COURSE), (0, COURSE)], segments=12)),
            skin_ring("wall_end_sskin", tr, 0.0, COURSE, "wall_end_s", segments=12)]
    corbel = lathe("wall_end_corbel", [(tr - 0.05, G.LEVEL), (tr + 0.1, G.LEVEL + 0.1), (tr + 0.1, G.LEVEL + 0.16),
                                       (0, G.LEVEL + 0.16)], segments=12)
    crown = [run["crown"], moss_tops(tint(corbel, STONE, 0.95), rng, 0.3)]
    crown += ring_of("wall_end_m", 6, tr - 0.02, G.LEVEL + 0.16, (0.14, 0.08, 0.13), rng)
    return {"base": build(*base), "plinth": build(*plinth), "sole": build(*sole), "cap": run["cap"], "crown": build(*crown), "fill": run["fill"]}


def wall_window():
    """A wall with two arrow slits, framed in pale stone, shuttered in oak."""
    def skip(x, z):
        return any(abs(x - sx) < 0.2 for sx in (-0.5, 0.5)) and 0.75 < z < 1.5
    run = wall_body("wall_window", -H, H, skip_front=skip, skip_back=skip)
    parts = [run["base"]]
    for sx in (-0.5, 0.5):
        for side in (-1, 1):
            y = side * (W2 + 0.012)
            parts.append((WOOD, 0.8, box(f"wall_window_slit{sx}{side}", (sx, y, 1.12), (0.05, 0.02, 0.3), bevel=0.0)))
            parts.append((STONE, 1.0, box(f"wall_window_l{sx}{side}", (sx - 0.1, y, 1.12), (0.05, 0.03, 0.34), bevel=0.01)))
            parts.append((STONE, 1.0, box(f"wall_window_r{sx}{side}", (sx + 0.1, y, 1.12), (0.05, 0.03, 0.34), bevel=0.01)))
            parts.append((STONE, 1.0, box(f"wall_window_sill{sx}{side}", (sx, y, 0.76), (0.16, 0.05, 0.04), bevel=0.01)))
    run["base"] = build(*parts)
    return run


def gatehouse():
    """Over a gate with a tower each side: a stone chamber bridging the towers, corbelled out over the gate both ways,
    with a slit window and merlons. It rises into the cell above the gate (shown only while that cell is empty)."""
    rng = random.Random("gatehouse")
    x, hy = H + 0.12, W2 + 0.16
    z0, z1 = WALL_TOP + 0.08, 3.0
    def slit(xx, z):
        return abs(xx) < 0.12 and 2.25 < z < 2.75
    parts = [
        (STONE, MORTAR, box("gatehouse_body", (0, 0, (z0 + z1) / 2), (x, hy, (z1 - z0) / 2), bevel=0.02)),
        skin_plane("gatehouse_f", -x, x, z0, z1, -hy, -1, "ghf", skip=slit),
        skin_plane("gatehouse_b", -x, x, z0, z1, hy, 1, "ghb", skip=slit),
        moss_tops(tint(box("gatehouse_coping", (0, 0, z1 + 0.06), (x, hy + 0.04, 0.06), bevel=0.02), STONE, 0.95), rng, 0.25),
    ]
    for side in (-1, 1):
        y = side * (hy + 0.012)
        parts.append((WOOD, 0.8, box(f"gatehouse_slit{side}", (0, y, 2.5), (0.05, 0.02, 0.22), bevel=0.0)))
        for i in range(7):  # corbels under the overhang
            cxx = -0.9 + i * 0.3
            parts.append((STONE, 0.9, box(f"gatehouse_corbel{side}{i}", (cxx, side * (hy - 0.08), z0 - 0.08), (0.07, 0.1, 0.08), bevel=0.02)))
        for k in (-1, 0, 1):
            m = box(f"gatehouse_m{k}{side}", (k * CELL_THIRD, side * (hy - 0.12), z1 + 0.12 + MERLON[1] / 2), (MERLON[0] / 2, 0.11, MERLON[1] / 2), bevel=0.03)
            parts.append(moss_tops(tint(m, STONE, rng.uniform(0.88, 1.0)), rng, 0.3))
    return build(*parts)


def wall_gate():
    """A wall with an arched oak gate on both faces; between two towers it grows a gatehouse."""
    def skip(x, z):
        return abs(x) < 0.62 and z < 1.55
    run = wall_body("wall_gate", -H, H, skip_front=skip, skip_back=skip)
    front = arch_door("wall_gate_f", 0, -W2, 0.32, 0.86, 1.18, facing=-1)
    back = arch_door("wall_gate_b", 0, W2, 0.32, 0.86, 1.18, facing=1)
    run["base"] = joined(run["base"], front, back)
    run["gatehouse"] = gatehouse()
    return run


def wall_broken():
    """A ruined wall: a stepped, crumbled top, one surviving merlon, fallen blocks in front, moss."""
    rng = random.Random("wall_broken")
    tops = [1.35, 0.95, 0.6, 1.1]
    parts = [(STONE, 0.9, box("wall_broken_plinth", (0, 0, 0.16), (H, W2 + 0.07, 0.16), bevel=0.05))]
    for i, top in enumerate(tops):
        x0, x1 = -H + i * 0.5, -H + (i + 1) * 0.5
        cx = (x0 + x1) / 2
        parts.append((STONE, MORTAR, box(f"wall_broken_body{i}", (cx, 0, (0.32 + top) / 2), (0.25, W2, (top - 0.32) / 2), bevel=0.02)))
        parts.append(skin_plane(f"wall_broken_f{i}", x0, x1, 0.32, top, -W2, -1, f"f{i}", moss_low=0.4))
        parts.append(skin_plane(f"wall_broken_b{i}", x0, x1, 0.32, top, W2, 1, f"b{i}", moss_low=0.4))
        parts.append(moss_tops(tint(box(f"wall_broken_top{i}", (cx + rng.uniform(-0.05, 0.05), 0, top + 0.05),
                                        (0.22, W2 - 0.02, 0.06), bevel=0.03), STONE, 0.95), rng, 0.6))
    parts.append((STONE, 0.95, box("wall_broken_merlon", (-0.75, -(W2 - 0.12), 1.35 + 0.32), (0.21, 0.11, 0.2), bevel=0.03)))
    for i in range(5):
        b = box(f"wall_broken_fallen{i}", (0, 0, 0), (rng.uniform(0.09, 0.16), rng.uniform(0.08, 0.13), rng.uniform(0.06, 0.1)), bevel=0.02)
        turn(b, "z", rng.uniform(0, 90))
        parts.append((STONE, rng.uniform(0.86, 1.0), move(b, (rng.uniform(-0.8, 0.8), rng.uniform(-0.85, -0.5), 0.07))))
    return build(*parts)


# ---- towers

def tower_body(name, z0, z1, skip=None, plinth=False, band=True):
    parts = []
    if plinth:
        parts.append((STONE, 0.9, lathe(name + "_plinth", [(0, 0), (R + 0.07, 0), (R + 0.07, 0.16), (R, 0.32), (0, 0.32)], segments=16)))
    prof = [(0, z0), (R, z0), (R, z1 - (0.08 if band else 0))]
    if band:
        prof += [(R + 0.04, z1 - 0.08), (R + 0.04, z1)]
    prof += [(0, z1)]
    parts.append((STONE, MORTAR, lathe(name + "_body", prof, segments=16)))
    parts.append(skin_ring(name + "_skin", R, z0, z1 - (0.08 if band else 0), name, skip=skip, moss_low=0.45 if plinth else 0.0))
    return parts


def slits(name, angles, z):
    parts = []
    for i, a in enumerate(angles):
        s = box(f"{name}_slit{i}", (R + 0.015, 0, z), (0.02, 0.05, 0.22), bevel=0.0)
        parts.append((WOOD, 0.8, turn(s, "z", a)))
    return parts


def near_angle(x, y, z, angle, half_width, z0, z1):
    a = math.degrees(math.atan2(y, x))
    return abs((a - angle + 180) % 360 - 180) < half_width and z0 < z < z1


def shoulder(name):
    """Stone closing the gap between a round tower and a wall that ends at the cell's east edge: a block from inside
    the drum to the edge, as wide as the wall's plinth, skinned both sides and coped at the wall walk."""
    x0, x1, hy = R - 0.25, H, W2 + 0.04
    cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
    return build(
        (STONE, 0.9, box(name + "_plinth", (cx, 0, 0.16), (hx, hy + 0.04, 0.16), bevel=0.04)),
        (STONE, MORTAR, box(name + "_body", (cx, 0, (0.32 + WALL_TOP) / 2), (hx, hy, (WALL_TOP - 0.32) / 2), bevel=0.02)),
        skin_plane(name + "_f", x0, x1, 0.32, WALL_TOP, -hy, -1, name + "f", moss_low=0.4),
        skin_plane(name + "_b", x0, x1, 0.32, WALL_TOP, hy, 1, name + "b", moss_low=0.4),
        tint(box(name + "_coping", (cx, 0, WALL_TOP + 0.06), (hx, hy + 0.04, 0.06), bevel=0.02), STONE, 0.95),
    )


def tower_door(name):
    """A doorway porch on the north side of a tower storey, opening onto the walk of the wall below beside it: a stone
    block standing out of the drum with an arched oak door, its threshold at the storey's floor, a sloped cap."""
    y, hx, z0, z1 = R + 0.18, 0.38, -0.1, 1.62
    def door(x, z):
        return abs(x) < 0.31 and z < 1.12
    cap = prism(name + "_cap", [(-hx - 0.05, z1), (hx + 0.05, z1), (hx + 0.05, z1 + 0.06), (0, z1 + 0.2), (-hx - 0.05, z1 + 0.06)],
                -y - 0.06, -(R - 0.1), bevel=0.0)
    return build(
        (STONE, 0.9, box(name + "_porch", (0, -(R + 0.04), (z0 + z1) / 2), (hx, 0.14, (z1 - z0) / 2), bevel=0.02)),
        skin_plane(name + "_f", -hx, hx, z0, z1, -y, -1, name + "f", skip=door),
        arch_door(name + "_d", 0, -y, 0.0, 0.46, 1.05, facing=-1),
        (STONE, 0.95, cap),
    )


def tower_link(name, top, plinth):
    """Masonry joining a tower to another standing next to it on the east: a block from inside the drum to the cell's
    edge, wider than a wall, up to top (the storey's height); the neighbour adds the other half."""
    x0, x1, hy = R - 0.25, H, 0.5
    cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
    z0 = COURSE if plinth else 0.0
    parts = [
        (STONE, MORTAR, box(name + "_body", (cx, 0, (z0 + top) / 2), (hx, hy, (top - z0) / 2), bevel=0.0)),
        skin_plane(name + "_f", x0, x1, z0, top, -hy, -1, name + "f", moss_low=0.4 if plinth else 0.0),
        skin_plane(name + "_b", x0, x1, z0, top, hy, 1, name + "b", moss_low=0.4 if plinth else 0.0),
    ]
    if plinth:
        parts.append((STONE, 0.9, box(name + "_plinth", (cx, 0, COURSE / 2), (hx, hy + 0.07, COURSE / 2), bevel=0.04)))
    if top < G.LEVEL:  # the top storey: coped at its parapet
        parts.append(tint(box(name + "_coping", (cx, 0, top + 0.06), (hx, hy + 0.04, 0.06), bevel=0.02), STONE, 0.95))
    return build(*parts)


def tower_joins(name, doors, link_top=G.LEVEL, plinth=False):
    """A tower piece's join parts: a shoulder toward each side a wall meets it, a link toward each tower beside it
    and, on storeys, a door on each side whose wall walk or stair top is one level down."""
    parts = {f"shoulder_{f}": turn(shoulder(f"{name}_sh{f}"), "z", FROM_E[f]) for f in "nesw"}
    parts.update({f"link_{f}": turn(tower_link(f"{name}_ln{f}", link_top, plinth), "z", FROM_E[f]) for f in "nesw"})
    if doors:
        parts.update({f"door_{f}": turn(tower_door(f"{name}_door{f}"), "z", FROM_N[f]) for f in "nesw"})
    return parts


def tower_base():
    def skip(x, y, z):
        return near_angle(x, y, z, -90, 22, 0, 1.45) or any(near_angle(x, y, z, a, 9, 1.05, 1.65) for a in (0, 180, 90))
    parts = tower_body("tower_base", 0.32, 2.0, skip=skip, plinth=True)
    parts.append(arch_door("tower_base_d", 0, -(R - 0.02), 0.32, 0.5, 1.0, facing=-1))
    parts += slits("tower_base", (0, 180, 90), 1.35)
    return {"base": build(*parts), **tower_joins("tower_base", doors=False, plinth=True)}


def tower_mid():
    def skip(x, y, z):
        return any(near_angle(x, y, z, a, 16, 0.75, 1.55) for a in (-90, 90)) or any(near_angle(x, y, z, a, 9, 0.5, 1.1) for a in (0, 180))
    parts = tower_body("tower_mid", 0.0, 2.0, skip=skip)
    for side, a in ((-1, -90), (1, 90)):
        y = side * (R + 0.012)
        parts.append((WOOD, box(f"tower_mid_win{side}", (0, y, 1.05), (0.16, 0.02, 0.22), bevel=0.0)))
        parts.append((WOOD, cyl(f"tower_mid_wintop{side}", (0, y, 1.27), 0.16, 0.04, axis="y", segments=8)))
        parts.append((STONE, 1.0, box(f"tower_mid_sill{side}", (0, y + side * 0.02, 0.8), (0.22, 0.05, 0.04), bevel=0.01)))
    parts += slits("tower_mid", (0, 180), 0.8)
    return {"base": build(*parts), **tower_joins("tower_mid", doors=True)}


def ring_of(name, n, r, z, half, rng, heights=None):
    """n blocks of half size (along the ring, out, up) standing round a circle of radius r with their bases at z."""
    out = []
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        h = heights[i] if heights else half[2]
        b = turn(box(f"{name}{i}", (0, 0, h), (half[0], half[1], h), bevel=0.03), "z", math.degrees(a) + 90)
        out.append(moss_tops(tint(move(b, (r * math.cos(a), r * math.sin(a), z)), STONE, rng.uniform(0.88, 1.0)), rng, 0.35))
    return out


def tower_top():
    """The crenellated top of a tower: a corbelled parapet round an oak floor."""
    rng = random.Random("tower_top")
    parts = tower_body("tower_top", 0.0, 0.7, band=False)
    parapet = lathe("tower_top_parapet", [(R, 0.7), (R + 0.1, 0.92), (R + 0.1, 1.5), (R - 0.12, 1.5), (R - 0.12, 1.06), (0, 1.06), (0, 0.7)], segments=16)
    tint(parapet, STONE, 0.95)
    tint(parapet, WOOD, 0.9, lambda c, n: n.z > 0.9 and c.z < 1.1)  # the floor
    parts.append(parapet)
    parts += ring_of("tower_top_m", 8, R - 0.01, 1.5, (0.19, 0.1, MERLON[1] / 2), rng)
    return {"base": build(*parts), **tower_joins("tower_top", doors=True, link_top=1.5)}


def tower_broken():
    """A ruined tower top: a low ring with a jagged rim of broken stones, a mossy floor, fallen blocks."""
    rng = random.Random("tower_broken")
    parts = tower_body("tower_broken", 0.0, 0.9, band=False)
    rim = lathe("tower_broken_rim", [(R - 0.14, 0.9), (R - 0.14, 0.75), (0, 0.75), (0, 0.9)], segments=16)
    parts.append(tint(rim, MOSS))
    heights = [rng.choice((0.08, 0.14, 0.22, 0.3, 0.4)) for _ in range(10)]  # half-heights of the broken rim
    parts += ring_of("tower_broken_r", 10, R - 0.07, 0.9, (0.24, 0.1, 0.1), rng, heights)
    for i in range(3):
        b = box(f"tower_broken_fallen{i}", (0, 0, 0), (0.1, 0.08, 0.07), bevel=0.02)
        turn(b, "z", rng.uniform(0, 90))
        parts.append((STONE, 0.9, move(b, (rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0.82))))
    return build(*parts)


def tower_roof():
    """A tiered cone roof (three courses of tiles, each with a lip), a finial pole and a pennant.
    Areas: roof A, timber B, cloth C."""
    cone = lathe("tower_roof", [(0, 0), (R + 0.16, 0), (R + 0.16, 0.1), (0.72, 0.7), (0.8, 0.7), (0.44, 1.28), (0.52, 1.28), (0, 1.95)], segments=16)
    tint(cone, A)
    tint(cone, A, 0.88, lambda c, n: n.z < -0.2)  # undersides of the lips a shade darker
    pole = cyl("tower_roof_pole", (0, 0, 2.1), 0.035, 0.4, segments=6)
    flag = prism("tower_roof_flag", [(0.03, 2.28), (0.42, 2.2), (0.03, 2.1)], -0.015, 0.015, bevel=0.0)
    return build(cone, (B, pole), (C, flag))


# ---- buildings

def gable_roof(name, half_len, half_w, z0, z1, steps=3):
    """A tiled gable roof, ridge along X: a profile with a lip at every tile course, pushed along X."""
    def slope(t):
        return half_w * (1 - t), z0 + (z1 - z0) * t

    lip = (0.06, -0.035)  # each course's lower edge stands out and down over the one below
    right = [(half_w, z0)]
    for k in range(1, steps):
        x, z = slope(k / steps)
        right += [(x + lip[0], z + lip[1]), (x, z)]
    # the left side mirrors the right, walking down from the ridge: the slope point first, then its lip
    left = []
    for k in range(steps - 1, 0, -1):
        x, z = slope(k / steps)
        left += [(-x, z), (-x - lip[0], z + lip[1])]
    underside = [(-half_w, z0), (-half_w + 0.1, z0 - 0.05), (0, z1 - 0.2), (half_w - 0.1, z0 - 0.05)]
    outline = right + [(0, z1)] + left + underside
    return turn(prism(name, outline, -half_len, half_len, bevel=0.0), "z", 90)


HX, HY = 0.92, 0.66  # a house's walls: the gables at x = +-HX (e, w), the eaves at y = +-HY


def house_frame(name, z0, z1):
    """One storey of timber frame on plaster from z0 to z1: corner posts, rails, studs and braces on the long
    sides, rails and a window on each gable side."""
    zm, hz = (z0 + z1) / 2, (z1 - z0) / 2
    parts = [(A, box(name + "_walls", (0, 0, zm), (HX, HY, hz), bevel=0.01))]
    for dx in (-1, 1):
        for dy in (-1, 1):
            parts.append((C, box(f"{name}_post{dx}{dy}", (dx * HX, dy * HY, zm), (0.06, 0.06, hz + 0.02), bevel=0.01)))
    for dy in (-1, 1):
        for z in (z0 + 0.03, z1 - 0.03):
            parts.append((C, box(f"{name}_beam{dy}{z:.2f}", (0, dy * (HY + 0.01), z), (HX + 0.04, 0.05, 0.05), bevel=0.01)))
        for dx in (-0.34, 0.34):
            parts.append((C, box(f"{name}_mid{dy}{dx}", (dx, dy * (HY + 0.01), zm), (0.045, 0.045, hz - 0.02), bevel=0.0)))
        for dx, a in ((-0.66, 35), (0.66, -35)):
            brace = box(f"{name}_brace{dy}{dx}", (0, 0, 0), (0.035, 0.04, min(0.32, hz * 0.55)), bevel=0.0)
            parts.append((C, move(turn(brace, "y", a), (dx, dy * (HY + 0.015), zm))))
    for dx in (-1, 1):
        for z in (z0 + 0.03, z1 - 0.03):
            parts.append((C, box(f"{name}_side{dx}{z:.2f}", (dx * (HX + 0.01), 0, z), (0.05, HY + 0.04, 0.05), bevel=0.01)))
        parts.append((C, box(f"{name}_win{dx}", (dx * (HX + 0.015), 0, zm + 0.08), (0.02, 0.2, min(0.18, hz * 0.4)), bevel=0.0)))
    return build(*parts)


def house():
    """A timber-framed cottage: cream plaster, oak frame and door, an orange tiled gable roof (ridge along X, gables
    east and west). Its parts make houses join: a stone footing on the ground or a timber jetty on a storey below, the
    roof or (with a storey on top) the walls carried up to the next level, and between houses gable to gable, an
    infill that closes the gap so their roofs (which run to the cell's edge) read as one long house.
    Areas: plaster A, roof B, timber C, stone D."""
    gable = turn(prism("house_gable", [(-HY, 1.52), (HY, 1.52), (0, 2.1)], -HX, HX, bevel=0.0), "z", 90)
    roof = build((A, gable), (B, gable_roof("house_roof", H, 0.9, 1.45, 2.38)))

    def link(side, tall):
        """Plaster from the gable wall out to the cell's edge on one side: up to the roof, or to the next level."""
        name = f"house_link{'_tall' if tall else ''}_{side}"
        top = [(HY, G.LEVEL), (-HY, G.LEVEL)] if tall else [(HY, 1.5), (0, 2.08), (-HY, 1.5)]
        ob = prism(name, [(-HY, 0.3)] + [(HY, 0.3)] + top, HX - 0.02, H, bevel=0.0)  # pushed out along +Y ...
        turn(ob, "z", -90)  # ... then turned so +Y points east
        if side == "w":
            turn(ob, "z", 180)
        return tint(ob, A)

    look = {
        "base": house_frame("house", 0.3, 1.5),
        "footing": build(  # the ground floor: stone footing, front door and step
            (D, box("house_footing", (0, 0, 0.15), (H - 0.02, HY + 0.08, 0.15), bevel=0.03)),
            (C, box("house_door", (0, -(HY + 0.03), 0.62), (0.2, 0.03, 0.3), bevel=0.01)),
            (D, box("house_step", (0, -(HY + 0.2), 0.04), (0.26, 0.1, 0.04), bevel=0.01))),
        "jetty": build((C, 0.85, box("house_jetty", (0, 0, 0.15), (H - 0.02, HY + 0.06, 0.15), bevel=0.02))),
        "roof": roof,
        "upper": house_frame("house_upper", 1.5, G.LEVEL),
    }
    for side, sx in (("e", 1), ("w", -1)):
        look[f"link_{side}"] = link(side, False)
        look[f"link_tall_{side}"] = link(side, True)
        # where a stair or a bridge reaches a gable: a loft hatch under the roof at the walk's height, or the upper
        # storey's door just over it
        look[f"loft_{side}"] = build(
            (C, 0.85, box(f"house_loft{side}", (sx * (HX + 0.02), 0, 1.93), (0.025, 0.13, 0.11), bevel=0.01)),
            (C, box(f"house_loftsill{side}", (sx * (HX + 0.03), 0, 1.81), (0.035, 0.17, 0.02), bevel=0.0)))
        look[f"updoor_{side}"] = build(
            (C, 0.85, box(f"house_updoor{side}", (sx * (H - 0.04), 0, 0.44), (0.04, 0.2, 0.42), bevel=0.01)),
            (C, box(f"house_uplintel{side}", (sx * (H - 0.035), 0, 0.88), (0.035, 0.26, 0.035), bevel=0.0)))
    return look


def keep():
    """A 2x2-cell stone keep, two levels tall: block-skinned walls, corner pilasters, an arched gate, windows,
    and a tiered hip roof. Footprint: Blender x -1..3, y -3..1 (catalog cells x 0..1, z 0..1). Areas: stone A,
    roof B, timber C, iron D."""
    cx, cy, h = 1.0, -1.0, 1.75
    top = 2.3  # leaves room under the two-level cap for a steep roof
    full = 2 * G.LEVEL  # where a keep standing on this one begins

    def skins(name, z0, z1, sides, skip_front=None):
        out = []
        if "n" in sides:
            out.append(skin_plane(name + "_n", cx - h, cx + h, z0, z1, cy - h, -1, name + "n", skip=skip_front))
        if "s" in sides:
            out.append(skin_plane(name + "_s", cx - h, cx + h, z0, z1, cy + h, 1, name + "s"))
        # side skins: built facing -Y at distance h, then turned to face +X (east) or -X (west) and moved over the keep
        if "e" in sides:
            out.append(move(turn(skin_plane(name + "_e", cy - h, cy + h, z0, z1, -h, -1, name + "e"), "z", 90), (cx, 0, 0)))
        if "w" in sides:
            out.append(move(turn(skin_plane(name + "_w", -(cy + h), -(cy - h), z0, z1, -h, -1, name + "w"), "z", -90), (cx, 0, 0)))
        return out

    def body(name, z0, z1, sides="nesw"):
        out = [(A, MORTAR, box(name + "_body", (cx, cy, (z0 + z1) / 2), (h, h, (z1 - z0) / 2), bevel=0.02))]
        out += skins(name, z0, z1, sides)
        for dx in (-1, 1):
            for dy in (-1, 1):
                out.append((A, 1.0, box(f"{name}_pilaster{dx}{dy}", (cx + dx * h, cy + dy * h, (z0 + z1) / 2), (0.16, 0.16, (z1 - z0) / 2 + 0.02), bevel=0.03)))
        return out

    def windows(name, zs, sides):
        out = []
        for z in zs:
            if "e" in sides: out.append((C, box(f"{name}_e{z}", (cx + h + 0.02, cy, z), (0.02, 0.16, 0.24), bevel=0.0)))
            if "w" in sides: out.append((C, box(f"{name}_w{z}", (cx - h - 0.02, cy, z), (0.02, 0.16, 0.24), bevel=0.0)))
            if "s" in sides: out.append((C, box(f"{name}_s{z}", (cx, cy + h + 0.02, z), (0.16, 0.02, 0.24), bevel=0.0)))
            if "n" in sides: out.append((C, box(f"{name}_n{z}", (cx, cy - h - 0.02, z), (0.16, 0.02, 0.24), bevel=0.0)))
        return out

    def door_skip(x, z):
        return abs(x - cx) < 0.62 and z < 1.75

    base = body("keep", 0.32, top, sides="esw")
    base.append((A, 0.95, box("keep_cornice", (cx, cy, top + 0.06), (h + 0.12, h + 0.12, 0.08), bevel=0.02)))
    base += windows("keep_win", (0.95, 1.8), "esw")
    # a 4-segment lathe is a square pyramid turned 45 degrees; radius 2.75 gives a 1.95 m half-width (a small eave)
    # rising into the 0.45 m the grid lets trim lean over the cell above, so the tiers stay steep (40-46 degrees)
    roof = lathe("keep_roof", [(0, top + 0.12), (2.75, top + 0.12), (2.75, top + 0.22), (1.9, top + 0.85), (2.02, top + 0.85),
                               (1.0, top + 1.5), (1.1, top + 1.5), (0, top + 2.08)], segments=4)
    roof = move(turn(roof, "z", 45), (cx, cy, 0))
    upper = body("keep_up", top + 0.14, full)
    upper += windows("keep_upwin", (3.1,), "nesw")

    def door(name):
        """A doorway built out of the wall where a stair's top or a bridge's deck arrives: a stone porch, an arched oak
        door, and a small gabled cap that rises through the roof's eaves like a dormer. Built facing -Y at y = 0."""
        hx, d, z0, z1 = 0.4, 0.3, DECK - 0.06, DECK + 0.8
        def skip(x, z):
            return abs(x) < 0.31 and z < z0 + 0.8
        cap = prism(name + "_cap", [(-hx - 0.06, z1), (hx + 0.06, z1), (0, z1 + 0.3)], -d - 0.06, 0.1, bevel=0.0)
        return build(
            (A, 0.92, box(name + "_porch", (0, (0.1 - d) / 2, (z0 + z1) / 2), (hx, (0.1 + d) / 2, (z1 - z0) / 2), bevel=0.02)),
            skin_plane(name + "_f", -hx, hx, z0, z1, -d, -1, name + "f", skip=skip),
            arch_door(name + "_d", 0, -d, z0 + 0.02, 0.44, 0.72, facing=-1),
            (B, cap),
        )

    # one per outer wall of each ground-floor cell: (cell, face, where on the wall, the turn from facing -Y)
    keep_doors = {}
    for i, f, at, deg in ((0, "w", (cx - h, 0), -90), (0, "s", (0, cy + h), 180), (1, "e", (cx + h, 0), 90), (1, "s", (2, cy + h), 180),
                          (2, "w", (cx - h, -2), -90), (2, "n", (0, cy - h), 0), (3, "e", (cx + h, -2), 90), (3, "n", (2, cy - h), 0)):
        keep_doors[f"door_{i}{f}"] = move(turn(door(f"keep_door{i}{f}"), "z", deg), (at[0], at[1], 0))
    return {
        **keep_doors,
        "base": build(*base),
        # on the ground: plinth and the gate; on a keep: the walls carried down to the floor and a windowed front
        "plinth": build((A, 0.9, box("keep_plinth", (cx, cy, 0.16), (h + 0.08, h + 0.08, 0.16), bevel=0.05))),
        "entrance": build(*skins("keep_f", 0.32, top, "n", skip_front=door_skip), arch_door("keep_d", cx, cy - h, 0.32, 0.9, 1.4, facing=-1)),
        "sill": build(*body("keep_sill", 0.0, 0.32)),
        "front": build(*skins("keep_f", 0.32, top, "n"), *windows("keep_fwin", (0.95, 1.8), "n")),
        # on top: the roof, or the walls carried up to the keep standing on this one
        "roof": tint(roof, B),
        "upper": build(*upper),
    }


def stairs():
    """Six stone steps only as wide as a wall, rising toward the back (s) to the wall walk: a mortar core faced with
    blocks on both sides and on each riser, a pale tread on every step. Against a wall's flank, part "landing" carries
    the top step on a block of masonry to the wall's face (in the next cell), so the stair reads as built onto it."""
    rng = random.Random("stairs")
    hw, step, n, gap = W2 - 0.02, 0.3, 6, 0.02
    front = H - n * step  # the first step's front; the top step ends at the cell's back edge, at the walk's height

    def sides(name, y0, y1, rows, quads, looks):
        """Block faces on both sides of a column from y0 to y1, one block per step-high course."""
        for r in range(rows):
            lo, hi = r * step + gap / 2, (r + 1) * step - gap / 2
            for side in (-1, 1):
                x = side * (hw + 0.012)
                q = [(x, y0 + gap / 2, lo), (x, y1 - gap / 2, lo), (x, y1 - gap / 2, hi), (x, y0 + gap / 2, hi)]
                quads.append(q if side > 0 else q[::-1])
                looks.append((MOSS, 1.0) if r == 0 and rng.random() < 0.4 else (STONE, rng.uniform(0.86, 1.0)))

    parts, quads, looks = [], [], []
    for i in range(n):
        y0, top = front + i * step, (i + 1) * step
        parts.append((STONE, MORTAR, box(f"stairs_{i}", (0, (y0 + H) / 2, top / 2), (hw, (H - y0) / 2, top / 2), bevel=0.0)))
        tread = box(f"stairs_tread{i}", (0, y0 + step / 2, top + 0.015), (hw + 0.015, step / 2 + 0.01, 0.015), bevel=0.01)
        parts.append(moss_tops(tint(tread, STONE, rng.uniform(0.92, 1.0)), rng, 0.25))
        sides("stairs", y0, y0 + step, i + 1, quads, looks)
        yy, lo, hi = y0 - 0.012, i * step + gap / 2, top - gap / 2
        for a, b in ((-hw, 0), (0, hw)):  # the riser, two blocks across
            quads.append([(a + gap / 2, yy, lo), (b - gap / 2, yy, lo), (b - gap / 2, yy, hi), (a + gap / 2, yy, hi)])
            looks.append((STONE, rng.uniform(0.86, 1.0)))
    parts.append(_skin_object("stairs_skin", quads, looks))

    def landing(name, reach):
        """Masonry carrying the top step from the cell's back edge to the face of what the stair leans on."""
        lq, ll = [], []
        sides(name, H, reach, n, lq, ll)
        return build(
            (STONE, MORTAR, box(name, (0, (H + reach) / 2, n * step / 2), (hw, (reach - H) / 2, n * step / 2), bevel=0.0)),
            moss_tops(tint(box(name + "_tread", (0, (H + reach) / 2, n * step + 0.015), (hw + 0.015, (reach - H) / 2, 0.015), bevel=0.01), STONE, 0.95), rng, 0.25),
            _skin_object(name + "_skin", lq, ll),
        )

    return {
        "base": build(*parts),
        "landing_wall": landing("stairs_landwall", H + (H - W2) + 0.02),  # a wall's flank, mid-cell beyond
        "landing_near": landing("stairs_landnear", H + 0.16),  # a tower's drum or a house's gable, just over the edge
        "landing_keep": landing("stairs_landkeep", H + 0.27),  # a keep's wall, a quarter metre in
    }


DECK = WALL_TOP + 0.1  # a bridge's deck: level with a wall walk's coping, a step under a tower storey's door


def bridge():
    """One cell of timber walkway at wall-walk height, spanning east-west: planks on two stringers, posts at both ends,
    a rail and a rope each side. Segments join end to end into a bridge of any length; where an end meets a tower,
    wall, keep or house instead, a reach part carries the deck to its face on a stone corbel.
    Areas: timber A, moss B, stone C, iron D (rope)."""
    rng = random.Random("bridge")
    parts = []
    for i in range(4):
        parts.append((A, rng.uniform(0.82, 1.0), box(f"bridge_plank{i}", (-H + 0.25 + i * 0.5, 0, DECK - 0.04), (0.24, 0.56, 0.04), bevel=0.0)))
    for side in (-1, 1):
        parts.append((A, 0.72, box(f"bridge_stringer{side}", (0, side * 0.38, DECK - 0.16), (H, 0.06, 0.08), bevel=0.0)))
        for x in (-H + 0.07, H - 0.07):
            parts.append((A, 0.85, box(f"bridge_post{side}{x:.2f}", (x, side * 0.52, DECK + 0.42), (0.05, 0.05, 0.46), bevel=0.01)))
        parts.append((A, 0.92, box(f"bridge_rail{side}", (0, side * 0.52, DECK + 0.84), (H, 0.035, 0.03), bevel=0.0)))
        parts.append((D, box(f"bridge_rope{side}", (0, side * 0.52, DECK + 0.45), (H, 0.012, 0.012), bevel=0.0)))

    def reach(name, dist):
        """The deck carried from the cell's east edge to a face dist beyond it, on a stepped stone corbel."""
        x0, x1 = H - 0.01, H + dist
        cx, hx = (x0 + x1) / 2, (x1 - x0) / 2
        out = [(A, 0.9, box(name + "_deck", (cx, 0, DECK - 0.04), (hx, 0.56, 0.04), bevel=0.0))]
        for side in (-1, 1):
            out.append((A, 0.72, box(f"{name}_str{side}", (cx, side * 0.38, DECK - 0.16), (hx, 0.06, 0.08), bevel=0.0)))
        out.append((C, 0.92, box(name + "_corbel", (x1 - 0.1, 0, DECK - 0.33), (0.16, 0.46, 0.09), bevel=0.02)))
        out.append((C, 0.86, box(name + "_corbel2", (x1 - 0.05, 0, DECK - 0.5), (0.1, 0.36, 0.08), bevel=0.02)))
        return build(*out)

    look = {"base": build(*parts)}
    for f, deg in (("e", 0), ("w", 180)):
        look[f"reach_{f}_wall"] = turn(reach(f"bridge_rw{f}", H - W2 + 0.02), "z", deg)  # a wall's flank, mid-cell beyond
        look[f"reach_{f}_near"] = turn(reach(f"bridge_rn{f}", 0.16), "z", deg)  # a tower's drum or a house's gable
        look[f"reach_{f}_keep"] = turn(reach(f"bridge_rk{f}", 0.27), "z", deg)  # a keep's wall
    return look


# ---- ground

def tile(name):
    return box(name, (0, 0, G.TILE_TOP - 0.09), (H, H, 0.09), bevel=0.0)


def ground_grass():
    """A grass tile with tufts and a few flowers. Areas: grass A, path B, moss C, cloth D (flowers)."""
    rng = random.Random("ground_grass")
    parts = [(A, tile("ground_grass"))]
    for i in range(7):
        x, y = rng.uniform(-0.85, 0.85), rng.uniform(-0.85, 0.85)
        parts.append((C, cyl(f"ground_grass_tuft{i}", (x, y, G.TILE_TOP + 0.06), 0.09, 0.12, segments=5, r2=0.0)))
    for i in range(3):
        x, y = rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8)
        parts.append((D, box(f"ground_grass_flower{i}", (x, y, G.TILE_TOP + 0.03), (0.03, 0.03, 0.03), bevel=0.0)))
    return build(*parts)


def path_edge(name):
    """Grass creeping over a path tile's south edge (Blender +Y): an uneven strip of turf and a few tufts."""
    rng = random.Random(name)
    parts, x = [], -H
    while x < H - 0.01:
        w = min(rng.uniform(0.25, 0.45), H - x)
        d = rng.uniform(0.1, 0.22)
        parts.append((B, rng.uniform(0.9, 1.0), box(f"{name}_turf{x:.2f}", (x + w / 2, H - d / 2, G.TILE_TOP + 0.012), (w / 2, d / 2, 0.012), bevel=0.0)))
        x += w
    for i in range(3):
        parts.append((B, cyl(f"{name}_tuft{i}", (rng.uniform(-0.85, 0.85), H - rng.uniform(0.05, 0.15), G.TILE_TOP + 0.06), 0.08, 0.1, segments=5, r2=0.0)))
    return build(*parts)


def ground_path():
    """A cobbled tile: a 4x4 grid of cobble faces just above a darker bed. Each side that doesn't meet another path
    gets a grassy edge (parts edge_n..edge_w), so paths blend into the grass and runs read as one road.
    Areas: path A, grass B, moss C, stone D."""
    rng = random.Random("ground_path")
    parts = [(A, 0.72, tile("ground_path"))]
    quads, looks = [], []
    z = G.TILE_TOP + 0.008
    for i in range(4):
        for j in range(4):
            x0, y0 = -H + i * 0.5 + 0.025, -H + j * 0.5 + 0.025
            jx = rng.uniform(-0.02, 0.02)
            quads.append([(x0 + jx, y0, z), (x0 + 0.45 + jx, y0, z), (x0 + 0.45 + jx, y0 + 0.45, z), (x0 + jx, y0 + 0.45, z)])
            looks.append((A, rng.uniform(0.88, 1.0)))
    parts.append(_skin_object("ground_path_cobbles", quads, looks))
    # built on the south side (Blender +Y); n is Blender -Y
    edges = {f: turn(path_edge(f"ground_path_edge{f}"), "z", {"s": 0, "n": 180, "e": -90, "w": 90}[f]) for f in "nesw"}
    return {"base": build(*parts), **{f"edge_{f}": ob for f, ob in edges.items()}}


# ---- props

def well():
    """A round stone well with an oak frame, a small tiled roof and a bucket. Areas: stone A, roof B, timber C, iron D."""
    ring = lathe("well", [(0.3, 0.02), (0.52, 0.02), (0.52, 0.62), (0.56, 0.62), (0.56, 0.7), (0.32, 0.7), (0.32, 0.25), (0, 0.25)], segments=12)
    parts = [(A, 0.9, ring), skin_ring("well_skin", 0.52, 0.02, 0.62, "well", segments=12, course=0.2), (D, 0.0, box("well_water", (0, 0, 0.3), (0.28, 0.28, 0.02), bevel=0.0))]
    for side in (-1, 1):
        parts.append((C, box(f"well_post{side}", (side * 0.46, 0, 0.95), (0.045, 0.045, 0.6), bevel=0.01)))
    parts.append((C, box("well_axle", (0, 0, 1.25), (0.5, 0.03, 0.03), bevel=0.0)))
    parts.append((D, box("well_bucket", (0, 0, 0.95), (0.08, 0.08, 0.09), bevel=0.01)))
    parts.append((B, gable_roof("well_roof", 0.62, 0.48, 1.45, 1.85, steps=2)))
    return build(*parts)


def rubble():
    """A pile of fallen blocks with moss."""
    rng = random.Random("rubble")
    parts = []
    for i in range(9):
        b = box(f"rubble_{i}", (0, 0, 0), (rng.uniform(0.18, 0.3), rng.uniform(0.14, 0.24), rng.uniform(0.11, 0.18)), bevel=0.03)
        turn(b, "z", rng.uniform(0, 90))
        turn(b, "x", rng.uniform(-12, 12))
        z = 0.14 if i < 6 else 0.38
        spread = 0.6 if i < 6 else 0.3
        parts.append(moss_tops(tint(move(b, (rng.uniform(-spread, spread), rng.uniform(-spread, spread), z)), STONE, rng.uniform(0.84, 1.0)), rng, 0.45))
    return build(*parts)


def banner():
    """A tall flagpole on a stone foot with a long banner. Areas: timber A, cloth B, stone C, iron D."""
    parts = [
        (C, box("banner_foot", (0, 0, 0.12), (0.22, 0.22, 0.12), bevel=0.03)),
        (A, cyl("banner_pole", (0, 0, 1.2), 0.045, 2.1, segments=8)),
        (A, box("banner_bar", (0.25, 0, 2.05), (0.3, 0.025, 0.025), bevel=0.0)),
        (D, cyl("banner_knob", (0, 0, 2.28), 0.06, 0.08, segments=8)),
    ]
    cloth = prism("banner_cloth", [(0.02, 2.0), (0.5, 2.0), (0.5, 1.05), (0.26, 1.22), (0.02, 1.05)], -0.012, 0.012, bevel=0.0)
    parts.append((B, cloth))
    return build(*parts)


def tree():
    """A tree of one of four species, picked per cell (parts oak, pine, poplar, apple, each "~k/4"), so a wood of
    them varies and a tree set down by hand comes up as any of them. The base is the moss at its foot.
    Areas: leaves A, moss B, timber C, cloth D (apples)."""
    rng = random.Random("tree")
    base = build(*[(B, rng.uniform(0.85, 1.0), cyl(f"tree_moss{i}", (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 0.03),
                                                    rng.uniform(0.12, 0.2), 0.06, segments=6)) for i in range(3)])
    oak = [(C, cyl("tree_oak_trunk", (0, 0, 0.5), 0.13, 1.0, segments=7, r2=0.08))]
    for i, (x, y, z, r) in enumerate(((0, 0, 1.35, 0.6), (0.28, -0.12, 1.05, 0.42), (-0.22, 0.16, 1.85, 0.42))):
        oak.append((A, 1.0 - 0.06 * i, ball(f"tree_oak_leaves{i}", (x, y, z), (r, r, r * 0.9), cuts=1)))
    pine = [(C, cyl("tree_pine_trunk", (0, 0, 0.35), 0.1, 0.7, segments=6, r2=0.07))]
    for i, (z, r, h) in enumerate(((0.75, 0.62, 0.8), (1.3, 0.48, 0.72), (1.8, 0.32, 0.62))):
        pine.append((A, 0.78 + 0.05 * i, cyl(f"tree_pine_tier{i}", (0, 0, z), r, h, segments=8, r2=0.0)))
    poplar = [(C, cyl("tree_poplar_trunk", (0, 0, 0.3), 0.09, 0.6, segments=6, r2=0.06)),
              (A, 0.92, ball("tree_poplar_crown", (0, 0, 1.35), (0.32, 0.32, 0.98), cuts=1))]
    apple = [(C, cyl("tree_apple_trunk", (0, 0, 0.4), 0.12, 0.8, segments=7, r2=0.09)),
             (A, 1.0, ball("tree_apple_crown", (0, 0, 1.12), (0.72, 0.72, 0.5), cuts=1))]
    for i in range(8):
        a, e = rng.uniform(0, 2 * math.pi), rng.uniform(-0.3, 0.6)
        at = (0.7 * math.cos(a) * math.cos(e), 0.7 * math.sin(a) * math.cos(e), 1.12 + 0.49 * math.sin(e))
        apple.append((D, box(f"tree_apple{i}", at, (0.055, 0.055, 0.055), bevel=0.02)))
    return {"base": base, "oak": build(*oak), "pine": build(*pine), "poplar": build(*poplar), "apple": build(*apple)}


# ---- the catalog

STONE_ROLES = ["stone", "moss", "timber", "iron"]
SIDES = {"n": "wall_side", "s": "wall_side"}
WALL_FACES = {"d": "wall_base", "u": "wall_top", "e": "wall_edge", "w": "wall_edge", **SIDES}
TOWER_SIDES = {f: "tower_side" for f in "nesw"}
ONE = [[0, 0, 0]]

# a wall on a wall reads as one: the lower keeps no coping or merlons and carries its body up, the upper no plinth
WALL_PARTS = {"plinth": ["d:!wall_top"], "sole": ["d:wall_top"], "cap": ["u:!wall_base"], "crown": ["u:empty"], "fill": ["u:wall_base"]}
# a tower meets a wall's end with a shoulder and a tower beside it with a link; a storey over a wall's walk or a
# stair's top gets a door onto it
SHOULDERS = {f"shoulder_{f}": [f"{f}:wall_edge"] for f in "nesw"}
LINKS = {f"link_{f}": [f"{f}:tower_side|parapet_side"] for f in "nesw"}
DOORS = {f"door_{f}": [f"{f}:empty", f"{f}-:wall_edge|stairs_top|bridge_link"] for f in "nesw"}
# a stair's landing reaches what it leans on
STAIRS_PARTS = {"landing_wall": ["s:wall_side"], "landing_near": ["s:tower_side|house_gable"], "landing_keep": ["s:keep_side"]}
HOUSE_PARTS = {
    "footing": ["d:!house_top"], "jetty": ["d:house_top"],
    "roof": ["u:!house_base"], "upper": ["u:house_base"],
    **{f"link_{f}": [f"{f}:house_gable", "u:!house_base"] for f in "ew"},
    **{f"link_tall_{f}": [f"{f}:house_gable", "u:house_base"] for f in "ew"},
    **{f"loft_{f}": [f"{f}:stairs_top|bridge_link", "u:!house_base"] for f in "ew"},
    **{f"updoor_{f}": ["d:house_top", f"{f}-:stairs_top|bridge_link"] for f in "ew"},
}
KEEP_TOP = 4  # the keep's cell [0, 1, 0]: its top level
KEEP_PARTS = {
    "plinth": ["d:!keep_top"], "entrance": ["d:!keep_top"], "sill": ["d:keep_top"], "front": ["d:keep_top"],
    "roof": {"cell": KEEP_TOP, "when": ["u:!keep_base"]}, "upper": {"cell": KEEP_TOP, "when": ["u:keep_base"]},
    # a doorway where a stair or a bridge arrives at a ground-floor wall
    **{f"door_{i}{f}": {"cell": i, "when": [f"{f}:stairs_top|bridge_link"]} for i, f in ((0, "w"), (0, "s"), (1, "e"), (1, "s"), (2, "w"), (2, "n"), (3, "e"), (3, "n"))},
}


def piece(id, name, category, build, faces, sym, gen_w, gen_y, tags, roles=STONE_ROLES, cells=ONE, layer="main", flat=False, parts=None):
    """flat: shade every face flat (big planar pieces whose shallow edges kit.shade would smooth into a dome)."""
    parts = {k: v if isinstance(v, dict) else {"when": v} for k, v in (parts or {}).items()}
    return dict(id=id, name=name, category=category, roles=roles, cells=cells, faces=faces, sym=sym, layer=layer,
                gen={"w": gen_w, "y": gen_y, "tags": tags}, build=build, flat=flat, parts=parts)


PIECES = [
    piece("wall_straight", "Wall", "walls", wall_straight, [WALL_FACES], 2, 3.0, [0, 1], ["wall"], parts=WALL_PARTS),
    piece("wall_corner", "Wall corner", "walls", wall_corner, [{"d": "wall_base", "u": "wall_top", "e": "wall_edge", "n": "wall_edge", "s": "wall_side", "w": "wall_side"}],
          4, 1.0, [0, 1], ["wall"], parts=WALL_PARTS),
    piece("wall_t", "Wall junction", "walls", wall_t, [{**WALL_FACES, "n": "wall_edge"}], 4, 0.3, [0, 1], ["wall"], parts=WALL_PARTS),
    piece("wall_end", "Wall end", "walls", wall_end, [{"d": "wall_base", "u": "wall_top", "w": "wall_edge", "n": "turret_side", "e": "turret_side", "s": "turret_side"}],
          4, 0.6, [0, 1], ["wall"], parts=WALL_PARTS),
    piece("wall_window", "Wall with windows", "walls", wall_window, [WALL_FACES], 2, 1.0, [0, 1], ["wall"], parts=WALL_PARTS),
    piece("wall_gate", "Gate", "walls", wall_gate, [{**WALL_FACES, "n": "gate_face", "s": "gate_face"}], 2, 0.4, [0, 0], ["wall"],
          parts={**WALL_PARTS, "gatehouse": ["e:tower_side", "w:tower_side", "u:empty"]}),
    piece("wall_broken", "Ruined wall", "walls", wall_broken, [{"d": "wall_base", "e": "wall_edge", "w": "wall_edge", "n": "ruin_side", "s": "ruin_side"}], 4, 1.5, [0, 1], ["wall", "ruin"]),
    piece("tower_base", "Tower", "towers", tower_base, [{"d": "tower_base", "u": "tower_ring", **TOWER_SIDES}], 4, 0.8, [0, 0], ["tower"], parts={**SHOULDERS, **LINKS}),
    piece("tower_mid", "Tower storey", "towers", tower_mid, [{"d": "tower_base", "u": "tower_ring", **TOWER_SIDES}], 2, 0.8, [1, 3], ["tower"],
          parts={**SHOULDERS, **LINKS, **DOORS}),
    piece("tower_top", "Tower top", "towers", tower_top, [{"d": "tower_base", "u": "roof_seat", **{f: "parapet_side" for f in "nesw"}}], 1, 0.8, [1, 4], ["tower"],
          parts={**SHOULDERS, **LINKS, **DOORS}),
    piece("tower_roof", "Cone roof", "towers", tower_roof, [{"d": "roof"}], 4, 1.0, [1, 5], ["roof"], roles=["roof", "timber", "cloth", "roof"]),
    piece("tower_broken", "Ruined tower top", "towers", tower_broken, [{"d": "tower_base", **{f: "ruin_side" for f in "nesw"}}], 1, 0.8, [1, 3], ["tower", "ruin"]),
    piece("house", "House", "buildings", house, [{"d": "house_base", "u": "house_top", "e": "house_gable", "w": "house_gable"}], 4, 1.5, [0, 2], ["house"],
          roles=["plaster", "roof", "timber", "stone"], parts=HOUSE_PARTS),
    piece("keep", "Keep", "buildings", keep, [{"d": "keep_base", "w": "keep_side", "s": "keep_side"}, {"d": "keep_base", "e": "keep_side", "s": "keep_side"},
                                          {"d": "keep_base", "w": "keep_side", "n": "keep_side"}, {"d": "keep_base", "e": "keep_side", "n": "keep_side"}]
          + [{"u": "keep_top"}] * 4, 4, 2.0, [0, 2], ["house"],
          roles=["stone", "roof", "timber", "iron"], flat=True, parts=KEEP_PARTS,
          cells=[[0, 0, 0], [1, 0, 0], [0, 0, 1], [1, 0, 1], [0, 1, 0], [1, 1, 0], [0, 1, 1], [1, 1, 1]]),
    piece("stairs", "Stairs", "buildings", stairs, [{"d": "base", "s": "stairs_top"}], 4, 0.4, [0, 0], ["prop"], parts=STAIRS_PARTS),
    piece("bridge", "Bridge", "buildings", bridge, [{"e": "bridge_link", "w": "bridge_link", "n": "bridge_rail", "s": "bridge_rail", "d": "bridge_span"}],
          2, 0.6, [0, 1], ["bridge"], roles=["timber", "moss", "stone", "iron"],
          parts={f"reach_{f}_{k}": [f"{f}:{s}"] for f in "ew" for k, s in (("wall", "wall_side"), ("near", "tower_side|house_gable"), ("keep", "keep_side"))}),
    piece("ground_grass", "Grass", "ground", ground_grass, [{"u": "ground"}], 1, 4.0, [-1, -1], ["ground"], roles=["grass", "path", "moss", "cloth"], layer="ground"),
    piece("ground_path", "Path", "ground", ground_path, [{"u": "ground"}], 1, 1.0, [-1, -1], ["ground", "path"], roles=["path", "grass", "moss", "stone"], layer="ground",
          parts={f"edge_{f}": [f"{f}:!#path"] for f in "nesw"}),
    piece("well", "Well", "props", well, [{"d": "base"}], 4, 0.3, [0, 0], ["prop"], roles=["stone", "roof", "timber", "iron"]),
    piece("rubble", "Rubble", "props", rubble, [{"d": "base"}], 4, 0.8, [0, 0], ["prop", "ruin"]),
    piece("banner", "Banner", "props", banner, [{"d": "base"}], 4, 0.3, [0, 0], ["prop"], roles=["timber", "cloth", "stone", "iron"]),
    piece("tree", "Tree", "props", tree, [{"d": "base"}], 4, 1.2, [0, 0], ["prop"], roles=["leaves", "moss", "timber", "cloth"],
          parts={k: [f"~{i}/4"] for i, k in enumerate(("oak", "pine", "poplar", "apple"))}),
]
