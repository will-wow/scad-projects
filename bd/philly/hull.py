"""Build the Philadelphia's hull as a hollow, printable solid.

The hull is a hard-chine scow: a flat bottom, a hard corner at the chine, and
flared sides up to the sheer. That means every transverse section is a simple
trapezoid -- centreline to chine along the flat bottom, then straight out and up
to the rail -- so the whole hull is a loft through those trapezoids rather than
anything needing compound-curved surfaces.

Hollowing lofts a second, inset set of sections and subtracts them. OCCT's
thick-solid operation is the obvious alternative and was used here first, but
it costs about 9 seconds against 0.6 for this -- 94% of the build -- for the
same 2.01mm wall. It also has to be told which face to leave open, and picking
that face is its own bug: the deck is not reliably the highest one. Insetting
the sections opens the top by construction, so there is no face to choose.

Getting the inset right is the whole trick. Shifting a section's rail straight
up to clear the deck also pushes the flared side outward, which measures 2.8mm
of wall for a 2mm request; the side has to move perpendicular to itself, and
the new chine corner is where the offset side and offset floor intersect.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import Part, Polyline, Vector, loft, make_face, scale

import lines as hull_lines
from lines import HullLines

# The scan's own baseline is the lowest point of the keel, so heights are already
# measured from the bottom of the boat.


@dataclass(frozen=True)
class OpenSpan:
    """A stretch of the hull that is hollowed out, as fractions of the length.

    The real boat is decked over forward and aft with an open waist between, so
    the hull is not one continuous cavity. Everything outside these spans is
    left solid from the bottom up -- which is not how the boat was built, where
    the decked ends covered storage and sleeping space, but is what prints.

    `floor` raises this span's bottom, in millimetres of the finished model, for
    a well that should not go all the way down. Zero hollows to the inside of
    the hull's bottom.
    """

    start: float
    end: float
    floor: float = 0.0


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
    # Which stretches are open to the bottom. The default is one span end to
    # end: a hull open for its whole length.
    open_spans: tuple[OpenSpan, ...] = (OpenSpan(0.0, 1.0),)
    # Where the deck sits over every other stretch, as a fraction of the local
    # depth from the inside of the bottom to the rail. The hull's sides carry on
    # above it as bulwarks. None fills the decked stretches to the rail instead.
    deck: float | None = None

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


def _assert_open(
    hull: Part,
    lines: HullLines,
    wall: float,
    spans: tuple[OpenSpan, ...],
    x0: float,
    x1: float,
    first: float,
    last: float,
) -> None:
    """Confirm the open spans really are open, by probing for air below the rail.

    Every silent failure this code has had looked fine from outside: a solid
    hull OCCT declined to hollow, a deck left skinned because the wrong face was
    opened. Volume alone does not separate those from a good build, so this
    looks inside -- and only inside the spans that are meant to be open, since
    a decked stretch is supposed to have material there.
    """
    for span in spans:
        start = max(first, x0 + (x1 - x0) * span.start)
        end = min(last, x0 + (x1 - x0) * span.end)
        if end - start <= 1e-6:
            continue
        x = 0.5 * (start + end)
        # Sample inside the band the deck skin would occupy: from the rail down
        # by one wall thickness. Below that band there is air either way, which
        # is a check that always passes -- as an earlier version of this did.
        z = lines.sheer_height.value(x) - 0.5 * wall
        if hull.is_inside(Vector(x, 0.0, z)):
            raise RuntimeError(f"the span {span.start:.2f}..{span.end:.2f} is still decked over")


def _inner_section(lines: HullLines, x: float, wall: float, floor_z: float | None = None):
    """The cavity's section at station `x`: the outer one, offset inward by `wall`.

    Offsetting a trapezoid is not the same as shrinking it. The floor moves up by
    `wall`, but the flared side has to move perpendicular to itself, and the new
    chine corner is where those two offset lines meet -- not either endpoint
    moved by a fixed amount. Getting this wrong is what made an earlier version
    measure 2.8mm of side wall for a 2mm request.

    The rail is carried one wall above the deck so the subtraction opens the top.
    `floor_z` places the cavity's bottom outright, which is how a deck is made:
    put the floor part-way up and the hull's own sides carry on past it as
    bulwarks. It is never allowed below the inside of the hull's bottom.

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

    # Where the offset side meets the offset floor.
    bottom = z_chine + wall
    floor_z = bottom if floor_z is None else max(floor_z, bottom)
    s_floor = (floor_z - base_z) * length / rise
    floor_y = base_y + s_floor * run / length

    # Carry the same line up past the rail.
    s_top = (z_sheer + wall - base_z) * length / rise
    top_y = base_y + s_top * run / length
    top_z = z_sheer + wall

    if floor_y <= 1e-6 or top_y < floor_y or top_z <= floor_z:
        return None

    points = [
        (x, -top_y, top_z),
        (x, -floor_y, floor_z),
        (x, floor_y, floor_z),
        (x, top_y, top_z),
    ]
    return make_face(Polyline(*points, close=True))


