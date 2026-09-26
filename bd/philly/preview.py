"""Render the hull to SVG without a GPU, a browser, or a display.

`just viewer` needs a browser to draw into, which a headless container doesn't
have -- so in a remote session there is no way to look at the model, only to
print numbers about it. A hull can be watertight, correctly scaled and still
the wrong shape, and several bugs here were only obvious on sight.

So this projects the tessellated mesh, sorts the triangles back to front and
flat-shades them: a painter's-algorithm renderer in about a hundred lines. It
writes SVG, which renders anywhere, and rasterises to PNG as well when a
Chromium is lying around (Playwright's, or the system's). The captions survive
into the SVG but a headless Chromium may drop text from the PNG, so the caption
is printed too.

    just preview
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
from dataclasses import dataclass, replace
from glob import glob
from pathlib import Path

import numpy as np
from build123d import Part

# Set before the model is imported, so module-level choices can read it. The
# model is imported inside main() for that reason, and so that a model module
# is free to `from preview import preview_mode` without an import cycle.
PREVIEW_ENV = "PREVIEW"

# What to render, as module:callable. The callable takes no arguments and
# returns a Part. Override with --model to reuse this script elsewhere.
DEFAULT_MODEL = "main:model"

# Tessellation tolerance in final millimetres: finer than the eye at this size.
MESH_TOLERANCE = 0.08


def preview_mode() -> bool:
    """True when rendering a preview, so a model can trade detail for speed.

    Set by this script before it imports the model. A model is free to ignore
    it; where it costs nothing to honour -- fewer loft sections, say -- the
    edit loop gets quicker without changing what the preview shows.
    """
    return os.environ.get(PREVIEW_ENV, "") not in ("", "0", "false", "False")


@dataclass(frozen=True)
class View:
    """A camera and canvas for one rendering."""

    name: str
    azimuth: float
    elevation: float
    width: int
    height: int
    label: str


# Azimuth 270 puts +X (bow to stern) along the screen's X axis in every view,
# so the three line up with each other.
VIEWS = (
    # High enough to look into the hull: at a low angle the decks hide the
    # open waist, and an interior you cannot see is one you cannot check.
    View("hull", 322.0, 48.0, 1100, 460, "three-quarter"),
    View("hull_plan", 270.0, 88.0, 1100, 340, "plan - bow at left"),
    View("hull_side", 270.0, 0.0, 1100, 280, "profile - sheer and flat bottom"),
    # Looking down the length, which is the only view that shows the shape of
    # the sections themselves -- how far the sides flare and how they bow.
    View("hull_bow", 0.0, 6.0, 700, 420, "bow on - section shape"),
)

LIGHT = np.array([0.4, -0.5, 0.75])

# Margin around the drawing, and the strip the caption sits in.
PAD = 30
CAPTION = 20


def _camera(azimuth: float, elevation: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Right, up and forward vectors for a camera aimed at the origin."""
    az, el = np.radians(azimuth), np.radians(elevation)
    forward = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    right = np.cross(np.array([0.0, 0.0, 1.0]), forward)
    right /= np.linalg.norm(right)
    return right, np.cross(forward, right), forward


def mesh(part: Part) -> tuple[np.ndarray, np.ndarray]:
    """Tessellate once; every view reuses the same triangles."""
    vertices, triangles = part.tessellate(MESH_TOLERANCE)
    return np.array([[v.X, v.Y, v.Z] for v in vertices]), np.array(triangles)


def fit(view: View, geometry: tuple[np.ndarray, np.ndarray]) -> View:
    """Grow a view's canvas if the model is taller than it was drawn for.

    The canvas sizes suit a hull: long, low, and wider than it is tall. Stand a
    200mm mast in it and fitting the whole thing into a 280px-high strip shrinks
    the boat to a smudge. Growing the canvas instead keeps the scale sensible.

    Views the model already fits are returned untouched, so the hull's own
    renders are unchanged.
    """
    points, _ = geometry
    right, up, _ = _camera(view.azimuth, view.elevation)
    screen = points @ np.stack([right, up]).T
    span = np.maximum(screen.max(axis=0) - screen.min(axis=0), 1e-9)
    needed = round((view.width - 2 * PAD) * span[1] / span[0]) + 2 * PAD + CAPTION
    if needed <= view.height:
        return view
    return replace(view, height=min(int(needed), 4 * view.width))


