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
class Planking:
    """Grooves down the outside of the hull, one at each plank seam.

    Cut into the section outlines rather than subtracted afterwards: the hull is
    already a loft through those outlines, so a seam costs three vertices and no
    boolean. The inside is left smooth, so the wall is thinner by `depth` at a
    seam and nowhere else.

    The groove is a sawtooth, not a symmetric V, because the hull prints
    bottom-down and a symmetric V does not survive that. Its upper facet faces
    downward at roughly atan(depth / half-width) away from the side -- and the
    side is already flared some 20 degrees off vertical, so the two add up and
    a 0.35 x 0.8 V put 4.8% of the hull past 45 degrees of overhang. Going in
    sharply over `lip` and back out along a ramp keeps the downward-facing facet
    inside `max_overhang`, with the steep facet pointing up where nothing has to
    bridge it. The ramp is worked out per station from the local flare.

    `count` is planks per side, chine to rail. `depth` and `lip` are in
    millimetres of the finished model; `max_overhang` is degrees from vertical.

    The default of 30 is deliberately under the 45 a printer will take, because
    the ramp is sized from the section flare alone and that under-predicts the
    real tilt near the ends. Measured on the finished solid, 45 leaves 2.4% of
    the hull past 45 degrees and 30 leaves none -- the same as no planking at
    all.
    """

    count: int = 6
    depth: float = 0.25
    lip: float = 0.20
    max_overhang: float = 30.0


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
    # How far the deck sits below the rail, in millimetres of the finished
    # model, over every stretch the open spans leave over. The hull's sides
    # carry on above it as bulwarks, so this is the bulwark's height -- and the
    # deck parallels the sheer, rising toward bow and stern with it. None fills
    # the decked stretches to the rail instead.
    bulwark: float | None = None
    # Plank seams down the outside. None leaves the sides smooth.
    planking: Planking | None = None

    @property
    def deck_open(self) -> bool:
        return self.wall > 0.0


def _station_positions(x0: float, x1: float, count: int) -> np.ndarray:
    """Cosine-spaced stations: dense at the ends, sparse amidships."""
    t = np.linspace(0.0, 1.0, count)
    return x0 + (x1 - x0) * (1.0 - np.cos(t * np.pi)) / 2.0


def _seam_points(
    y_chine: float,
    z_chine: float,
    y_sheer: float,
    z_sheer: float,
    planking: Planking,
    factor: float,
) -> list[tuple[float, float]]:
    """Points along the side that cut a groove at each plank seam.

    Three points a seam: on the surface, in by `depth` over a short lip, then
    back out along a ramp. Going out rather than in is the facet that ends up
    facing downward, so it is the one given the gentle angle; the lip faces up
    and can be as abrupt as it likes.

    Seams whose groove would not fit between the chine and the rail are skipped,
    which is what keeps the grooves off both.
    """
    run = y_sheer - y_chine
    rise = z_sheer - z_chine
    length = float(np.hypot(run, rise))
    if length <= 0.0 or planking.count < 2:
        return []

    # Inward normal of the side: toward the centreline and up.
    normal_y, normal_z = -rise / length, run / length
    depth = planking.depth / factor

    # The downward-facing facet starts from however far the side already leans,
    # so only the rest of the budget is left for the ramp itself. This is the
    # flare in the section plane; near the bow and stern the surface also tilts
    # along its length, but that tilt turns the normal toward the horizontal
    # rather than further down, so ignoring it is the conservative way round.
    flare = np.degrees(np.arctan2(abs(run), abs(rise)))
    spare = planking.max_overhang - flare
    if spare <= 1.0:
        # Already at the limit: a groove here would overhang however it is cut,
        # so leave this stretch smooth rather than pretend otherwise.
        return []
    ramp_along = (depth / float(np.tan(np.radians(spare)))) / length
    lip = (planking.lip / factor) / length

    points: list[tuple[float, float]] = []
    for seam in range(1, planking.count):
        middle = seam / planking.count
        corners = ((-lip, 0.0), (0.0, depth), (ramp_along, 0.0))
        if not all(0.0 < middle + offset < 1.0 for offset, _ in corners):
            continue
        for offset, inset in corners:
            along = middle + offset
            points.append(
                (
                    y_chine + run * along + normal_y * inset,
                    z_chine + rise * along + normal_z * inset,
                )
            )
    return points


def _section(lines: HullLines, x: float, planking: Planking | None = None, factor: float = 1.0):
    """One transverse section at station `x`, as a planar face.

    Centreline to chine is flat -- that is the bottom panel -- then out and up to
    the rail, by way of any plank seams. The top edge closes the section across
    what will become the deck; the hollowing step removes it.
    """
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)

    if y_chine <= 1e-6 or y_sheer < y_chine or z_sheer <= z_chine:
        return None

    side = (
        _seam_points(y_chine, z_chine, y_sheer, z_sheer, planking, factor)
        if planking is not None
        else []
    )
    starboard = [(y_chine, z_chine), *side, (y_sheer, z_sheer)]
    points = [(x, -y, z) for y, z in reversed(starboard)] + [(x, y, z) for y, z in starboard]
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
    bulwark: float | None,
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

    if bulwark is not None:
        if bulwark <= 0.0:
            raise ValueError(f"bulwark height must be positive, got {bulwark}")
        drop = bulwark / factor

        def deck_height(x: float) -> float:
            # A fixed drop below the rail, so the deck parallels the sheer
            # rather than the bottom. Measuring it as a fraction of the local
            # depth instead made the forecastle climb faster than the sheer,
            # because the forefoot sweeps up under it.
            return lines.sheer_height.value(x) - drop

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

    factor = spec.length / lines.length
    faces = [
        f
        for f in (_section(lines, float(x), spec.planking, factor) for x in stations)
        if f is not None
    ]
    if len(faces) < 2:
        raise RuntimeError("not enough valid stations to loft the hull")
    hull = loft(faces)

    if spec.deck_open:
        # Work in source units so the model is scaled exactly once, at the end.
        factor = spec.length / lines.length
        hull = _hollow(
            hull, lines, stations, spec.wall / factor, spec.open_spans, spec.bulwark, factor
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
