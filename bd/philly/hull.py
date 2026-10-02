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

import math
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from build123d import (
    Box,
    Compound,
    Part,
    Polyline,
    Pos,
    Vector,
    extrude,
    loft,
    make_face,
    scale,
)

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
    plank: float | None = None
    """the width of its planks in millimetres of the finished model, or None for a plain deck"""
    tab: float = 0.0
    """how far its aft corners run on along each side past its end, in
    millimetres of the finished model, or 0 for a square end; see `_tabs`"""

    def __post_init__(self) -> None:
        if not 0.0 <= self.start < self.end <= 1.0:
            raise ValueError(f"deck {self.start}..{self.end} is not an increasing 0..1 range")
        if not 0.0 < self.height <= 1.0:
            raise ValueError(f"deck height must lie in 0..1, got {self.height}")
        if self.plank is not None and self.plank <= 0.0:
            raise ValueError(f"a plank must have some width, got {self.plank}")
        if self.tab < 0.0:
            raise ValueError(f"a deck's tab cannot be negative, got {self.tab}")


@dataclass(frozen=True)
class Seams:
    """The grooves between a deck's planks, in millimetres of the finished model.

    Planks run fore and aft, as the scan shows on every deck, so the seams are
    straight lines along the length. Shallow on purpose: a gun's carriage is
    checked for deck 0.3mm under each corner, and a seam there must not read
    as a hole.
    """

    width: float = 0.5
    depth: float = 0.2
    margin: float = 0.5
    """how far short of the inside of the hull each seam stops"""
    clearance: float = 1.0
    """the least anything standing on the deck may leave between its edge and a seam

    Any closer and the strip of deck between them is too thin for the mesher,
    which drops it: the export then has a hole in the deck. See `clear_of_seams`.
    """

    def __post_init__(self) -> None:
        if self.width <= 0.0 or self.margin < 0.0:
            raise ValueError("a seam needs some width, and cannot run into the side")
        if not 0.0 < self.depth < 0.3:
            raise ValueError(f"a seam must be shallower than 0.3mm, got {self.depth}")


@dataclass(frozen=True)
class Well:
    """The ceiling on the floor of every open stretch, in millimetres of the model.

    A well is not a deck -- its floor is found from the chine rather than
    declared -- but it grooves the same way, since the faired bottom is flat and
    so the floor is one height.
    """

    plank: float
    """the width of its planks"""
    clear: float
    """how far out from the centreline the innermost seam stands

    The floor is not bare: the keelson runs down the middle of it, and the
    mast's tube stands on it in the forward well. Both are fitted after the hull
    is built, so a seam has to keep `Seams.clearance` off them or the strip left
    between is too thin for the mesher. Inboard of this the floor reads as one
    wide plank with the keelson on it, which is what a ceiling looks like
    anyway.
    """

    def __post_init__(self) -> None:
        if self.plank <= 0.0:
            raise ValueError(f"a plank must have some width, got {self.plank}")
        if self.clear < 0.0:
            raise ValueError(
                f"the first seam cannot stand inboard of the centreline, got {self.clear}"
            )


def clear_of_seams(
    spec: HullSpec, deck: Deck, edges: tuple[float, ...], outboard: float = math.inf
) -> float:
    """How far to move something standing on `deck` so none of its edges is near a seam.

    `edges` are where its fore-and-aft edges stand, as distances from the
    centreline in millimetres of the finished model. The answer is the smallest
    move that keeps every one `Seams.clearance` from a seam, outboard first
    unless that is further than `outboard` allows, and 0 on a deck without
    seams.
    """
    if spec.seams is None or deck.plank is None:
        return 0.0
    plank = deck.plank
    keep = spec.seams.width / 2.0 + spec.seams.clearance

    def fouls(y: float) -> bool:
        seam = (np.floor(y / plank - 0.5) + 0.5) * plank
        return min(abs(y - seam), abs(y - seam - plank)) < keep

    for move in np.arange(0.0, plank, 0.01):
        for shift in (float(move), -float(move)):
            if shift > outboard:
                continue
            if not any(fouls(edge + shift) for edge in edges):
                return shift
    raise ValueError(f"nothing with edges at {edges} fits between the seams of a {plank}mm plank")


