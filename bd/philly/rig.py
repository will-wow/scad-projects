"""The mast, its socket in the hull, the yards, and the sails.

The real boat carried a single 36ft mast with a square course and a topsail,
stepped in the forward well and held to a transverse beam by an iron band.
At 1:55 that mast is about 200mm, which is the one dimension here taken from
the record; nothing gives its diameter, so that is a ratio instead -- and a
deliberately generous one, because a true-scale 3.7mm rod 200mm long snaps.

The nautical names, since the code uses one word for a thing that has three:
the transverse beam is a *thwart*, the beam a mast passes through is the
*partners*, and the socket it stands in is the *step*. The bar here is all
three at once, so it is just "the bar".

Three printed parts:

- the bar and its tube, unioned into the hull so they print with it
- the mast, which lifts out of the tube, so the boat can be dismasted in play
  and the mast can turn under sail
- the sails, thin plates that clip onto the yards

Everything is in millimetres of the finished model, unlike hull.py, which works
in the source drawing's units until the last step. The hull arrives here already
scaled, so this is the far side of that line.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import Axis, Box, Cylinder, Part, Pos, RegularPolygon, Rot, extrude, fillet

from hull import HullSpec, as_part, inner_half_width, open_stretches
from lines import HullLines

# Clearance between parts that have to fit together, per side. Anything that
# slides into something else is grown or shrunk by this.
TOLERANCE = 0.3

# The bar's width and height, as a fraction of the hull's depth.
BAR_RATIO = 0.10

# The mast across its flats, as a fraction of the hull's depth. A period mast
# of this length would have been some 8 inches through, which is 3.7mm here --
# right, and far too fragile once it is 200mm long and printed lying down.
MAST_RATIO = 0.153


@dataclass(frozen=True)
class Rig:
    """The mast and what hangs off it. Lengths in millimetres unless noted."""

    mast_length: float = 200.8
    """the whole mast, foot to truck: 36ft at this model's 1:55"""
    neck_width: float = 0.5
    """the necked clip section's diameter, as a fraction of the mast's width

    The yard itself is square and as wide as the mast; this is only the short
    turned-down section a sail clips into.
    """
    yard_fillet: float = 0.6
    """how far the square yard's long edges are rounded off"""
    course: tuple[float, float] = (0.20, 0.52)
    """the lower sail's yards, as fractions of the mast's length from its foot"""
    topsail: tuple[float, float] = (0.58, 0.88)
    """the upper sail's yards, likewise"""
    course_span: tuple[float, float] = (0.36, 0.26)
    """yard lengths for the course and the topsail, as fractions of mast length"""
    clip_inset: float = 0.08
    """how far in from a yard's tip a sail clips on, as a fraction of its half-length"""
    clip_length: float = 2.5
    """the length of the necked section, which is what locates a sail fore and aft"""
    sail_thickness: float = 0.6
    """three layers at 0.2mm: thin enough to look like canvas, thick enough to survive"""
    loop_wall: float = 0.8
    """material around a sail's corner bore"""
    mast_clearance: float = 1.0
    """how far a sail must stay clear of the mast it hangs in front of"""
    mouth: float = 0.9
    """a corner eye's opening, as a fraction of the neck's diameter

    Under 1.0 so the sail clips on and stays put rather than falling off.
    """

    def __post_init__(self) -> None:
        for name, pair in (("course", self.course), ("topsail", self.topsail)):
            if not 0.0 < pair[0] < pair[1] < 1.0:
                raise ValueError(f"{name} yards {pair} are not an increasing 0..1 pair")
        if self.course[1] > self.topsail[0]:
            raise ValueError("the course's head yard is above the topsail's foot")


def mast_width(spec: HullSpec, lines: HullLines) -> float:
    """The mast across its flats, which sets the bore and so the tube."""
    return MAST_RATIO * lines.depth * (spec.length / lines.length)


def bar_size(spec: HullSpec, lines: HullLines) -> float:
    """The bar is square, and this is its side."""
    return BAR_RATIO * lines.depth * (spec.length / lines.length)


