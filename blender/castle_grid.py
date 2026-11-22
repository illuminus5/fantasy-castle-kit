"""The castle kit's metric contract and socket rules. Unity (and any other engine) gets the same numbers through
export/catalog.json.

Blender space: metres, +Z up, a piece's front is -Y. The glTF export turns that into +Y up with the front at +Z,
and the catalog is written in those glTF axes. Faces are named in catalog axes:
  n = +Z (the front, Blender -Y)   e = +X   s = -Z (Blender +Y)   w = -X   u = up   d = down

The lattice is cubic: a cell is CELL wide and deep and LEVEL tall, so a quarter turn never changes a footprint and the
generator can treat every cell alike. A piece's origin is the bottom centre of its first cell; its geometry stays
inside its cells (x, y in -1..1, z in 0..2 for a one-cell piece), except trim that may lean OVER into the cell above
by up to OVER (merlons, roof eaves) so that stacked pieces read as one wall.

Ground tiles live on their own layer under the board's first level: their top sits TILE_TOP above the board, and
pieces standing on the board sink into them by that much.

Socket rules (catalog "sockets"): two touching faces fit if either lists the other in "fits". A face left out of a
piece's table is "open" (air). "open" meets any face whose "air" is true. Faces that may not face air: bottoms (they
need support), a wall's ends (a run goes on into a wall, a tower or the turret end) and the tower ring (generated towers
are always capped). Placement never checks empty neighbours, so "air" only binds the generator; the player stays free.
An "aligned" bottom stacked on a piece must show the same sides as the piece under it (no wall crosswise on a wall,
no keep half over another).

A stair's top or a bridge's end "lands" (at wall-walk height, 1.9 m up its level) on the face it meets; that face's
"above" says what the cell over it must show toward the landing: a storey's side (where a door opens onto the deck)
or "empty" (a wall's open walk). Without it a bridge would meet a house's roof or a tower's cone. Only the generator
holds to it (it collapses level by level, so the landing is known before the level above); by hand anything goes.

Pieces can also have optional parts (pieces.py "parts") that show only when their neighbours say so: a tower's stone
shoulder where a wall meets it, a house's roof only when no storey stands on it. They never change the rules above.
"""
CELL = 2.0
LEVEL = 2.0
OVER = 0.45  # how far trim may rise into the cell above
TILE_TOP = 0.06  # a ground tile's top above the board
WALL = 0.7  # a curtain wall's thickness
TOWER_R = 0.92  # a round tower's radius (it fits its cell, leaving a lip)
MERLON = (0.42, 0.4)  # a merlon's width and height
H = CELL / 2

# see the docstring for air, fits and aligned
SOCKETS = {
    "open": {"air": True},
    "ground": {"air": True, "fits": ["base", "wall_base", "tower_base", "house_base", "keep_base", "bridge_span"]},  # the board, a ground tile's top
    "base": {"air": False},  # a prop standing on the ground
    "wall_base": {"air": False, "aligned": True},
    "wall_top": {"air": True, "fits": ["wall_base"]},
    "wall_edge": {"air": False, "fits": ["wall_edge", "tower_side"]},  # a wall's end: it joins a wall or a tower
    "wall_side": {"air": True, "above": ["empty"]},  # a wall's flank: never against another wall's end or flank, nor a tower
    "turret_side": {"air": True},  # the round wall end's drum: nothing joins it
    "gate_face": {"air": True},  # a gate's doors: kept clear of stairs
    "ruin_side": {"air": True},  # a ruined wall or tower top: too low for a stair, a bridge or a joining wall
    "house_base": {"air": False, "aligned": True},
    "house_top": {"air": True, "fits": ["house_base"]},  # a second storey
    "house_gable": {"air": True, "fits": ["house_gable", "wall_side", "tower_side"], "above": ["house_gable"]},  # gable to gable: a long house
    "keep_base": {"air": False, "aligned": True},
    "keep_top": {"air": True, "fits": ["keep_base"]},
    "tower_base": {"air": False},
    # air False: the generator always caps a tower (storey, top, roof or ruin). Players can still leave one bare,
    # because placement never checks empty neighbours.
    "tower_ring": {"air": False, "fits": ["tower_base", "roof"]},
    "tower_side": {"air": True, "fits": ["wall_edge", "tower_side"], "above": ["tower_side", "parapet_side"]},  # towers side by side grow a link
    "parapet_side": {"air": True, "fits": ["wall_edge", "tower_side", "parapet_side"]},  # a crenellated top: walls and towers join it, nothing lands on it
    "stairs_top": {"air": False, "lands": True, "fits": ["wall_side", "tower_side", "keep_side", "house_gable"]},  # what stairs lean on
    "keep_side": {"air": True},  # a keep's ground-floor walls (for stairs and bridges)
    "roof_seat": {"air": True, "fits": ["roof"]},  # a crenellated tower top takes a roof
    "roof": {"air": False},
    # A bridge is a one-cell walkway at wall-walk height: its ends join another segment or the side of a tower, wall,
    # keep or house, and hold it up ("carries": a joined face counts as support, not only a bottom). Its sides take
    # nothing; under it is air or the ground, never a wall top.
    "bridge_link": {"air": False, "carries": True, "lands": True, "fits": ["bridge_link", "tower_side", "wall_side", "keep_side", "house_gable"]},
    "bridge_rail": {"air": True},
    "bridge_span": {"air": True},
}
