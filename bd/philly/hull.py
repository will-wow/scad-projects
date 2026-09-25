"""Build the Philadelphia's hull as a hollow, printable solid.

See HOW-IT-WORKS.md for a tour of the whole thing; this is the reasoning that
belongs next to the code.

The hull is a hard-chine scow: a flat bottom, a hard corner at the chine, and
sides rising to the sheer. Every transverse section is therefore a closed
outline that a few numbers describe -- centreline to chine along the flat
bottom, then out and up to the rail, bowed by `Bulge` or dead straight without
it -- so the whole hull is a loft through those outlines rather than anything
needing compound-curved surfaces.

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
from build123d import Compound, Part, Polyline, Vector, loft, make_face, scale

import lines as hull_lines
from lines import HullLines

# The scan's own baseline is the lowest point of the keel, so heights are already
# measured from the bottom of the boat.


@dataclass(frozen=True)
class Deck:
    """A platform across the hull, and the stretch of length it covers.

    The boat is decked in three places -- a forecastle, a middle platform and
    the quarterdeck -- each at its own height, with the bilge open between
    them. A deck is modelled as solid from the bottom up to its height, which
    is not how the boat was built (the decked ends covered storage and sleeping
    space) but is what prints; the hull's sides carry on past it as bulwarks.

    Anywhere no deck covers is hollowed right down to the inside of the bottom.
    A shallow well is therefore just a low deck -- both are a cavity with its
    floor part-way up, so one idea covers both.
    """

    start: float
    """where the deck begins, as a fraction of the overall length"""
    end: float
    """where it ends, as a fraction of the overall length"""
    height: float
    """the platform's height above the bottom, as a fraction of the hull's depth"""

    def __post_init__(self) -> None:
        if not 0.0 <= self.start < self.end <= 1.0:
            raise ValueError(f"deck {self.start}..{self.end} is not an increasing 0..1 range")
        if not 0.0 < self.height <= 1.0:
            raise ValueError(f"deck height must lie in 0..1, got {self.height}")


@dataclass(frozen=True)
class Bulge:
    """
    Bow the sides outward between the chine and the rail.
    Simple convex swell, good enough for this boat without tumblehome.
    """

    amount: float = 0.06
    """the height of the swell as a fraction of the side's own slant height"""
    peak: float = 0.45
    """where along the side the swell is widest"""

    def __post_init__(self) -> None:
        if not 0.0 < self.peak < 1.0:
            raise ValueError(f"bulge peak must lie strictly inside 0..1, got {self.peak}")

    def at(self, t: float) -> float:
        """The swell's shape: zero at both ends, 1 at `peak`, curve between."""
        t = min(max(t, 0.0), 1.0)
        return float(np.sin(np.pi * t ** (np.log(0.5) / np.log(self.peak))))


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
    # The platforms, each with its own height. Everything they leave over is
    # hollowed to the bottom, so the default -- none at all -- is a hull open
    # for its whole length.
    decks: tuple[Deck, ...] = ()
    # How far the sides bow outward between chine and rail. None keeps them the
    # dead-straight panels the lines plan alone gives.
    bulge: Bulge | None = None

    @property
    def deck_open(self) -> bool:
        return self.wall > 0.0


def _station_positions(x0: float, x1: float, count: int) -> np.ndarray:
    """Cosine-spaced stations: dense at the ends, sparse amidships."""
    t = np.linspace(0.0, 1.0, count)
    return x0 + (x1 - x0) * (1.0 - np.cos(t * np.pi)) / 2.0


# Points across the side when it is bowed. The swell is one smooth hump, so it
# does not take many to read as a curve once tessellated.
SIDE_SAMPLES = 11


