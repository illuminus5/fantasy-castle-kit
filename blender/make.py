"""Builds the castle kit: every piece in pieces.py into export/<category>.glb (meshes named by piece id, no
materials, the Col tint mask) and export/catalog.json (sizes, sockets and generator hints, in glTF axes).

Run through build.bat, or:  blender -b --python blender/make.py
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
KIT = HERE.parent
sys.path[:0] = [str(HERE)]

import bpy  # noqa: E402

import castle_grid as G  # noqa: E402
import kit  # noqa: E402
from pieces import PIECES  # noqa: E402

# ponytail: one fixed floor for the additive display (darker reads as see-through); raise it if a theme looks thin.
LUMA_FLOOR = 0.15


def gltf_box(lo, hi):
    """Blender (x, y, z) to glTF (x, z, -y), rounded."""
    return [[round(lo.x, 4), round(lo.z, 4), round(-hi.y, 4)], [round(hi.x, 4), round(hi.z, 4), round(-lo.y, 4)]]


def luma(hexc):
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def check_themes():
    """Every role a piece uses has a colour in every theme, and none is too dark for AURA."""
    themes = json.loads((KIT / "export" / "themes.json").read_text(encoding="utf-8"))
    roles = {r for p in PIECES for r in p["roles"]}
    for t in themes["themes"]:
        for r in sorted(roles):
            c = t["colors"].get(r)
            assert c, f"theme {t['id']}: no colour for role {r}"
            assert luma(c) >= LUMA_FLOOR, f"theme {t['id']}: {r} {c} is too dark for the see-through display ({luma(c):.2f})"


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    check_themes()
    ids = [p["id"] for p in PIECES]
    assert len(ids) == len(set(ids)), "duplicate piece id"
    by_category, entries = {}, []
    for p in PIECES:
        look = p["build"]()
        look = look if isinstance(look, dict) else {"base": look}
        assert set(look) - {"base"} == set(p["parts"]), f"{p['id']}: built parts {sorted(look)} != declared {sorted(p['parts'])}"
        for key, ob in look.items():
            kit.shade(kit.finish(ob, cuts=False))
            if p.get("flat"):
                for poly in ob.data.polygons:
                    poly.use_smooth = False
            ob.name = ob.data.name = p["id"] if key == "base" else f"{p['id']}__{key}"
            by_category.setdefault(p["category"], []).append(ob)
        ob = look["base"]
        aabb = gltf_box(*kit.bounds(ob))
        entry = {k: v for k, v in p.items() if k not in ("build", "flat", "parts")}
        entry.update(aabb=aabb, tris=kit.tris(ob),
                     solids=[[[round((a + b) / 2, 4) for a, b in zip(*aabb)], [round((b - a) / 2, 4) for a, b in zip(*aabb)]]])
        if p["parts"]:
            entry["parts"] = [{"id": k, "mesh": f"{p['id']}__{k}", "cell": v.get("cell", 0), "when": v["when"],
                               "tris": kit.tris(look[k])} for k, v in p["parts"].items()]
        entries.append(entry)
    out = KIT / "export"
    for category, obs in by_category.items():
        kit.export(out / f"{category}.glb", obs)
    # ids that older saves may hold, and the piece that replaced them
    aliases = {"wall_corner": "wall_junction", "wall_t": "wall_junction"}
    catalog = {"grid": {"cell": G.CELL, "level": G.LEVEL, "tile_top": G.TILE_TOP}, "sockets": G.SOCKETS, "aliases": aliases, "pieces": entries}
    (out / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    print("catalog", len(entries), "pieces,", sum(e["tris"] for e in entries), "triangles")


if __name__ == "__main__":
    main()