def render(
    geometry: tuple[np.ndarray, np.ndarray], view: View, path: Path, *, caption: str = ""
) -> int:
    """Write the mesh to `path` as a flat-shaded SVG. Returns the triangle count."""
    points, faces = geometry

    right, up, forward = _camera(view.azimuth, view.elevation)
    screen = points @ np.stack([right, up]).T
    corners = screen[faces]

    # Flat shading from the face normals, and depth for the painter's sort.
    normals = np.cross(
        points[faces[:, 1]] - points[faces[:, 0]],
        points[faces[:, 2]] - points[faces[:, 0]],
    )
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals /= np.where(lengths == 0, 1.0, lengths)
    # Absolute value so inside faces -- the hull is open, you see into it -- are
    # lit rather than black.
    lit = np.abs(normals @ (LIGHT / np.linalg.norm(LIGHT))) * 0.75 + 0.25

    # Depth cue. Without it a recessed floor and the deck above it shade
    # identically -- both face up -- and an open span is invisible against the
    # decks either side, which is the one thing this render exists to show.
    depth = points[faces].mean(axis=1) @ forward
    near = (depth - depth.min()) / max(float(depth.max() - depth.min()), 1e-9)
    shade = lit * (0.55 + 0.45 * near)

    low, high = corners.reshape(-1, 2).min(axis=0), corners.reshape(-1, 2).max(axis=0)
    span = np.maximum(high - low, 1e-9)
    scale = min((view.width - 2 * PAD) / span[0], (view.height - 2 * PAD - CAPTION) / span[1])
    # SVG's Y axis points down, so flip it.
    flip = np.array([1.0, -1.0])
    offset = np.array([view.width / 2, view.height / 2]) - (low + high) / 2 * scale * flip

    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view.width}" '
        f'height="{view.height}" viewBox="0 0 {view.width} {view.height}">',
        f'<rect width="{view.width}" height="{view.height}" fill="#14181d"/>',
    ]
    # Farthest first: `forward` points from the model toward the camera, so a
    # larger dot product is nearer. Reversing this paints far over near, which
    # renders the hull inside-out -- convincingly enough that it went unnoticed.
    for i in np.argsort(depth):
        pixels = corners[i] * scale * flip + offset
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in pixels)
        level = shade[i]
        rgb = (int(150 * level + 30), int(115 * level + 24), int(78 * level + 16))
        body.append(f'<polygon points="{coords}" fill="rgb{rgb}"/>')
    text = " - ".join(p for p in (view.label, caption) if p)
    body.append(
        f'<text x="{PAD}" y="{view.height - 14}" fill="#9aa4b2" '
        f'font-family="monospace" font-size="18">{text}</text>'
    )
    body.append("</svg>")

    path.write_text("\n".join(body))
    # Chromium renders a bare .svg with a white page margin around it; wrapping
    # it in a zero-margin page makes the PNG match the SVG.
    path.with_suffix(".html").write_text(
        f'<body style="margin:0;background:#14181d">{"".join(body)}</body>'
    )
    return len(faces)


def find_chromium() -> str | None:
    """Playwright's Chromium, else one on PATH, else Windows' usual shelves.

    Windows installers do not put the browser on PATH, so without the last
    look this writes SVG only on the machine most likely to have a browser.
    """
    for pattern in (
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/*",
    ):
        for candidate in sorted(glob(pattern)):
            if Path(candidate).is_file():
                return candidate
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for root in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        for relative in (
            r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
        ):
            installed = Path(os.environ.get(root, "")) / relative
            if os.environ.get(root) and installed.is_file():
                return str(installed)
    return None


def rasterise(chromium: str, view: View, path: Path) -> bool:
    """Screenshot the SVG's HTML wrapper into a PNG beside it."""
    try:
        subprocess.run(
            [
                chromium,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                f"--window-size={view.width},{view.height}",
                f"--screenshot={path.with_suffix('.png').resolve()}",
                # as_uri, because a Windows path pasted after file:// is not one.
                path.with_suffix(".html").resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.SubprocessError, OSError:
        return False
    return path.with_suffix(".png").exists()


def load_model(target: str):
    """Import `module:callable` and call it, returning the Part to render."""
    module_name, _, attribute = target.partition(":")
    if not module_name or not attribute:
        raise SystemExit(f"--model must look like module:callable, got {target!r}")
    module = importlib.import_module(module_name)
    try:
        factory = getattr(module, attribute)
    except AttributeError:
        raise SystemExit(f"{module_name} has no {attribute!r}") from None
    return factory()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"module:callable to render (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("preview"), help="output directory (default: preview/)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="render at full detail: don't set PREVIEW for the model",
    )
    args = parser.parse_args()

    if not args.full:
        os.environ[PREVIEW_ENV] = "1"
    part = load_model(args.model)

    size = part.bounding_box().size
    caption = (
        f"{size.X:.0f} x {size.Y:.1f} x {size.Z:.1f}mm, {part.volume / 1000:.1f}cm3"
        f"{'' if args.full else '  (preview detail)'}"
    )

    print(caption)
    args.out.mkdir(parents=True, exist_ok=True)
    geometry = mesh(part)
    chromium = find_chromium()
    for view in VIEWS:
        view = fit(view, geometry)
        path = args.out / f"{view.name}.svg"
        count = render(geometry, view, path, caption=caption)
        drawn = rasterise(chromium, view, path) if chromium else False
        print(f"{path}  {count} triangles{'  + png' if drawn else ''}")
    if not chromium:
        print("no chromium found; wrote SVG only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
