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
import shutil
import subprocess
from dataclasses import dataclass
from glob import glob
from pathlib import Path

import numpy as np
from build123d import Part

from hull import HullSpec, build

# Tessellation tolerance in final millimetres: finer than the eye at this size.
MESH_TOLERANCE = 0.08


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
    View("hull", 322.0, 26.0, 1100, 420, "three-quarter"),
    View("hull_plan", 270.0, 88.0, 1100, 340, "plan - bow at left"),
    View("hull_side", 270.0, 0.0, 1100, 280, "profile - sheer and flat bottom"),
)

LIGHT = np.array([0.4, -0.5, 0.75])


def _camera(azimuth: float, elevation: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Right, up and forward vectors for a camera aimed at the origin."""
    az, el = np.radians(azimuth), np.radians(elevation)
    forward = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    right = np.cross(np.array([0.0, 0.0, 1.0]), forward)
    right /= np.linalg.norm(right)
    return right, np.cross(forward, right), forward


def render(part: Part, view: View, path: Path, *, caption: str = "") -> int:
    """Write `part` to `path` as a flat-shaded SVG. Returns the triangle count."""
    vertices, triangles = part.tessellate(MESH_TOLERANCE)
    points = np.array([[v.X, v.Y, v.Z] for v in vertices])
    faces = np.array(triangles)

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
    shade = np.abs(normals @ (LIGHT / np.linalg.norm(LIGHT))) * 0.75 + 0.25

    low, high = corners.reshape(-1, 2).min(axis=0), corners.reshape(-1, 2).max(axis=0)
    pad = 30
    span = np.maximum(high - low, 1e-9)
    scale = min((view.width - 2 * pad) / span[0], (view.height - 2 * pad - 20) / span[1])
    # SVG's Y axis points down, so flip it.
    flip = np.array([1.0, -1.0])
    offset = np.array([view.width / 2, view.height / 2]) - (low + high) / 2 * scale * flip

    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view.width}" '
        f'height="{view.height}" viewBox="0 0 {view.width} {view.height}">',
        f'<rect width="{view.width}" height="{view.height}" fill="#14181d"/>',
    ]
    for i in np.argsort(points[faces].mean(axis=1) @ forward)[::-1]:
        pixels = corners[i] * scale * flip + offset
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in pixels)
        level = shade[i]
        rgb = (int(150 * level + 30), int(115 * level + 24), int(78 * level + 16))
        body.append(f'<polygon points="{coords}" fill="rgb{rgb}"/>')
    text = " - ".join(p for p in (view.label, caption) if p)
    body.append(
        f'<text x="{pad}" y="{view.height - 14}" fill="#9aa4b2" '
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
    """Playwright's Chromium if it's installed, else whatever is on PATH."""
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
                f"--screenshot={path.with_suffix('.png')}",
                f"file://{path.with_suffix('.html').resolve()}",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.SubprocessError, OSError:
        return False
    return path.with_suffix(".png").exists()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("preview"), help="output directory (default: preview/)"
    )
    parser.add_argument(
        "--length", type=float, default=HullSpec().length, help="printed length, mm"
    )
    parser.add_argument("--wall", type=float, default=HullSpec().wall, help="wall thickness, mm")
    parser.add_argument(
        "--stations", type=int, default=HullSpec().stations, help="sections in the loft"
    )
    args = parser.parse_args()

    part = build(HullSpec(length=args.length, wall=args.wall, stations=args.stations))
    size = part.bounding_box().size
    caption = (
        f"{size.X:.0f} x {size.Y:.1f} x {size.Z:.1f}mm, "
        f"{args.wall:g}mm wall, {part.volume / 1000:.1f}cm3"
    )

    print(caption)
    args.out.mkdir(parents=True, exist_ok=True)
    chromium = find_chromium()
    for view in VIEWS:
        path = args.out / f"{view.name}.svg"
        count = render(part, view, path, caption=caption)
        drawn = rasterise(chromium, view, path) if chromium else False
        print(f"{path}  {count} triangles{'  + png' if drawn else ''}")
    if not chromium:
        print("no chromium found; wrote SVG only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
