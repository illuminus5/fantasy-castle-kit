"""Concept art for the castle kit, made by the local ComfyUI with Qwen Image 2.1.

ComfyUI must be running on 127.0.0.1:8188 with the Qwen Image 2.1 models. Set COMFYUI_DIR to its folder (default
C:\\ComfyUI) and run this with ComfyUI's own Python:
    <ComfyUI>\\venv\\Scripts\\python.exe concepts.py [--styles a,b] [--seeds 1,2]
        style directions: inspiration\\style_<style>_<seed>.png, out\\styles.png, docs\\prompts.md
    <ComfyUI>\\venv\\Scripts\\python.exe concepts.py --refs [--pieces a,b] [--style-ref <png>]
        one reference per piece, in the chosen style (the concept passed as a reference image):
        inspiration\\ref_<piece>.png, out\\refs.png, docs\\ref_prompts.md
"""
import argparse
import json
import os
import pathlib
import shutil
import time
import urllib.request

URL = "http://127.0.0.1:8188"
COMFY = pathlib.Path(os.environ.get("COMFYUI_DIR", r"C:\ComfyUI"))
COMFY_OUT = COMFY / "output"
HERE = pathlib.Path(__file__).resolve().parent

SHEET = (
    "Isometric concept art sheet of a modular low-poly fantasy castle building kit for a tabletop game. "
    "Separate pieces neatly laid out with space between them on a plain very light grey background: a straight "
    "castle wall with crenellations, a corner wall, a gatehouse with a rounded arch and a wooden door, a round "
    "tower built from stacked segments with arrow slits, a crenellated tower top, a conical tower roof with a "
    "small flag, a small timber-framed house with a gable roof, stone stairs, a wooden bridge walkway, a broken "
    "ruined wall, a stone well, and square grass and cobblestone ground tiles. Chunky readable shapes, clean "
    "silhouettes, flat-shaded faces with soft bevels, bright cheerful colours, soft even studio lighting, no text. "
    "Palette: {palette}."
)
# ponytail: palettes stay bright on purpose. AURA's display is additive, so near-black reads as transparent.
STYLES = {
    "sandstone": "warm honey sandstone walls, cobalt blue roofs, cream trim, small red pennant flags",
    "whitegold": "pale white limestone walls, gleaming gold trim and roof finials, turquoise teal roofs",
    "brickslate": "terracotta red brick walls with white stone corners, light blue-grey slate roofs, warm wood doors",
    "timbermoss": "pale mossy grey-green stone, warm oak timber framing, orange clay tile roofs, bright moss accents",
}
W, H = 1472, 1104

# The chosen style (timbermoss): every piece reference is drawn in the style of this concept.
STYLE_REF = "inspiration/style_timbermoss_2.png"
REF = (
    "Using the exact art style, colours, materials and lighting of image 1, show a single {desc} as a low-poly game "
    "asset from the same modular fantasy castle kit. Isometric view, the one object centred on a plain very light grey "
    "background, nothing else, no text."
)
PIECE_REFS = {
    "wall_straight": "straight section of mossy stone castle curtain wall with crenellations",
    "wall_corner": "L-shaped corner section of mossy stone castle wall with crenellations",
    "wall_t": "T-shaped junction of three mossy stone castle walls with crenellations",
    "wall_end": "end of a mossy stone castle wall finished with a sturdy square buttress pillar",
    "wall_window": "mossy stone castle wall section with two narrow arrow-slit windows",
    "wall_gate": "castle gate wall section with a rounded stone arch and a heavy oak door with iron bands",
    "wall_broken": "ruined castle wall section with a crumbled broken top and a few fallen stones",
    "tower_base": "bottom segment of a round mossy stone tower with an arched oak door",
    "tower_mid": "middle segment of a round mossy stone tower with two small arched windows",
    "tower_top": "crenellated top of a round mossy stone tower, corbelled out, with a wooden floor",
    "tower_roof": "conical orange clay tile tower roof with a small pennant flag on top",
    "tower_broken": "ruined broken top of a round mossy stone tower, crumbling, with moss",
    "house": "small timber-framed cottage with cream plaster walls, oak beams, a wooden door and an orange clay tile gable roof",
    "keep": "large square stone keep hall with oak doors and a steep orange clay tile hip roof",
    "stairs": "short straight flight of mossy stone stairs",
    "bridge": "wooden plank walkway bridge with simple rope railings",
    "ground_grass": "square tile of bright grass with tufts and tiny flowers",
    "ground_path": "square tile of cobblestone path with a little grass at the edges",
    "well": "round stone well with a small wooden roof and a bucket",
    "rubble": "small pile of mossy stone rubble",
    "banner": "tall wooden flagpole with a long orange-red banner",
    "tree": "small low-poly round tree with a brown trunk and bright green leaves",
}