@dataclass(frozen=True)
class Knee:
    """An L-shaped knee against the inside of the side, standing on a deck.

    Only the ones between a platform's ends: the pairs at each end stand on its
    cross-beams and are placed from the deck's edges. See details.py.
    """

    station: float
    """along the length, as a fraction from the bow"""
    side: int
    """+1 to starboard, -1 to port"""

    def __post_init__(self) -> None:
        if self.side not in (-1, 1):
            raise ValueError(f"a knee stands to port or starboard, not {self.side}")
        if not 0.0 < self.station < 1.0:
            raise ValueError(f"the knee at {self.station} is off the boat")


@dataclass(frozen=True)
class Bench:
    """A bench along both sides, between two stations given as fractions from the bow."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.start < self.end <= 1.0:
            raise ValueError(f"bench {self.start}..{self.end} is not an increasing 0..1 range")


@dataclass(frozen=True)
class Bulge:
    """
    Bow the sides outward between the chine and the rail.
    Simple convex swell, good enough for this boat without tumbling home.
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
    # The grooves cut into any deck that has a plank width.
    seams: Seams | None = None
    # The same grooves on the floor of every open well, or None to leave them
    # bare. Not a plank width on its own: something stands on every well's
    # floor, so the innermost seam has to be placed clear of it.
    wells: Well | None = None
    # The boat's joinery, which details.py fits once the hull is built: knees on
    # the platforms, benches along the sides and the keelson showing in the wells.
    knees: tuple[Knee, ...] = ()
    benches: tuple[Bench, ...] = ()
    keelson: bool = False
    # The stem: one board bent round the bow in front of the planking. Without
    # it the planking ends in the flat face the lines leave for it.
    stem: bool = True

    @property
    def deck_open(self) -> bool:
        return self.wall > 0.0


@dataclass(frozen=True)
class Bow:
    """Where the flat bottom ends, and where the planking's sweep up from it ends.

    Both in the source's millimetres. Forward of `start` the bottom rises along
    `_sweep`, tangent to the flat and vertical at `tip`, reaching the rail there.
    """

    start: float
    """the first point of the chine's profile, where the flat bottom begins"""
    tip: float
    """where the planking closes onto the stem, at the rail"""


def _bow(lines: HullLines) -> Bow:
    start = lines.chine_height.span[0]
    tip = lines.sheer_half_width.span[0]
    if not tip < start:
        raise ValueError(f"the lines end aft of the start of the flat bottom at {start:.0f}")
    return Bow(start, tip)


# How full the forefoot's curve is: 2 is a quarter-ellipse, and lower fills it
# out towards the corner between the bottom and the stem.
FOREFOOT = 2.0


def _sweep(u: float) -> float:
    """How far up the forefoot is, 0..1, at `u` of the way from the flat to the tip.

    A superellipse: flat where it leaves the bottom, vertical at the tip.
    """
    return 1.0 - (1.0 - u**FOREFOOT) ** (1.0 / FOREFOOT)


def _face_x(lines: HullLines, bow: Bow, z: float) -> float:
    """Where the forefoot's face is at height `z`, found by bisection."""
    forward, aft = bow.tip, bow.start
    for _ in range(40):
        mid = 0.5 * (forward + aft)
        forward, aft = (forward, mid) if _outline(lines, mid, bow).z_chine < z else (mid, aft)
    return aft


def _station_positions(x0: float, x1: float, count: int) -> np.ndarray:
    """Cosine-spaced stations: dense at the ends, sparse amidships."""
    t = np.linspace(0.0, 1.0, count)
    return x0 + (x1 - x0) * (1.0 - np.cos(t * np.pi)) / 2.0


# Sections through the forefoot, counting the one where the flat bottom begins.
BOW_SECTIONS = 6
# How far round the forefoot's quarter-ellipse they go. Nearer the tip they thin
# to slivers that OCCT cannot cut cleanly, and the stem covers what is left.
BOW_REACH = 0.8


def _forefoot_positions(bow: Bow) -> np.ndarray:
    """The forefoot's sections, forward to aft, ending where the flat bottom begins.

    Spread evenly round the ellipse rather than along x: the curve ends
    vertical, so sections even in x would leave its steep part to one or two.
    """
    theta = np.linspace(0.0, BOW_REACH * np.pi / 2.0, BOW_SECTIONS)
    return np.sort(bow.start - (bow.start - bow.tip) * np.sin(theta))


class Outline(NamedTuple):
    """The four numbers that describe a section: chine and rail, out and up."""

    y_chine: float
    z_chine: float
    y_sheer: float
    z_sheer: float


