"""Shape, paint and export helpers for Blender, copied from the author's space station kit so this kit builds on
its own. The castle uses box, cyl, lathe, prism, ball, turn, move, joined, finish, shade, export, new_object, bounds
and tris; the rest (pattern UVs, cuts for curling a mesh round a ring) comes along unused.

Blender space: metres, +Z up. Every mesh carries:
  Col   a per-corner colour mask (pieces.py says what its channels mean for the castle)
  UV    pattern coordinates in metres
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

AREAS = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1)]
BROKEN = (0, 0, 0, 1)
# The kit's chunkiness: every chamfer is this many times its written size, and has this many steps (1 is a flat
# chamfer, 2 a rounder edge at more than twice the triangles). Set in the environment to try another look.
BEVEL = float(os.environ.get("KIT_BEVEL", "1"))
ROUND = int(os.environ.get("KIT_ROUND", "1"))


# ---- objects

def _linked(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def new_object(name, verts=(), faces=(), edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), list(faces))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def evaluated(ob):
    """ob with its modifiers applied (bpy.ops.object.modifier_apply is unreliable without a window)."""
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def edit(ob):
    """with edit(ob) as bm: ... edits ob's mesh as a bmesh."""
    class Edit:
        def __enter__(self):
            self.bm = bmesh.new()
            self.bm.from_mesh(ob.data)
            return self.bm

        def __exit__(self, *exc):
            self.bm.to_mesh(ob.data)
            self.bm.free()
    return Edit()


def fix_normals(ob):
    with edit(ob) as bm:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return ob


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bounds(*obs):
    """The corners (low, high) of the box around the objects."""
    cos = [v.co for o in obs for v in o.data.vertices]
    return Vector([min(c[i] for c in cos) for i in range(3)]), Vector([max(c[i] for c in cos) for i in range(3)])


def copy(ob, name=None):
    new = ob.copy()
    new.data = ob.data.copy()
    new.name = new.data.name = name or ob.name
    bpy.context.scene.collection.objects.link(new)
    return new


# ---- shapes