def graph(prompt, seed, prefix, ref=None, size=(W, H)):
    """Qwen Image 2.1 text-to-image; with ref (a file in ComfyUI's input folder) it is passed as image 1."""
    encode = {"clip": ["2", 0], "prompt": prompt, "negative_prompt": "", "resolution": 1024}
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "4": {"class_type": "TextEncodeQwenImage21", "inputs": encode},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": size[0], "height": size[1], "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0],
                                                   "seed": seed, "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }
    if ref:
        g["9"] = {"class_type": "LoadImage", "inputs": {"image": ref}}
        encode["images.image_1"] = ["9", 0]
        encode["vae"] = ["3", 0]
    return g


def call(path, body=None):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def render(prompt, seed, prefix, ref=None, size=(W, H)):
    pid = call("/prompt", {"prompt": graph(prompt, seed, prefix, ref, size)})["prompt_id"]
    while True:
        h = call(f"/history/{pid}").get(pid)
        if h and h.get("status", {}).get("completed"):
            img = h["outputs"]["8"]["images"][0]
            return COMFY_OUT / img.get("subfolder", "") / img["filename"]
        if h and h.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(h["status"])[:800])
        time.sleep(2)


def sheet(paths, labels, cols, dest, thumb=(W // 2, H // 2)):
    from PIL import Image, ImageDraw, ImageFont  # ComfyUI's venv ships Pillow
    thumbs = [Image.open(p).convert("RGB").resize(thumb) for p in paths]
    tw, th = thumbs[0].size
    out = Image.new("RGB", (cols * tw, -(-len(thumbs) // cols) * (th + 36)), "white")
    draw, font = ImageDraw.Draw(out), ImageFont.load_default(size=28)
    for i, (t, label) in enumerate(zip(thumbs, labels)):
        x, y = (i % cols) * tw, (i // cols) * (th + 36)
        draw.text((x + 10, y + 2), label, fill="black", font=font)
        out.paste(t, (x, y + 36))
    dest.parent.mkdir(exist_ok=True)
    out.save(dest)


def refs(pieces, style_ref, seed):
    """One reference image per piece, drawn in the style of the chosen concept."""
    name = "castle_style_ref.png"
    shutil.copyfile(HERE / style_ref, COMFY / "input" / name)
    made, notes = [], [f"# Piece reference prompts (Qwen Image 2.1, image 1 = {style_ref}, seed {seed})\n"]
    for piece in pieces:
        prompt = REF.format(desc=PIECE_REFS[piece])
        notes.append(f"## {piece}\n{prompt}\n")
        src = render(prompt, seed, f"castle/ref_{piece}", ref=name, size=(1024, 1024))
        dest = HERE / "inspiration" / f"ref_{piece}.png"
        shutil.copyfile(src, dest)
        made.append(dest)
        print("made", dest.name, flush=True)
    (HERE / "docs" / "ref_prompts.md").write_text("\n".join(notes), encoding="utf-8")
    sheet(made, pieces, 6, HERE / "out" / "refs.png", thumb=(400, 400))
    print("sheet", HERE / "out" / "refs.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", default=",".join(STYLES))
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--refs", action="store_true")
    ap.add_argument("--pieces", default=",".join(PIECE_REFS))
    ap.add_argument("--style-ref", default=STYLE_REF)
    a = ap.parse_args()
    if a.refs:
        refs(a.pieces.split(","), a.style_ref, int(a.seeds.split(",")[0]))
        return
    styles, seeds = a.styles.split(","), [int(s) for s in a.seeds.split(",")]
    made, labels, notes = [], [], ["# Concept prompts (Qwen Image 2.1, 25 steps, cfg 1, euler/simple, %dx%d)\n" % (W, H)]
    for style in styles:
        prompt = SHEET.format(palette=STYLES[style])
        notes.append(f"## {style}\n{prompt}\n")
        for seed in seeds:
            src = render(prompt, seed, f"castle/style_{style}_{seed}")
            dest = HERE / "inspiration" / f"style_{style}_{seed}.png"
            shutil.copyfile(src, dest)
            made.append(dest)
            labels.append(f"{style}  (seed {seed})")
            print("made", dest.name, flush=True)
    (HERE / "docs" / "prompts.md").write_text("\n".join(notes), encoding="utf-8")
    sheet(made, labels, len(seeds), HERE / "out" / "styles.png")
    print("sheet", HERE / "out" / "styles.png")


if __name__ == "__main__":
    main()