def _side_profile(
    y_chine: float,
    z_chine: float,
    y_sheer: float,
    z_sheer: float,
    bulge: Bulge | None,
) -> list[tuple[float, float]]:
    """The starboard side from chine to rail, as (y, z) points.

    A straight side is just its two ends. A bowed one is sampled across, each
    point carried out of the chord horizontally -- horizontally rather than
    along the surface normal so that it keeps its height, which is what lets the
    cavity follow the same swell without a real offset. See `Bulge`.

    Every station returns the same number of points. That is worth keeping:
    lofting between sections whose vertices do not correspond makes OCCT build a
    common parameterisation, which cost sixty times as much as lofting between
    matched ones.
    """

    # if no bulge, the side profile is a straight line
    if bulge is None:
        return [(y_chine, z_chine), (y_sheer, z_sheer)]
    run = y_sheer - y_chine
    rise = z_sheer - z_chine
    # overall distance to sheer
    chord = float(np.hypot(run, rise))
    if chord <= 0.0:
        return [(y_chine, z_chine), (y_sheer, z_sheer)]

    points: list[tuple[float, float]] = []
    for v in np.linspace(0.0, 1.0, SIDE_SAMPLES):
        t = float(v)
        points.append((y_chine + run * t + bulge.at(t) * bulge.amount * chord, z_chine + rise * t))
    return points


def _section(lines: HullLines, x: float, bulge: Bulge | None = None):
    """One transverse section at station `x`, as a planar face.

    Centreline to chine is flat -- that is the bottom panel -- then out and up to
    the rail, by way of any swell. The top edge closes the section across what
    will become the deck; the hollowing step removes it.
    """
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)

    if y_chine <= 1e-6 or y_sheer < y_chine or z_sheer <= z_chine:
        return None

    starboard = _side_profile(y_chine, z_chine, y_sheer, z_sheer, bulge)
    points = [(x, -y, z) for y, z in reversed(starboard)] + [(x, y, z) for y, z in starboard]
    return make_face(Polyline(*points, close=True))


# How much of the result a boolean may leave behind as loose fragments before
# it counts as having cut the hull apart rather than merely shaved it.
DEBRIS_FRACTION = 1e-4


def _as_part(shape: object, what: str) -> Part:
    """Remove any extra slivers left from a boolean operation."""

    # build123d's operators are generic over shape kinds; ensure this is a solid.
    if not isinstance(shape, Compound):
        raise RuntimeError(f"{what} produced a {type(shape).__name__}, not a solid")

    solids = shape.solids()
    if not solids:
        raise RuntimeError(f"{what} produced nothing solid")

    # if there is one solid, we're good.
    if len(solids) == 1 and isinstance(shape, Part):
        return shape

    # checking for a solid broken into pieces
    largest = max(solids, key=lambda s: s.volume)
    # Smaller pieces
    debris = sum(s.volume for s in solids if s is not largest)
    # Make sure the smaller pieces are a small fraction of the solid
    if debris > DEBRIS_FRACTION * largest.volume:
        raise RuntimeError(
            f"{what} split the hull into {len(solids)} pieces; "
            f"{debris / largest.volume:.1%} of it broke away"
        )
    # discard the small pieces.
    return Part(largest.wrapped)