def box(name, at, half, bevel=0.02, segments=1):
    """A box with chamfered edges: half its size each way (x, y, z) about at. bevel 0 leaves it sharp."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    for v in bm.verts:
        v.co = Vector(at) + Vector((v.co.x * half[0], v.co.y * half[1], v.co.z * half[2]))
    w = min(bevel * BEVEL, min(half) * 0.6)
    if w > 0.001:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=w, offset_type="OFFSET", segments=max(segments, ROUND), profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return _linked(name, bm)


def prism(name, outline, y0, y1, bevel=0.02):
    """An outline [(x, z), ...] drawn on the front and pushed back from y0 to y1: wedges, brackets, console sides."""
    n = len(outline)
    verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    ob = new_object(name, verts, faces)
    with edit(ob) as bm:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        w = min(bevel, abs(y1 - y0) * 0.3)
        if w > 0.001:
            bmesh.ops.bevel(bm, geom=bm.edges[:], offset=w, offset_type="OFFSET", segments=1, profile=0.5,
                            affect="EDGES", clamp_overlap=True)
    return ob


def cyl(name, at, r, h, axis="z", segments=12, bevel=0.0, r2=None):
    """A cylinder (or a cone, with r2) centred on at, its length h along axis; bevel chamfers its two rims."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r, radius2=r if r2 is None else r2, depth=h)
    w = min(bevel, r * 0.5, h * 0.3)
    if w > 0.001:
        rims = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6 and len(e.link_faces) == 2
                and any(len(f.verts) > 4 for f in e.link_faces)]
        bmesh.ops.bevel(bm, geom=rims, offset=w, offset_type="OFFSET", segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
    ob = _linked(name, bm)
    if axis != "z":
        turn(ob, "y" if axis == "x" else "x", 90)
    return move(ob, at)


def lathe(name, profile, segments=16, at=(0, 0, 0)):
    """A profile [(radius, z), ...] spun about +Z. A radius of 0 closes that end to a point."""
    verts, faces, rings = [], [], []
    for r, z in profile:
        if r <= 0:
            rings.append([len(verts)])
            verts.append((at[0], at[1], at[2] + z))
        else:
            rings.append(list(range(len(verts), len(verts) + segments)))
            verts += [(at[0] + r * math.cos(a), at[1] + r * math.sin(a), at[2] + z)
                      for a in (2 * math.pi * k / segments for k in range(segments))]
    for a, b in zip(rings, rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                faces.append((a[0], b[k], b[j]))
            elif len(b) == 1:
                faces.append((a[k], a[j], b[0]))
            else:
                faces.append((a[k], a[j], b[j], b[k]))
    return fix_normals(new_object(name, verts, faces))


def ball(name, at, radii, cuts=2):
    """A rounded form: a sphere of even quads stretched to radii (x, y, z) about at."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    at, radii = Vector(at), Vector(radii)
    for v in bm.verts:
        v.co = v.co.normalized() * radii + at
    return _linked(name, bm)


def tube(name, path, r, segments=8, round_ends=False):
    """A pipe of radius r through the points of path, its ends cut flat (or rounded: cables, handles). Corners
    are mitred: pass the path through rounded() first for an elbow."""
    path = [Vector(p) for p in path]
    tang = [(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized() for i in range(len(path))]
    stations = [(p, t, r) for p, t in zip(path, tang)]
    if round_ends:
        stations = ([(path[0] - tang[0] * r, tang[0], 0), (path[0] - tang[0] * r * 0.6, tang[0], r * 0.75)] + stations
                    + [(path[-1] + tang[-1] * r * 0.6, tang[-1], r * 0.75), (path[-1] + tang[-1] * r, tang[-1], 0)])
    else:
        stations = [(path[0], tang[0], 0)] + stations + [(path[-1], tang[-1], 0)]
    verts, faces, rings = [], [], []
    n = Vector((0, 0, 1))
    for p, t, rad in stations:
        n = n - t * n.dot(t)
        n = n.normalized() if n.length > 1e-6 else t.orthogonal().normalized()
        b = t.cross(n)
        if rad == 0:
            rings.append([len(verts)])
            verts.append(p)
        else:
            rings.append(list(range(len(verts), len(verts) + segments)))
            verts += [p + (b * math.cos(a) + n * math.sin(a)) * rad for a in (2 * math.pi * k / segments for k in range(segments))]
    for a, b in zip(rings, rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            if len(a) == 1:
                faces.append((a[0], b[k], b[j]))
            elif len(b) == 1:
                faces.append((a[k], a[j], b[0]))
            else:
                faces.append((a[k], a[j], b[j], b[k]))
    return fix_normals(new_object(name, verts, faces))


def rounded(path, radius, steps=3):
    """path with each corner replaced by an arc of that radius: what tube() needs for an elbow."""
    path = [Vector(p) for p in path]
    out = [path[0]]
    for a, c, b in zip(path, path[1:], path[2:]):
        u, v = (a - c).normalized(), (b - c).normalized()
        half = u.angle(v) / 2
        if half > math.pi / 2 - 1e-3:
            out.append(c)
            continue
        d = min(radius / math.tan(half), (a - c).length * 0.49, (b - c).length * 0.49)
        centre = c + (u + v).normalized() * (d / math.cos(half))
        start, end = c + u * d - centre, c + v * d - centre
        for k in range(steps + 1):  # slerp gives directions only: the arc's radius is put back
            out.append(centre + start.normalized().slerp(end.normalized(), k / steps) * start.length)
    return out + [path[-1]]


def ring(name, at, radius, thickness, facing="y", segments=16, sides=4):
    """A torus about a point: flanges, hoops, hatch wheels. facing: the axis through its hole."""
    prof = [(radius + thickness * math.cos(a), thickness * math.sin(a)) for a in (2 * math.pi * (k + 0.5) / sides for k in range(sides))]
    ob = lathe(name, prof + prof[:1], segments=segments)
    if facing != "z":
        turn(ob, "x" if facing == "y" else "y", 90)
    return move(ob, at)


def holed(name, at, half, r, y0, y1, segments=12):
    """A plate with a round hole through it, standing in the x-z plane: half its size each way (x, z) about
    at (x, z), from y0 back to y1, the hole of radius r in its middle. A porthole's surround."""
    (cx, cz), (hx, hz), n = at, half, segments
    ring, rim = [], []  # the hole's edge, and the points of the plate's edge straight out from it
    for k in range(n):
        c, s = math.cos(math.tau * (k + 0.5) / n), math.sin(math.tau * (k + 0.5) / n)
        t = min(hx / abs(c), hz / abs(s))
        ring.append((cx + r * c, cz + r * s))
        rim.append((cx + t * c, cz + t * s))
    outline = []  # the plate's edge in order, its corners put in where the rim turns one
    faces = []  # each: the outline's points (by index) between two neighbours on the ring
    for k in range(n):
        j = (k + 1) % n
        span = [len(outline)]
        outline.append(rim[k])
        if (abs(abs(rim[k][0] - cx) - hx) < 1e-6) != (abs(abs(rim[j][0] - cx) - hx) < 1e-6):
            a = math.tau * (k + 1) / n
            span.append(len(outline))
            outline.append((cx + math.copysign(hx, math.cos(a)), cz + math.copysign(hz, math.sin(a))))
        faces.append((k, span))
    m = len(outline)
    verts = [(x, y, z) for y in (y0, y1) for x, z in ring] + [(x, y, z) for y in (y0, y1) for x, z in outline]
    polys = []
    for k, span in faces:
        j, nxt = (k + 1) % n, (span[-1] + 1) % m
        for side in (0, 1):  # the front, the back
            polys.append([k + side * n, *[2 * n + side * m + i for i in span], 2 * n + side * m + nxt, j + side * n])
        polys.append([k, j, j + n, k + n])  # the hole's wall
    polys += [[2 * n + i, 2 * n + (i + 1) % m, 2 * n + m + (i + 1) % m, 2 * n + m + i] for i in range(m)]  # the plate's edge
    return fix_normals(new_object(name, verts, polys))


def turn(ob, axis, degrees, pivot=(0, 0, 0)):
    """Rotate ob's mesh about an axis ("x", "y", "z") through pivot."""
    ob.data.transform(Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(degrees), 4, axis.upper()) @ Matrix.Translation(-Vector(pivot)))
    return ob


def move(ob, by):
    ob.data.transform(Matrix.Translation(by))
    return ob


def mirrored(ob, axis=0):
    """ob with its mirror image across the plane where that axis is 0 added."""
    with edit(ob) as bm:
        new = bmesh.ops.duplicate(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:])["geom"]
        for v in new:
            if isinstance(v, bmesh.types.BMVert):
                v.co[axis] = -v.co[axis]
        bmesh.ops.reverse_faces(bm, faces=[f for f in new if isinstance(f, bmesh.types.BMFace)])
    return ob


