"""Build the Philadelphia's hull as a hollow, printable solid.

The hull is a hard-chine scow: a flat bottom, a hard corner at the chine, and
flared sides up to the sheer. That means every transverse section is a simple
trapezoid -- centreline to chine along the flat bottom, then straight out and up
to the rail -- so the whole hull is a loft through those trapezoids rather than
anything needing compound-curved surfaces.

Hollowing uses OCCT's thick-solid operation with the deck face removed, which
gives a wall of exactly the requested thickness measured perpendicular to each
surface. Insetting the section outlines by hand instead looks simpler but is
wrong on a flared hull: shifting a section's rail upward to open the deck also
pushes the inclined side outward, which measured ~2.8mm of wall for a 2mm
request. Let OCCT do the offset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import Axis, Part, Polyline, loft, make_face, offset, scale

import lines as hull_lines
from lines import HullLines

# The scan's own baseline is the lowest point of the keel, so heights are already
# measured from the bottom of the boat.


@dataclass(frozen=True)
class HullSpec:
    """What to build. Lengths in millimetres of the finished, printed model."""

    # Overall length of the printed hull. The source data is 1:1 real-world mm
    # (a 16.4m boat), so this is the toy scale-down.
    length: float = 300.0
    # Wall thickness of the hollow hull.
    wall: float = 2.0
    # Transverse sections in the loft. Cosine-spaced, so they bunch up toward the
    # bow and stern where the curves bend hardest.
    stations: int = 48

    @property
    def deck_open(self) -> bool:
        return self.wall > 0.0


def _station_positions(x0: float, x1: float, count: int) -> np.ndarray:
    """Cosine-spaced stations: dense at the ends, sparse amidships."""
    t = np.linspace(0.0, 1.0, count)
    return x0 + (x1 - x0) * (1.0 - np.cos(t * np.pi)) / 2.0


def _section(lines: HullLines, x: float):
    """One transverse trapezoid at station `x`, as a planar face.

    Centreline to chine is flat -- that is the bottom panel -- then straight out
    and up to the rail. The top edge closes the section across what will become
    the deck; the hollowing step removes it.
    """
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)

    if y_chine <= 1e-6 or y_sheer < y_chine or z_sheer <= z_chine:
        return None

    points = [
        (x, -y_sheer, z_sheer),
        (x, -y_chine, z_chine),
        (x, y_chine, z_chine),
        (x, y_sheer, z_sheer),
    ]
    return make_face(Polyline(*points, close=True))


def _as_part(shape: object, what: str) -> Part:
    """build123d's operators are generic over shape kinds; the hull is a solid.

    Anything else means the operation degenerated -- an empty result, or a shell
    where a solid was expected -- so say which step produced it.
    """
    if not isinstance(shape, Part):
        raise RuntimeError(f"{what} produced a {type(shape).__name__}, not a solid")
    return shape


def _inner_section(lines: HullLines, x: float, wall: float, margin: float):
    """The cavity's section at station `x`: the outer one, offset inward by `wall`.

    Offsetting a trapezoid is not the same as shrinking it. The floor moves up by
    `wall`, but the flared side has to move perpendicular to itself, and the new
    chine corner is where those two offset lines meet -- not either endpoint
    moved by a fixed amount. Getting this wrong is what made an earlier version
    measure 2.8mm of side wall for a 2mm request.

    The rail is carried `margin` above the deck so the subtraction opens the top.
    Returns None where the section is too small to hold a cavity, which leaves
    the stem and transom solid.
    """
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)

    rise = z_sheer - z_chine
    run = y_sheer - y_chine
    if rise <= 1e-9:
        return None
    length = float(np.hypot(rise, run))

    # Inward normal of the side, and the side's own direction.
    base_y = y_chine - wall * rise / length
    base_z = z_chine + wall * run / length

    # Where the offset side meets the offset floor (z = z_chine + wall).
    s_floor = wall * (length - run) / rise
    floor_y = base_y + s_floor * run / length
    floor_z = z_chine + wall

    # Carry the same line up past the rail.
    s_top = (z_sheer + margin - base_z) * length / rise
    top_y = base_y + s_top * run / length
    top_z = z_sheer + margin

    if floor_y <= 1e-6 or top_y < floor_y or top_z <= floor_z:
        return None

    points = [
        (x, -top_y, top_z),
        (x, -floor_y, floor_z),
        (x, floor_y, floor_z),
        (x, top_y, top_z),
    ]
    return make_face(Polyline(*points, close=True))


def _hollow(hull: Part, lines: HullLines, stations: np.ndarray, wall: float) -> Part:
    """Hollow the hull, leaving the deck open.

    OCCT's thick-solid is the first choice: it offsets every face perpendicular
    to itself, so the wall is exactly `wall` everywhere by construction. But it
    fails on this shape for some wall thicknesses -- and it fails *silently*,
    handing back the solid unchanged, valid, with no exception. A solid hull
    looks fine in the viewer and only announces itself as hours of print time,
    so the result is checked rather than trusted, and a hand-built inner loft
    takes over when the check fails.
    """
    deck = hull.faces().sort_by(Axis.Z)[-1]
    try:
        thick = offset(hull, -wall, openings=deck)
    except Exception:  # noqa: BLE001  (any OCCT failure just means: use the fallback)
        thick = None
    if thick is not None and thick.volume < 0.95 * hull.volume:
        return _as_part(thick, "thick-solid hollowing")

    inner = [
        f for f in (_inner_section(lines, float(x), wall, wall) for x in stations) if f is not None
    ]
    if len(inner) < 2:
        raise RuntimeError("wall is too thick to hollow this hull at any station")
    hollowed = _as_part(hull - loft(inner), "cavity subtraction")
    if hollowed.volume >= 0.95 * hull.volume:
        raise RuntimeError("hollowing removed nothing -- check the wall thickness")
    return hollowed


def build(spec: HullSpec | None = None, lines: HullLines | None = None) -> Part:
    """Loft the outer hull, hollow it, and scale to the target length."""
    spec = spec or HullSpec()
    lines = lines or hull_lines.load()

    x0, x1 = lines.sheer_half_width.span
    stations = _station_positions(x0, x1, spec.stations)

    faces = [f for f in (_section(lines, float(x)) for x in stations) if f is not None]
    if len(faces) < 2:
        raise RuntimeError("not enough valid stations to loft the hull")
    hull = loft(faces)

    if spec.deck_open:
        # Work in source units so the model is scaled exactly once, at the end.
        hull = _hollow(hull, lines, stations, spec.wall / (spec.length / lines.length))

    return _as_part(scale(hull, spec.length / lines.length), "scaling")


if __name__ == "__main__":
    spec = HullSpec()
    lines = hull_lines.load()
    part = build(spec, lines)
    bbox = part.bounding_box()
    print(f"source LOA {lines.length:.0f}mm -> printed {spec.length:.0f}mm")
    print(f"  scale     1:{lines.length / spec.length:.0f}")
    print(f"  bbox      {bbox.size.X:.1f} x {bbox.size.Y:.1f} x {bbox.size.Z:.1f} mm")
    print(f"  volume    {part.volume / 1000:.1f} cm^3")
    print(f"  watertight{'' if part.is_valid else ' NO -- invalid solid'}")