def _assert_open(
    hull: Part,
    lines: HullLines,
    wall: float,
    spans: list[tuple[float, float]],
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
    for low, high in spans:
        start = max(first, x0 + (x1 - x0) * low)
        end = min(last, x0 + (x1 - x0) * high)
        if end - start <= 1e-6:
            continue
        x = 0.5 * (start + end)
        # Sample inside the band the deck skin would occupy: from the rail down
        # by one wall thickness. Below that band there is air either way, which
        # is a check that always passes -- as an earlier version of this did.
        z = lines.sheer_height.value(x) - 0.5 * wall
        if hull.is_inside(Vector(x, 0.0, z)):
            raise RuntimeError(f"the span {low:.2f}..{high:.2f} is still decked over")


def _inner_section(
    lines: HullLines,
    x: float,
    wall: float,
    floor_z: float | None = None,
    bulge: Bulge | None = None,
):
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

    A bowed side is followed by displacing the cavity's side by the same amount
    at the same height, so the two surfaces move together and the wall survives
    without a genuine polyline offset. The two curves are then a constant
    distance apart measured along the chord's normal; perpendicular to the
    surface itself that is short by cos(local lean), which at the default swell
    is under 2% of the wall.

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

    starboard = [(floor_y, floor_z), (top_y, top_z)]
    if bulge is not None:
        chord = float(np.hypot(run, rise))
        curved: list[tuple[float, float]] = []
        for s_along in np.linspace(0.0, 1.0, SIDE_SAMPLES):
            y = floor_y + s_along * (top_y - floor_y)
            z = floor_z + s_along * (top_z - floor_z)
            # Match the outer surface at this height, not at this fraction of
            # the cavity: the cavity is cut short at the bottom by the floor and
            # runs past the rail at the top, so its own parameter is not the
            # outer side's.
            swell = bulge.at((z - z_chine) / rise) * bulge.amount * chord
            curved.append((y + swell, z))
        starboard = curved

    points = [(x, -y, z) for y, z in reversed(starboard)] + [(x, y, z) for y, z in starboard]
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


def _ordered(decks: tuple[Deck, ...]) -> list[Deck]:
    """The decks bow to stern, refusing any that overlap.

    Overlapping decks are not merged the way overlapping open spans once were:
    two decks covering the same stretch at different heights have no sensible
    answer, and picking one quietly would be worse than saying so.
    """
    ordered = sorted(decks, key=lambda d: d.start)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.start < earlier.end:
            raise ValueError(
                f"decks {earlier.start}..{earlier.end} and {later.start}..{later.end} overlap"
            )
    return ordered


def _open(decks: list[Deck]) -> list[tuple[float, float]]:
    """Everything the decks leave over: the stretches hollowed to the bottom."""
    stretches: list[tuple[float, float]] = []
    edge = 0.0
    for deck in decks:
        if deck.start > edge:
            stretches.append((edge, deck.start))
        edge = deck.end
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
    bulge: Bulge | None = None,
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
        for f in (_inner_section(lines, x, wall, floor_z(x), bulge) for x in (start, *inside, end))
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
    decks: tuple[Deck, ...],
    bulge: Bulge | None = None,
) -> Part:
    """Hollow the undecked stretches to the bottom, and each deck to its height."""
    x0, x1 = float(stations[0]), float(stations[-1])
    # Where the hull is wide enough to hold a cavity at all; a stretch reaching
    # past that is clipped rather than refused, so "open to the bow" means as
    # far forward as the stem allows.
    first, last = _cavity_span(lines, wall, x0, x1)

    def clip(a: float, b: float) -> tuple[float, float]:
        return max(first, x0 + (x1 - x0) * a), min(last, x0 + (x1 - x0) * b)

    ordered = _ordered(decks)
    open_stretches = _open(ordered)

    hollowed = hull
    for stretch in open_stretches:
        hollowed = _cut(
            hollowed,
            lines,
            stations,
            wall,
            clip(*stretch),
            lambda x: lines.chine_height.value(x) + wall,
            bulge,
        )

    for deck in ordered:
        # Flat, and measured from the bottom rather than down from the rail:
        # the three platforms sit at three different heights, so each one is
        # its own number instead of a single drop below a sheer they no longer
        # share.
        floor = deck.height * lines.depth
        hollowed = _cut(
            hollowed,
            lines,
            stations,
            wall,
            clip(deck.start, deck.end),
            lambda x, floor=floor: floor,
            bulge,
        )

    if hollowed.volume >= 0.95 * hull.volume:
        raise RuntimeError("hollowing removed nothing -- check the wall thickness and the decks")
    _assert_open(hollowed, lines, wall, open_stretches, x0, x1, first, last)
    return hollowed


def build(spec: HullSpec | None = None, lines: HullLines | None = None) -> Part:
    """Loft the outer hull, hollow it, and scale to the target length."""
    spec = spec or HullSpec()
    lines = lines or hull_lines.load()

    x0, x1 = lines.sheer_half_width.span
    stations = _station_positions(x0, x1, spec.stations)

    # Everything is built in the source's own millimetres and scaled exactly
    # once, at the end; `factor` converts the spec's finished sizes into them.
    factor = spec.length / lines.length

    faces = [f for f in (_section(lines, float(x), spec.bulge) for x in stations) if f is not None]
    if len(faces) < 2:
        raise RuntimeError("not enough valid stations to loft the hull")
    hull = loft(faces)

    if spec.deck_open:
        hull = _hollow(
            hull,
            lines,
            stations,
            spec.wall / factor,
            spec.decks,
            spec.bulge,
        )

    return _as_part(scale(hull, factor), "scaling")


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