def join(a, b):
    """Merge b's mesh into a."""
    _layers(a.data)
    _layers(b.data)
    with edit(a) as bm:
        bm.from_mesh(b.data)
    bpy.data.objects.remove(b)
    return a


def joined(*obs):
    for o in obs[1:]:
        join(obs[0], o)
    return obs[0]


def cut(ob, planes):
    """Slice ob along planes [(point, normal), ...], keeping both sides."""
    with edit(ob) as bm:
        for co, no in planes:
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=co, plane_no=no)
    return ob


# ---- paint and UVs

def _layers(me):
    col = me.color_attributes.get("Col")
    if col is None:
        col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        for d in col.data:
            d.color = AREAS[0]
    uv = me.uv_layers.get("UV") or me.uv_layers.new(name="UV")
    me.color_attributes.active_color = col
    me.color_attributes.render_color_index = me.color_attributes.find("Col")
    return col, uv


def paint(ob, area, where=None):
    """Mark faces as tintable area 0, 1 or 2: all of them, or those where(centre, normal) holds."""
    col = _layers(ob.data)[0]
    for p in ob.data.polygons:
        if where is None or where(p.center, p.normal):
            for li in p.loop_indices:
                col.data[li].color = AREAS[area]
    return ob


def P(*pairs):
    """Shapes [(area, shape), ...] painted and joined into one piece."""
    return joined(*[paint(ob, area) for area, ob in pairs])


def uv_box(ob):
    """Pattern UVs in metres, each face seen square-on from the side it faces (so nothing reads mirrored)."""
    me = ob.data
    uv = _layers(me)[1]
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            if ax == 1:
                uv.data[li].uv = (c.x if n.y < 0 else -c.x, c.z)
            elif ax == 0:
                uv.data[li].uv = (c.y if n.x > 0 else -c.y, c.z)
            else:
                uv.data[li].uv = (c.x if n.z > 0 else -c.x, c.y)
    return ob