@dataclass(frozen=True)
class Step:
    """Where the mast's socket sits, in millimetres of the finished model.

    Worked out once and handed to everything that needs it: the hull fitting
    builds to these numbers, and the mast is cut to match them.
    """

    station: float
    """along the length, at the middle of the forward well"""
    bar_top: float
    """the bar's upper face, one bar-width below the rail"""
    bar_size: float
    bar_half_length: float
    """half the bar's span: the inside of the hull at the bar's top edge"""
    floor: float
    """the inside of the hull's bottom -- the bore stops here, or the boat leaks"""
    outer_floor: float
    """the outside of the bottom, so the tube can be merged into it"""
    top: float
    """the top of the tube, one bar-width proud of the rail"""
    bore_radius: float
    wall: float

    @property
    def socket(self) -> float:
        """How much of the mast the tube holds."""
        return self.top - self.floor

    @property
    def tube_radius(self) -> float:
        return self.bore_radius + self.wall


def step(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> Step:
    """Solve where the mast steps, from the hull's own lines.

    The station comes from the decks rather than a number: the mast stands in
    the forward well, and the well is wherever the first stretch of deck stops.
    Move a deck and the mast moves with it instead of ending up buried in a
    platform.
    """
    rig = rig or Rig()
    factor = spec.length / lines.length
    stretches = open_stretches(sorted(spec.decks, key=lambda d: d.start))
    if not stretches:
        raise ValueError("the hull is decked over end to end; there is no well to step a mast in")
    start, end = stretches[0]

    x0, x1 = lines.sheer_half_width.span
    source_x = x0 + (x1 - x0) * 0.5 * (start + end)
    wall = spec.wall / factor

    bar = bar_size(spec, lines)
    rail = lines.sheer_height.value(source_x) * factor
    chine = lines.chine_height.value(source_x) * factor
    bar_top = rail - bar

    return Step(
        station=source_x * factor,
        bar_top=bar_top,
        bar_size=bar,
        # Measured at the bar's top, which is the widest the inside gets over
        # the bar's height. The side flares, so the bar then overlaps into the
        # wall at its lower edge -- by less than the wall is thick, so it meets
        # the hull all the way down without breaking through.
        bar_half_length=inner_half_width(lines, source_x, wall, bar_top / factor, spec.bulge)
        * factor,
        floor=chine + spec.wall,
        outer_floor=chine,
        # One bar-width proud of the rail: enough to read as a fitting, little
        # enough that the boat still looks like a boat with the mast out.
        top=rail + bar,
        bore_radius=mast_width(spec, lines) / 2.0 + TOLERANCE,
        wall=spec.wall,
    )


def fit_mast(hull: Part, spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> Part:
    """Add the bar and the mast tube to a finished hull, and bore them.

    Has to run after the hull is hollowed: the cavity subtraction would carve
    straight back through anything added before it.

    The tube runs all the way down to the bottom, which is doing two jobs. It
    steps the mast, and it plants a pillar under the middle of the bar -- the
    bar spans the whole well, and without something under it that is a single
    unsupported span of about 78mm to bridge. Halved, it is printable.
    """
    rig = rig or Rig()
    seat = step(spec, lines, rig)

    bar = Pos(seat.station, 0.0, seat.bar_top - seat.bar_size / 2.0) * Box(
        seat.bar_size, 2.0 * seat.bar_half_length, seat.bar_size
    )

    tube_height = seat.top - seat.outer_floor
    tube = Pos(seat.station, 0.0, seat.outer_floor + tube_height / 2.0) * Cylinder(
        seat.tube_radius, tube_height
    )

    # From the inside of the bottom up, and a hair past the tube's top so the
    # cut does not end on a coincident face. It must not reach the outside of
    # the bottom: a bore through the hull is a hole in the boat.
    bore_height = seat.top + 1.0 - seat.floor
    bore = Pos(seat.station, 0.0, seat.floor + bore_height / 2.0) * Cylinder(
        seat.bore_radius, bore_height
    )

    return as_part(as_part(hull + bar + tube, "fitting the mast bar") - bore, "boring the mast")


def yards(rig: Rig) -> list[tuple[float, float]]:
    """Each yard as (height up the mast, half its length), in millimetres.

    Height is measured from the mast's foot, so an assembled view has to add
    wherever the foot ends up -- the bottom of the bore, since that is what the
    mast stands on.
    """
    course_span, topsail_span = rig.course_span
    return [
        (rig.course[0] * rig.mast_length, course_span * rig.mast_length / 2.0),
        (rig.course[1] * rig.mast_length, course_span * rig.mast_length / 2.0),
        (rig.topsail[0] * rig.mast_length, topsail_span * rig.mast_length / 2.0),
        (rig.topsail[1] * rig.mast_length, topsail_span * rig.mast_length / 2.0),
    ]


def _yard(rig: Rig, width: float, half: float) -> Part:
    """One yard, centred on the origin and running along y.

    Square, and as wide as the mast, so that it lies on the bed when the mast is
    laid down to print. Round yards looked better and did not print: a 2.5mm
    cylinder on the mast's centreline hangs 1.25mm clear of the bed for the
    whole 72mm of its length, with nothing underneath it.

    Where a sail clips on, a short length is turned down to a round neck. That
    is a 2.5mm bridge between two square shoulders rather than an overhang, and
    the shoulders are what stop a sail sliding along the yard.
    """
    radius = rig.neck_width * width / 2.0
    bar = Box(width, 2.0 * half, width)
    bar = fillet(bar.edges().filter_by(Axis.Y), rig.yard_fillet)
    lengthwise = Rot(-90.0, 0.0, 0.0)
    for side in (-1.0, 1.0):
        at = Pos(0.0, side * half * (1.0 - rig.clip_inset), 0.0)
        # Cut the square away over the clip's length, then put the neck back.
        bar -= at * Box(2.0 * width, rig.clip_length, 1.2 * width)
        bar += at * (lengthwise * Cylinder(radius, rig.clip_length))
    return as_part(bar, "a yard")


def upright_mast(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> Part:
    """The mast standing on the origin, which is the easy way to reason about it.

    Public so an assembled view can stand it in the boat. `mast()` is the same
    thing laid down for printing.

    Round for as long as it is in the tube, so it turns; hexagonal above, which
    is what lets it print lying down on a flat face rather than on a curve.
    """
    rig = rig or Rig()
    seat = step(spec, lines, rig)
    width = mast_width(spec, lines)
    base = seat.socket + TOLERANCE  # stands proud of the tube by the clearance

    shaft = Pos(0.0, 0.0, base / 2.0) * Cylinder(width / 2.0, base)

    # rotation=30 puts the flats across x. After this part is laid down, x is
    # what faces the bed, so the mast prints on a flat rather than an edge.
    hexagon = RegularPolygon(width / np.sqrt(3.0), 6, rotation=30.0)
    shaft += Pos(0.0, 0.0, base) * extrude(hexagon, amount=rig.mast_length - base)

    for height, half in yards(rig):
        shaft += Pos(0.0, 0.0, height) * _yard(rig, width, half)

    return as_part(shaft, "the mast")


def mast(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> Part:
    """The mast, laid down along +X ready to print.

    Printed standing up it would be a 200mm tower on a 5mm footprint, so it is
    exported lying on the bed. Rotating about Y carries the shaft from +Z to +X
    and leaves the yards along Y, all of it in the plane of the bed.
    """
    rig = rig or Rig()
    laid = Rot(0.0, 90.0, 0.0) * upright_mast(spec, lines, rig)
    return as_part(Pos(0.0, 0.0, -laid.bounding_box().min.Z) * laid, "laying the mast down")


def neck_radius(spec: HullSpec, lines: HullLines, rig: Rig) -> float:
    """Half the necked clip section, which is what a sail's corner has to clear."""
    return rig.neck_width * mast_width(spec, lines) / 2.0


def stand_off(spec: HullSpec, lines: HullLines, rig: Rig) -> float:
    """How far a sail's plate hangs from the yard's axis.

    Far enough to clear the mast. A sail spans the whole width of its yard and
    the mast stands in the middle of it, so a plate any nearer the axis tries to
    occupy the same space as the mast -- which is exactly what the first
    assembled render showed it doing, 130 cubic millimetres of overlap a sail.

    Measured against the mast across its corners, which is the wider way and so
    holds however the mast is turned in its socket. It can turn: that is the
    point of the round base.
    """
    corners = mast_width(spec, lines) / np.sqrt(3.0)
    return corners + rig.sail_thickness + rig.mast_clearance


def sail_sizes(rig: Rig) -> list[tuple[float, float]]:
    """Each sail as (width between the yards' clip necks, height between the yards)."""
    course_span, topsail_span = rig.course_span
    sizes = []
    for (low, high), span in (
        (rig.course, course_span),
        (rig.topsail, topsail_span),
    ):
        half = span * rig.mast_length / 2.0
        sizes.append(
            (
                2.0 * half * (1.0 - rig.clip_inset),
                (high - low) * rig.mast_length,
            )
        )
    return sizes


def sail(rig: Rig, width: float, height: float, radius: float, offset: float) -> Part:
    """One sail, lying flat: the plate in the XY plane, corner eyes along Y.

    Public so an assembled view can hang one on the yards; `sails()` lays both
    out side by side for printing instead.

    The corners cannot simply be holes. The bore has to be wider than the yard,
    and the yard is several times thicker than the plate, so a hole through the
    plate's edge would be wider than the plate itself. Each corner gets an eye
    on a short neck instead, which is what a real sail's cringle is anyway.

    The neck is what holds the plate clear of the mast -- see `stand_off` -- and
    it is as wide as the eye, so nothing overhangs: the whole corner rises off
    the bed as a wall with a ring on top. The eye's mouth opens away from the
    bed, and so, once the sail is rigged, square to the sail, which is what lets
    it press onto both its yards at once. A mouth facing up on one yard and down
    on the other would need the sail to stretch to reach both.
    """
    bore = radius + TOLERANCE
    outer = bore + rig.loop_wall
    plate = Pos(0.0, 0.0, rig.sail_thickness / 2.0) * Box(height, width, rig.sail_thickness)

    eye_length = rig.clip_length - 2.0 * TOLERANCE
    mouth = rig.mouth * 2.0 * radius
    lengthwise = Rot(-90.0, 0.0, 0.0)
    sail = plate
    for along in (-height / 2.0, height / 2.0):
        for across in (-width / 2.0, width / 2.0):
            corner = Pos(along, across, 0.0)
            sail += corner * Pos(0.0, 0.0, offset / 2.0) * Box(2.0 * outer, eye_length, offset)
            sail += corner * Pos(0.0, 0.0, offset) * (lengthwise * Cylinder(outer, eye_length))
            sail -= corner * Pos(0.0, 0.0, offset) * (lengthwise * Cylinder(bore, eye_length + 2.0))
            # The slot, from the bore's centre straight up and out.
            sail -= (
                corner
                * Pos(0.0, 0.0, offset + outer / 2.0 + 0.5)
                * Box(mouth, eye_length + 2.0, outer + 1.0)
            )
    return as_part(sail, "a sail")


def sails(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> Part:
    """Both sails, side by side and flat on the bed."""
    rig = rig or Rig()
    radius = neck_radius(spec, lines, rig)
    offset = stand_off(spec, lines, rig)
    gap = 5.0
    built = []
    across = 0.0
    for width, height in sail_sizes(rig):
        built.append(Pos(0.0, across + width / 2.0, 0.0) * sail(rig, width, height, radius, offset))
        across += width + gap
    together = built[0]
    for extra in built[1:]:
        together += extra
    # Deliberately not run through as_part: these really are separate solids,
    # laid out side by side for one print, so "more than one piece" is the
    # answer rather than the failure it would be anywhere else here.
    if len(together.solids()) != len(built):
        raise RuntimeError(f"expected {len(built)} sails, got {len(together.solids())}")
    if not together.is_valid:
        raise RuntimeError("the sails are not a valid solid")
    return together