def _outline(lines: HullLines, x: float, bow: Bow | None = None) -> Outline:
    """The section's corners at station `x`, read off the lines.

    Forward of `bow.start` the chine rises round the forefoot, and the bottom
    panel between the chines becomes the flat face the stem lies on. Forward of
    the tip there is no section at all; the chine meets the rail.
    """
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)
    if bow is None or x >= bow.start:
        return Outline(y_chine, z_chine, y_sheer, z_sheer)

    u = min((bow.start - x) / (bow.start - bow.tip), 1.0)
    return Outline(y_chine, z_chine + (z_sheer - z_chine) * _sweep(u), y_sheer, z_sheer)


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


def _section(lines: HullLines, x: float, bulge: Bulge | None = None, bow: Bow | None = None):
    """One transverse section at station `x`, as a planar face.

    Centreline to chine is flat -- that is the bottom panel -- then out and up to
    the rail, by way of any swell. The top edge closes the section across what
    will become the deck; the hollowing step removes it.
    """
    y_chine, z_chine, y_sheer, z_sheer = _outline(lines, x, bow)

    if y_chine <= 1e-6 or y_sheer < y_chine or z_sheer <= z_chine:
        return None

    starboard = _side_profile(y_chine, z_chine, y_sheer, z_sheer, bulge)
    points = [(x, -y, z) for y, z in reversed(starboard)] + [(x, y, z) for y, z in starboard]
    return make_face(Polyline(*points, close=True))


# How much of the result a boolean may leave behind as loose fragments before
# it counts as having cut the hull apart rather than merely shaved it.
DEBRIS_FRACTION = 1e-4


def as_part(shape: object, what: str) -> Part:
    """Remove any extra slivers left from a boolean operation.

    Public because rig.py does booleans against the hull too, and they can fail
    the same ways.
    """

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


def on_the_bed(part: Part, what: str) -> Part:
    """Dropped until its lowest point sits on z = 0, where a printer wants it."""
    return as_part(Pos(0.0, 0.0, -part.bounding_box().min.Z) * part, what)


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


def inner_half_width(
    lines: HullLines,
    x: float,
    wall: float,
    z: float,
    bulge: Bulge | None = None,
    bow: Bow | None = None,
) -> float:
    """How far the cavity's side stands from the centreline at height `z`.

    This is the inside face of the hull, and it is not the outside minus the
    wall. The side is flared, so it has to be offset perpendicular to itself;
    the line that results is what `_inner_section` builds its sections from and
    what anything fitted against the inside of the hull -- the mast's bar, say
    -- has to reach. One function so there is one answer.

    `z` may sit above the rail or below the chine; the line is simply extended,
    which is what the cavity itself needs at its top.
    """
    y_chine, z_chine, y_sheer, z_sheer = _outline(lines, x, bow)

    rise = z_sheer - z_chine
    run = y_sheer - y_chine
    if rise <= 1e-9:
        raise ValueError(f"the hull has no depth at station {x}")
    chord = float(np.hypot(rise, run))

    # The side offset inward by `wall`, as a point on it and its slope.
    base_y = y_chine - wall * rise / chord
    base_z = z_chine + wall * run / chord
    y = base_y + (z - base_z) * run / rise

    if bulge is not None:
        # The swell displaces the cavity by the same amount as the hull at the
        # same height -- see `Bulge`.
        y += bulge.at((z - z_chine) / rise) * bulge.amount * chord
    return y


@dataclass(frozen=True)
class Scaled:
    """The hull's lines in millimetres of the finished model.

    Everything in this module works in the source's own 1:1 millimetres and
    scales once at the end. Everything fitted to the hull afterwards -- the
    joinery, the mast's step, the awning's legs, the guns' slides -- works in
    printed millimetres, and each of them wants the same handful of answers
    about where the hull is. This is that handful, so a fitting asks rather
    than converting for itself.
    """

    spec: HullSpec
    lines: HullLines

    @property
    def factor(self) -> float:
        """Printed millimetres to the source's."""
        return self.spec.length / self.lines.length

    def station(self, fraction: float) -> float:
        """Along the boat, from a fraction of the overall length."""
        x0, x1 = self.lines.span
        return (x0 + (x1 - x0) * fraction) * self.factor

    def inside(self, x: float, z: float, wall: float | None = None) -> float:
        """The inside face of the planking at height `z`, or of a wall this thick."""
        factor = self.factor
        thick = (self.spec.wall if wall is None else wall) / factor
        return inner_half_width(self.lines, x / factor, thick, z / factor, self.spec.bulge) * factor

    def sheer(self, x: float) -> float:
        """The top of the rail."""
        return self.lines.sheer_height.value(x / self.factor) * self.factor

    def bottom(self, x: float) -> float:
        """The outside of the hull's bottom."""
        return self.lines.chine_height.value(x / self.factor) * self.factor

    def floor(self, x: float) -> float:
        """The inside of the bottom, where no deck covers it."""
        return self.bottom(x) + self.spec.wall

    def deck(self, deck: Deck) -> float:
        """A platform's height."""
        return deck.height * self.lines.depth * self.factor