def _cavity_span(lines: HullLines, wall: float, x0: float, x1: float) -> tuple[float, float]:
    """The first and last station that can hold a cavity, found by bisection.

    Near the stem and the transom the hull is narrower than two walls, so the
    cavity has to stop and leave those ends solid. Letting that happen wherever
    the stations happen to land makes the solid plugs an artefact of sampling:
    the bow plug measured anywhere from 812mm to 1566mm depending only on the
    station count, which silently changed print weight along with it. Solving
    for the boundary instead pins the plugs to the geometry, so `stations`
    controls smoothness and nothing else.
    """

    def holds_cavity(x: float) -> bool:
        return _inner_section(lines, x, wall) is not None

    middle = 0.5 * (x0 + x1)
    if not holds_cavity(middle):
        raise RuntimeError("wall is too thick to hollow this hull amidships")

    def boundary(solid_end: float) -> float:
        """Bisect between an end that can't hold a cavity and the middle that can."""
        low, high = solid_end, middle
        if holds_cavity(low):
            return low
        for _ in range(40):  # ~1e-12 of the length; far below any tolerance here
            mid = 0.5 * (low + high)
            low, high = (low, mid) if holds_cavity(mid) else (mid, high)
        return high

    return boundary(x0), boundary(x1)


def _merge(spans: tuple[OpenSpan, ...]) -> list[tuple[float, float]]:
    """The open spans as sorted, non-overlapping fraction ranges."""
    merged: list[tuple[float, float]] = []
    for start, end in sorted((s.start, s.end) for s in spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _decked(spans: tuple[OpenSpan, ...]) -> list[tuple[float, float]]:
    """Everything the open spans leave over: the stretches that carry a deck."""
    covered = _merge(spans)
    stretches: list[tuple[float, float]] = []
    edge = 0.0
    for start, end in covered:
        if start > edge:
            stretches.append((edge, start))
        edge = end
    if edge < 1.0:
        stretches.append((edge, 1.0))
    return stretches


def _cut(
    hull: Part,
    lines: HullLines,
    stations: np.ndarray,
    wall: float,
    bounds: tuple[float, float],
    floor_z,
) -> Part:
    """Subtract one cavity between `bounds`, with its floor placed by `floor_z`.

    `floor_z` takes a station and returns the height for the cavity's bottom
    there, or None for "all the way down". The loft caps its own ends, so each
    cut leaves a bulkhead at its boundary.
    """
    start, end = bounds
    if end - start <= 1e-6:
        return hull
    inside = [float(x) for x in stations if start < x < end]
    faces = [
        f
        for f in (_inner_section(lines, x, wall, floor_z(x)) for x in (start, *inside, end))
        if f is not None
    ]
    if len(faces) < 2:
        return hull
    return _as_part(hull - loft(faces), "cavity subtraction")


def _hollow(
    hull: Part,
    lines: HullLines,
    stations: np.ndarray,
    wall: float,
    spec_spans: tuple[OpenSpan, ...],
    deck: float | None,
    factor: float,
) -> Part:
    """Hollow the open spans to the bottom, and the decked stretches to the deck."""
    x0, x1 = float(stations[0]), float(stations[-1])
    # Where the hull is wide enough to hold a cavity at all; a span reaching
    # past that is clipped rather than refused, so "open to the bow" means as
    # far forward as the stem allows.
    first, last = _cavity_span(lines, wall, x0, x1)

    def to_source(fraction: float) -> float:
        return x0 + (x1 - x0) * fraction

    def clip(a: float, b: float) -> tuple[float, float]:
        return max(first, to_source(a)), min(last, to_source(b))

    for span in spec_spans:
        if not 0.0 <= span.start < span.end <= 1.0:
            raise ValueError(f"open span {span.start}..{span.end} is not an increasing 0..1 range")

    hollowed = hull
    for span in spec_spans:
        lift = span.floor / factor
        hollowed = _cut(
            hollowed,
            lines,
            stations,
            wall,
            clip(span.start, span.end),
            lambda x, lift=lift: lines.chine_height.value(x) + wall + lift,
        )

    if deck is not None:
        if not 0.0 < deck < 1.0:
            raise ValueError(f"deck must sit between the bottom and the rail, got {deck}")

        def deck_height(x: float) -> float:
            bottom = lines.chine_height.value(x) + wall
            return bottom + deck * (lines.sheer_height.value(x) - bottom)

        for stretch in _decked(spec_spans):
            hollowed = _cut(hollowed, lines, stations, wall, clip(*stretch), deck_height)

    if hollowed.volume >= 0.95 * hull.volume:
        raise RuntimeError("hollowing removed nothing -- check the wall thickness and open spans")
    _assert_open(hollowed, lines, wall, spec_spans, x0, x1, first, last)
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
        factor = spec.length / lines.length
        hull = _hollow(
            hull, lines, stations, spec.wall / factor, spec.open_spans, spec.deck, factor
        )

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
