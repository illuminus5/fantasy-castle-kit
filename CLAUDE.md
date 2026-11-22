# Modular fantasy castle kit

Notes for working on the kit with Claude Code. README.md describes the kit itself: the pieces, sockets, join parts
and formats.

## Commands

- Build: `build.bat` (Blender 5.2 headless runs `blender\make.py`: every piece into `export\*.glb` and
  `export\catalog.json`). Set `BLENDER` for a non-default install.
- Copy into a game project: `sync.bat "<project>\Assets\Castle\Kit"`, or put that folder in `sync_target.txt`
  (git-ignored) and run `sync.bat` alone. From Git Bash, run the .bat files through PowerShell or `cmd /c`: quoting a
  path with spaces from bash fails.
- Concept art: `concepts.py` with a local ComfyUI running (see its docstring; `COMFYUI_DIR` points at ComfyUI).
  It writes `inspiration\` (git-ignored) and `out\` (review sheets, git-ignored).
- Check changes by rendering the pieces in the engine and looking at every image before showing it.

## The look

- timbermoss (mossy grey-green stone, oak timber, orange clay roofs) is the default theme; the stone is lifted brighter
  than the concept art for the additive display. `export\themes.json` is written by hand: edit it, don't regenerate it.
- Stone "skins": thin block quads proud of a darker mortar body, mask dimmed 0.86-1.0 per block; moss on lower
  courses and merlon caps; a fourth tint area D (clear mask, alpha 0) for iron, footings, flowers, apples.

## Things that bite

- glTFast (Unity) mirrors X on import. The catalog stays in glTF axes; an engine negates x and swaps e/w once on load.
- `blender\kit.py` is a copy of the shape helpers from the author's space station kit; changes there don't flow here.
- Piece ids `[a-z0-9_]`. Castle pieces never curl: `kit.finish(ob, cuts=False)`.
- Faces that may not face air: bottoms, `wall_edge` (a wall run must reach a wall, tower or the turret end),
  `tower_ring` (generated towers are capped), `stairs_top` and `bridge_link` (they must meet something). Everything
  else allows air, or the generator corners itself. `aligned` bottoms (walls, houses, keeps) must match the sides of
  what they stand on: that is what stops a wall crosswise on a wall. Sockets that fit nothing (`wall_side`,
  `turret_side`, `gate_face`, `ruin_side`, `bridge_rail`) still allow air and open faces; they keep the wrong things
  apart.
- Landings (`lands` / `above`): a stair top or bridge end may only meet a face whose cell above shows a storey with a
  door, or nothing over a wall's walk. A generator can only apply that once both cells are decided (the reference
  generator collapses level by level and narrows the level above). Keep the generator's levels able to meet it:
  houses may reach y 2 and bridges stay at y 0..1.
- Stacked pieces must read as one: wall parts plinth/sole, cap/crown and fill swap so a wall on a wall has no coping,
  plinth or merlons at the joint, and its skin courses carry on (`skin_plane(row0=...)`). Do the same for any new
  stackable.
- Join parts (`parts` in pieces.py) are looks only: a builder returns {"base": ob, part: ob}, make.py exports each as
  `<id>__<part>`, an engine merges the base with the parts whose conditions hold. Parts never change the socket
  rules. Each part's mesh is in piece space: build it on one side and turn it (`FROM_E`, `FROM_N`).
- `~k/n` conditions pick by a hash of the cell (0 at the origin, so a tray or preview shows part k = 0).
- The wall junction replaced wall_corner and wall_t (catalog `aliases` map them for old saves). Its placement faces are
  all `junction`; the generator uses `gen_faces` (corner, T, cross) so runs stay whole. Its arms are join parts.
- Keeps are two levels with a parapet; the roof is the separate keep_roof piece (keep_top fits keep_base and
  keep_roof_base). Every keep cell's outer side is keep_side, or stacking fails the aligned check.
- No near-black colours anywhere: on an additive display dark reads as see-through. `make.py` checks a luma floor.
- Four tint areas: R, G, B = A, B, C; alpha 0 = D. Paint with `pieces.tint` / `build`, not `kit.paint` (3 areas only).
- `kit.shade` smooths edges under 50 degrees, so shallow pyramids (the keep's roof) turn into domes: `flat=True`.
- Multi-cell pieces: cells are in catalog axes (x = Blender x, z = -Blender y); the keep's are x 0..1, z 0..1, y 0..1.
- Unity only re-imports a GLB when its bytes change.