def _inner_section(
    lines: HullLines,
    x: float,
    wall: float,
    floor_z: float | None = None,
    bulge: Bulge | None = None,
    bow: Bow | None = None,
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
    y_chine, z_chine, y_sheer, z_sheer = _outline(lines, x, bow)

    rise = z_sheer - z_chine
    if rise <= 1e-9:
        return None

    # Where the offset side meets the offset floor.
    bottom = z_chine + wall
    floor_z = bottom if floor_z is None else max(floor_z, bottom)
    floor_y = inner_half_width(lines, x, wall, floor_z, None, bow)

    # Carry the same line up past the rail.
    top_z = z_sheer + wall
    top_y = inner_half_width(lines, x, wall, top_z, None, bow)

    if floor_y <= 1e-6 or top_y < floor_y or top_z <= floor_z:
        return None

    starboard = [(floor_y, floor_z), (top_y, top_z)]
    if bulge is not None:
        chord = float(np.hypot(y_sheer - y_chine, rise))
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


def _cavity_span(
    lines: HullLines, wall: float, x0: float, x1: float, bow: Bow | None = None
) -> tuple[float, float]:
    """The first and last station that can hold a cavity, found by bisection.

    Near the stem and the transom the hull is narrower than two walls, so the
    cavity has to stop and leave those ends solid. Letting that happen wherever
    the stations happen to land makes the solid plugs an artefact of sampling:
    a plug's length would move by the better part of a metre (full size)
    depending only on the station count, silently changing the print weight
    along with it. Solving
    for the boundary instead pins the plugs to the geometry, so `stations`
    controls smoothness and nothing else.

    In the forefoot the bottom is the stem's face, which leans forward as it
    rises, so the cavity also has to stay a wall aft of that face at the height
    of its own floor.
    """

    def holds_cavity(x: float) -> bool:
        if _inner_section(lines, x, wall, None, None, bow) is None:
            return False
        if bow is None or x >= bow.start:
            return True
        floor = _outline(lines, x, bow).z_chine + wall
        return x - wall >= _face_x(lines, bow, floor)

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


def deck_at(spec: HullSpec, fraction: float) -> Deck | None:
    """The deck covering `fraction` of the length, or None over open bilge.

    What to do about open bilge is the caller's: a gun, a knee and an awning's
    leg all want a deck under them and all have their own way of saying so.
    """
    return next((d for d in spec.decks if d.start <= fraction <= d.end), None)


def open_stretches(decks: list[Deck]) -> list[tuple[float, float]]:
    """Everything the decks leave over: the stretches hollowed to the bottom.

    Public because the rig needs it: the mast steps into the forward well, and
    that well is wherever the decks happen not to be. Deriving it means moving
    a deck moves the mast with it, rather than leaving a socket in the middle
    of a platform.
    """
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
    floor_z: float | None,
    bulge: Bulge | None = None,
    bow: Bow | None = None,
) -> Part:
    """Subtract one cavity between `bounds`, its floor at `floor_z`.

    None for a floor takes it all the way down to the inside of the bottom,
    which is what makes a well. The loft caps its own ends, so each cut leaves a
    bulkhead at its boundary.
    """
    start, end = bounds
    if end - start <= 1e-6:
        return hull
    inside = [float(x) for x in stations if start < x < end]
    # Split where the flat bottom begins, as the hull itself is lofted.
    runs = [[start, *inside, end]]
    if bow is not None and start < bow.start < end:
        runs = [
            [start, *(x for x in inside if x < bow.start), bow.start],
            [bow.start, *(x for x in inside if x > bow.start), end],
        ]

    cavity = None
    for run in runs:
        faces = [
            f
            for f in (_inner_section(lines, x, wall, floor_z, bulge, bow) for x in run)
            if f is not None
        ]
        if len(faces) < 2:
            continue
        piece = loft(faces)
        cavity = piece if cavity is None else cavity + piece
    if cavity is None:
        return hull
    return as_part(hull - cavity, "cavity subtraction")