# ---- breaking

def shatter(ob, n, seed=0):
    """The chunks ob breaks into: about n solid pieces cut by planes through it, the cuts painted as broken edges.
    A thin piece (a panel, a plate) is cut across, never split into two thinner sheets. ob itself is left whole."""
    rng = random.Random(seed)
    _layers(ob.data)
    first = bmesh.new()
    first.from_mesh(ob.data)
    parts = [first]

    def size(bm):
        cos = [v.co for v in bm.verts]
        return [max(c[i] for c in cos) - min(c[i] for c in cos) for i in range(3)], [(max(c[i] for c in cos) + min(c[i] for c in cos)) / 2 for i in range(3)]

    for _ in range(n * 3):  # some cuts miss or shave nothing off: try a few more times than needed
        if len(parts) >= n:
            break
        parts.sort(key=lambda bm: -max(size(bm)[0]))
        bm = parts.pop(0)
        ext, mid = size(bm)
        thin = min(range(3), key=lambda i: ext[i])
        no = Vector([rng.uniform(-1, 1) for _ in range(3)])
        if ext[thin] < 0.35 * max(ext):
            no[thin] = 0.0
        no[max(range(3), key=lambda i: ext[i])] += rng.choice((-1.5, 1.5))  # mostly across its longest side
        co = Vector([mid[i] + rng.uniform(-0.2, 0.2) * ext[i] for i in range(3)])
        halves = []
        for outer in (True, False):
            half = bm.copy()
            got = bmesh.ops.bisect_plane(half, geom=half.verts[:] + half.edges[:] + half.faces[:], dist=1e-5, plane_co=co,
                                         plane_no=no.normalized(), clear_outer=outer, clear_inner=not outer)
            edges = [e for e in got["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
            layer = half.loops.layers.float_color["Col"]
            for f in bmesh.ops.triangle_fill(half, edges=edges, use_beauty=True, use_dissolve=False,
                                             normal=no if outer else -no)["geom"]:
                if isinstance(f, bmesh.types.BMFace):
                    for loop in f.loops:
                        loop[layer] = BROKEN
            if len(half.faces) >= 4:
                halves.append(half)
            else:
                half.free()
        if len(halves) == 2:
            parts += halves
            bm.free()
        else:  # the plane missed: keep the piece whole
            for h in halves:
                h.free()
            parts.append(bm)
    out = []
    for i, bm in enumerate(parts):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        out.append(_linked(f"{ob.name}__c{i}", bm))
    return out


# ---- finishing and export

def finish(ob, cuts=True):
    """What every mesh gets before it is exported or shattered: pattern UVs, and a cut along each metre line
    it crosses sideways, so that no edge is too long to follow a ring station's curve (not for a piece that is
    never curled: a `rigid` one)."""
    ob.data.validate()
    _layers(ob.data)
    uv_box(ob)
    lo, hi = bounds(ob)
    planes = []
    for axis in (0, 1) if cuts else ():
        if hi[axis] - lo[axis] > 1.2:
            for k in range(math.ceil(lo[axis] + 0.2), math.floor(hi[axis] - 0.2) + 1):
                planes.append((tuple(float(k) if i == axis else 0.0 for i in range(3)), tuple(1.0 if i == axis else 0.0 for i in range(3))))
    cut(ob, planes)
    return ob


def shade(ob):
    """Soft chamfers, flat faces, crisp corners: edges sharper than 50 degrees stay sharp, and the normals lean
    to the larger faces, so a chamfered box reads as a rounded one without its big faces looking pillowed."""
    with edit(ob) as bm:
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(50))
        for f in bm.faces:
            f.smooth = True
    m = ob.modifiers.new("wn", "WEIGHTED_NORMAL")
    m.keep_sharp, m.weight, m.mode = True, 50, "FACE_AREA"
    evaluated(ob)
    _layers(ob.data)  # the export takes the active color attribute: a chunk's mesh is new and has none marked
    return ob


def export(path, objs):
    """One GLB of meshes named by piece id (chunks and moving parts as id__c0, id__leaf0), no materials."""
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_skins=False,
                              export_animations=False, export_materials="NONE", export_vertex_color="ACTIVE",
                              export_all_vertex_colors=False, export_apply=False)
    print("exported", path, len(objs), "meshes,", sum(tris(o) for o in objs), "triangles")