# Stations each groove's length is solved over. The deck's inside only curves
# gently along a platform, so a groove ends within a hair of where it could.
SEAM_SAMPLES = 200


def _seams(
    lines: HullLines,
    wall: float,
    bounds: tuple[float, float],
    floor: float,
    plank: float,
    first: float,
    seam: tuple[float, float, float],
    overrun: tuple[float, float],
    bulge: Bulge | None = None,
) -> list[Part]:
    """The grooves between one deck's planks, in the source's units like `_cut`.

    Straight grooves from `first` out, each running only where the deck is wide
    enough to keep it `margin` clear of the side -- so they stop short wherever
    the hull closes in. `overrun` is how far each end carries past the deck's
    own ends: out over an open edge, so the groove does not end on the
    bulkhead's face, or short of a neighbouring deck.

    `first` is where the innermost seam goes: half a plank out, so that a plank
    is centred on the centreline, unless something stands there.

    `seam` is the width, depth and margin of `Seams`, in the source's units.
    Trimming each groove to the deck rather than intersecting a comb with the
    cavity is the same shape at a quarter of the cost.
    """
    width, depth, margin = seam
    start, end = bounds
    if end - start <= 1e-6:
        return []
    along = np.linspace(start, end, SEAM_SAMPLES)
    room = np.array(
        [inner_half_width(lines, float(x), wall, floor - depth, bulge) for x in along]
    ) - (margin + 0.5 * width)

    grooves: list[Part] = []
    for y in np.arange(first, float(room.max()), plank):
        fits = along[room >= y]
        low = float(fits.min()) - (overrun[0] if fits.min() <= start else 0.0)
        high = float(fits.max()) + (overrun[1] if fits.max() >= end else 0.0)
        if high - low <= width:
            continue
        for side in (-1.0, 1.0):
            grooves.append(
                Pos(0.5 * (low + high), side * float(y), floor)
                * Box(high - low, width, 2.0 * depth)
            )
    return grooves


def _well_floor(
    lines: HullLines,
    wall: float,
    bounds: tuple[float, float],
    depth: float,
    bow: Bow | None = None,
) -> float:
    """The inside of the bottom over an open stretch, in the source's units.

    One height, because a groove is cut at one: the faired bottom is flat, so
    amidships this is a constant. Where it is not -- forward of `bow.start`,
    where the bottom sweeps up round the forefoot -- it is refused rather than
    averaged, since a straight groove at one height would surface in the middle
    of the ramp. Read off `_outline` for that reason, which is where the cavity
    takes its own floor from; the chine's curve alone clamps there instead of
    rising.
    """
    heights = [
        _outline(lines, float(x), bow).z_chine + wall
        for x in np.linspace(bounds[0], bounds[1], SEAM_SAMPLES)
    ]
    if max(heights) - min(heights) > depth:
        raise ValueError(
            f"the well from {bounds[0]:.0f} to {bounds[1]:.0f} has no flat floor to groove: "
            f"it rises {(max(heights) - min(heights)) / depth:.0f} times a seam's depth across it"
        )
    return max(heights)


def _hollow(
    hull: Part,
    spec: HullSpec,
    lines: HullLines,
    stations: np.ndarray,
    factor: float,
    bow: Bow | None = None,
) -> Part:
    """Hollow the undecked stretches to the bottom, and each deck to its height."""
    wall = spec.wall / factor
    bulge, seams, wells = spec.bulge, spec.seams, spec.wells
    x0, x1 = lines.span
    # Where the hull is wide enough to hold a cavity at all; a stretch reaching
    # past that is clipped rather than refused, so "open to the bow" means as
    # far forward as the stem allows.
    first, last = _cavity_span(lines, wall, x0, x1, bow)

    def clip(a: float, b: float) -> tuple[float, float]:
        return max(first, x0 + (x1 - x0) * a), min(last, x0 + (x1 - x0) * b)

    ordered = _ordered(spec.decks)
    stretches = open_stretches(ordered)

    def overrun(edge: float, others: list[Deck]) -> float:
        """Past an open edge, a wall's width; up against another deck, a margin short."""
        if seams is None:
            return 0.0
        abutting = any(abs(d.start - edge) < 1e-9 or abs(d.end - edge) < 1e-9 for d in others)
        return -seams.margin / factor if abutting else wall

    def grooves_for(
        bounds: tuple[float, float],
        floor: float,
        plank: float,
        first: float,
        ends: tuple[float, float],
    ) -> list[Part]:
        """One deck's or one well's seams, with the finished sizes put into the source's."""
        assert seams is not None
        return _seams(
            lines,
            wall,
            bounds,
            floor,
            plank / factor,
            first / factor,
            (seams.width / factor, seams.depth / factor, seams.margin / factor),
            ends,
            bulge,
        )

    hollowed = hull
    grooves: list[Part] = []
    for stretch in stretches:
        bounds = clip(*stretch)
        hollowed = _cut(hollowed, lines, stations, wall, bounds, None, bulge, bow)
        if seams is None or wells is None or bounds[1] - bounds[0] <= 1e-6:
            continue
        # A well abuts a deck at each end, so `overrun` pulls its grooves short
        # of both bulkheads rather than running them onto their faces.
        grooves += grooves_for(
            bounds,
            _well_floor(lines, wall, bounds, seams.depth / factor, bow),
            wells.plank,
            wells.clear,
            (overrun(stretch[0], list(ordered)), overrun(stretch[1], list(ordered))),
        )

    for deck in ordered:
        # Flat, and measured from the bottom rather than down from the rail:
        # the three platforms sit at three different heights, so each one is
        # its own number instead of a single drop below a sheer they no longer
        # share.
        floor = deck.height * lines.depth
        bounds = clip(deck.start, deck.end)
        hollowed = _cut(hollowed, lines, stations, wall, bounds, floor, bulge, bow)
        if seams is None or deck.plank is None:
            continue
        others = [d for d in ordered if d is not deck]
        grooves += grooves_for(
            bounds,
            floor,
            deck.plank,
            0.5 * deck.plank,
            (overrun(deck.start, others), overrun(deck.end, others)),
        )
    for deck in ordered:
        abutting = any(abs(d.start - deck.end) < 1e-9 for d in ordered)
        if deck.tab > 0.0 and deck.end < 1.0 and not abutting:
            edge = x0 + (x1 - x0) * deck.end
            for tab in _tabs(lines, wall, deck, edge, factor, bulge, bow):
                hollowed = as_part(hollowed + tab, "adding a deck's tab")

    if grooves:
        # One cut for every deck: each boolean costs about as much as the last.
        hollowed = as_part(hollowed - Part(Compound(grooves).wrapped), "cutting the seams")

    if hollowed.volume >= 0.95 * hull.volume:
        raise RuntimeError("hollowing removed nothing -- check the wall thickness and the decks")
    _assert_open(hollowed, lines, wall, stretches, x0, x1, first, last)
    return hollowed


# A deck's tab, as fractions of its length aft: how far it reaches in from the
# side, and the radius of the quarter circle cut out of its inboard aft corner.
TAB_WIDTH = 0.95
TAB_NOTCH = 1.0 / np.sqrt(2.0)
# Points round a tab's notch.
TAB_SAMPLES = 12


def _tabs(
    lines: HullLines,
    wall: float,
    deck: Deck,
    edge: float,
    factor: float,
    bulge: Bulge | None,
    bow: Bow | None,
) -> list[Part]:
    """The deck's aft corners, carried on past its end at `edge` along each side.

    Each tab is a square on the corner, `deck.tab` long and
    `TAB_WIDTH` of that in from the inside of the side, with a quarter circle
    `TAB_NOTCH` as large cut out of its inboard aft corner. Like the deck it is
    solid down to the bilge. It is drawn oversize in plan and trimmed to a
    cavity half a wall larger than the real one, so it fits the side and floor
    exactly and overlaps them rather than meeting them on a surface.
    """
    reach = deck.tab / factor
    width = TAB_WIDTH * reach
    notch = TAB_NOTCH * reach
    top = deck.height * lines.depth
    face = inner_half_width(lines, edge, wall, top, bulge, bow)
    inner = face - width

    cut = [
        (edge + reach + notch * np.cos(t), inner + notch * np.sin(t))
        for t in np.linspace(np.pi / 2.0, np.pi, TAB_SAMPLES)
    ]
    plan = [
        (edge - wall, face + 3.0 * wall),
        (edge + reach, face + 3.0 * wall),
        *cut,
        (edge - wall, inner),
    ]

    stations = np.linspace(edge - wall, edge + reach + wall, 4)
    sections = [_inner_section(lines, float(x), 0.5 * wall, None, bulge, bow) for x in stations]
    room = loft([f for f in sections if f is not None])

    tabs = []
    for side in (-1.0, 1.0):
        points = [(x, side * y, 0.0) for x, y in plan]
        block = extrude(make_face(Polyline(*points, close=True)), amount=top)
        tabs.append(as_part(block & room, "trimming a deck's tab"))
    return tabs


# Points along the stem.
STEM_SAMPLES = 48
# How far the stem's foot sits above the bottom, printed mm. Flush with it, the
# foot lies on the planking's bottom face tangentially, which OCCT cannot fuse.
STEM_LIFT = 0.2
# How far the stem's back reaches into the planking, printed mm, so the two
# overlap rather than meeting on a surface. Fixed rather than a share of the
# wall, so the stem is the same board however thick the hull is.
STEM_OVERLAP = 1.0


def _stem(lines: HullLines, bow: Bow, factor: float) -> Part:
    """The stem, in the source's millimetres: one board bent round the bow.

    Its back follows the face the planking leaves at the forefoot and its front
    stands `STEM_DEPTH` out from it everywhere, so its section is the same
    rectangle from foot to head. Where that would run below the bottom it is
    cut flat, and its head is cut flat at the rail. It is as wide as the face.

    The back is set `STEM_OVERLAP` into the planking.
    """
    theta = np.linspace(0.0, np.pi / 2.0, STEM_SAMPLES)
    xs = bow.start - (bow.start - bow.tip) * np.sin(theta)
    zs = np.array([_outline(lines, float(x), bow).z_chine for x in xs])

    # Unit normals pointing out of the hull: forward and down.
    tx, tz = np.gradient(xs), np.gradient(zs)
    length = np.hypot(tx, tz)
    nx, nz = -tz / length, tx / length

    depth = hull_lines.STEM_DEPTH
    overlap = STEM_OVERLAP / factor
    floor = lines.chine_height.value(bow.start) + STEM_LIFT / factor
    top = zs[-1]

    outer = [(x, 0.0, max(z, floor)) for x, z in zip(xs + depth * nx, zs + depth * nz, strict=True)]
    inner = [(x, 0.0, z) for x, z in zip(xs - overlap * nx, zs - overlap * nz, strict=True)][::-1]
    outer[-1] = (outer[-1][0], 0.0, top)
    inner[0] = (inner[0][0], 0.0, top)
    profile = make_face(Polyline(*outer, *inner, close=True))
    half = lines.chine_half_width.value(bow.start)
    return extrude(profile, amount=half, dir=(0.0, 1.0, 0.0), both=True)


def _loft(lines: HullLines, stations: np.ndarray, bulge: Bulge | None, bow: Bow) -> Part:
    faces = [f for f in (_section(lines, float(x), bulge, bow) for x in stations) if f is not None]
    if len(faces) < 2:
        raise RuntimeError("not enough valid stations to loft the hull")
    return loft(faces)


def build(spec: HullSpec | None = None, lines: HullLines | None = None) -> Part:
    """Loft the outer hull, add the stem, hollow it, and scale to the target length."""
    spec = spec or HullSpec()
    lines = lines or hull_lines.load()

    # Everything is built in the source's own millimetres and scaled exactly
    # once, at the end; `factor` converts the spec's finished sizes into them.
    factor = spec.length / lines.length

    bow = _bow(lines)
    forefoot = _forefoot_positions(bow)
    main = _station_positions(bow.start, lines.sheer_half_width.span[1], spec.stations)

    # Two lofts meeting on the section where the flat bottom begins. One loft
    # through both sets would overshoot the forefoot's tight turn into the long
    # gaps between stations aft, and dip below the bottom.
    hull = as_part(
        _loft(lines, forefoot, spec.bulge, bow) + _loft(lines, main, spec.bulge, bow),
        "joining the bow",
    )

    # Before the hollowing, so that the cavity trims whatever of the post lies
    # inside the planking and leaves only what stands proud of it.
    if spec.stem:
        post = _stem(lines, bow, factor)
        hull = as_part(hull + post, "adding the stem")

    if spec.deck_open:
        hull = _hollow(hull, spec, lines, np.concatenate([forefoot[:-1], main]), factor, bow)

    return as_part(scale(hull, factor), "scaling")


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
