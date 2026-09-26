"""The awning frame over the after part of the boat.

The real boat carried a light frame from about the middle platform to the
transom: uprights off the deck, a rail over the top, crossbars across. It stowed
spare sails and gave shade. Here it is a separate printed part that drops into
sockets in the decks and lifts straight out again, so a sail can be struck from
the mast and rigged on the awning instead.

Two things decide its shape, and neither is written down twice:

- The crossbars are pitched at half the topsail's height, so *any* two-apart
  pair is exactly the sail's span. There is no special pair to keep in step if
  the rig changes.
- The clip necks are `rig.neck_radius`, the same number the sail's corner eyes
  were cut for, taken from rig.py rather than copied.

Millimetres of the finished model throughout, as rig.py is; the hull arrives
already scaled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import Axis, Box, Cylinder, Part, Pos, Rot, fillet

from hull import Deck, HullSpec, as_part, inner_half_width
from lines import HullLines
from rig import TOLERANCE, Rig, neck_radius, sail_sizes

# Square section for every member. The frame is handled, so nothing thinner.
BAR = 3.4

# The pad each upright steps on, and how far the socket is bored into it.
BOSS = 7.0
BOSS_HEIGHT = 3.0
SOCKET_DEPTH = 5.0

# Material that must be left under a socket. A deck is solid from the bottom of
# the hull up, so a socket's floor is also the hull's bottom, and anything
# thinner than a wall there is a leak waiting to happen.
FLOOR = 2.0


@dataclass(frozen=True)
class Awning:
    """The frame's extent and proportions. Fractions of the overall length."""

    span: tuple[float, float] = (0.39, 0.86)
    """fore and aft extent: from the front of the middle platform to short of the transom"""
    legs: tuple[float, ...] = (0.42, 0.58, 0.74, 0.82)
    """where the pairs of uprights stand

    Kept well forward of the transom, where the hull closes in fast: an upright
    stands on the quarterdeck, and the inside there narrows from 27mm of
    half-width at 0.80 to 15mm at 0.90. Legs that far aft pinch the frame to a
    point.
    """
    rise: float = 0.40
    """roof clearance above the highest rail it spans, as a fraction of the hull's depth"""
    inset: float = 2.5
    """how far inboard of the hull's inside face an upright's centreline stands"""
    edge: float = 0.6
    """how far the bars' long edges are rounded off"""

    def __post_init__(self) -> None:
        if not 0.0 <= self.span[0] < self.span[1] <= 1.0:
            raise ValueError(f"awning span {self.span} is not an increasing 0..1 range")
        if len(self.legs) < 2:
            raise ValueError("an awning needs at least two pairs of legs")
        for leg in self.legs:
            if not self.span[0] <= leg <= self.span[1]:
                raise ValueError(f"the leg at {leg} is outside the awning's span {self.span}")
        if list(self.legs) != sorted(self.legs):
            raise ValueError("the legs are not in order bow to stern")


@dataclass(frozen=True)
class Foot:
    """One pair of uprights: where they stand and what they stand on."""

    station: float
    """along the length, in millimetres"""
    half: float
    """the centreline's distance from the centreline of the boat"""
    deck: float
    """the height of the deck it steps on"""
    bottom: float
    """the outside of the hull below it, which a socket must not reach"""

    @property
    def base(self) -> float:
        """The top of the boss, which is where an upright actually starts."""
        return self.deck + BOSS_HEIGHT

    @property
    def socket_floor(self) -> float:
        return self.base - SOCKET_DEPTH


@dataclass(frozen=True)
class Frame:
    """Everything solved once, so the frame and the hull's sockets agree."""

    roof: float
    """the roof's height: planar, so one number"""
    feet: tuple[Foot, ...]
    nodes: tuple[tuple[float, float], ...]
    """the side rail as (station, half-width) points, the feet plus the span's ends"""
    bars: tuple[float, ...]
    """crossbar stations"""
    clip: float
    """how far out along a crossbar a sail clips on"""
    neck: float
    """the clip neck's radius -- what a sail's corner eye was cut for"""
    clip_length: float

    def half_at(self, station: float) -> float:
        """The side rail's offset at any station, along the polyline through the feet."""
        return float(np.interp(station, [n[0] for n in self.nodes], [n[1] for n in self.nodes]))


def _deck_at(spec: HullSpec, fraction: float) -> Deck | None:
    return next((d for d in spec.decks if d.start <= fraction <= d.end), None)


def frame(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Frame:
    """Solve the frame against the hull it has to sit in.

    The uprights' offsets come from `hull.inner_half_width` at the height of the
    deck they step on -- the narrowest the inside gets over an upright's length,
    since the side flares outward going up. Measuring at the rail instead would
    put the feet through the planking.
    """
    rig = rig or Rig()
    factor = spec.length / lines.length
    x0, x1 = lines.sheer_half_width.span

    def source(fraction: float) -> float:
        return x0 + (x1 - x0) * fraction

    feet: list[Foot] = []
    for leg in awning.legs:
        deck = _deck_at(spec, leg)
        if deck is None:
            raise ValueError(
                f"the leg at {leg:.3f} stands over open bilge; there is nothing to bore a socket in"
            )
        at = source(leg)
        height = deck.height * lines.depth * factor
        inside = inner_half_width(lines, at, spec.wall / factor, height / factor, spec.bulge)
        feet.append(
            Foot(
                station=at * factor,
                half=inside * factor - awning.inset,
                deck=height,
                bottom=lines.chine_height.value(at) * factor,
            )
        )

    def carried_to(station: float, near: Foot, far: Foot) -> float:
        """The side rail carried past the last leg, on the line of the last two.

        Not measured against the hull again: the ends overhang the legs, and the
        hull's inside at the rail is a couple of millimetres wider than it is
        down at the deck, so asking it would kink the rail outward at each end.
        """
        slope = (near.half - far.half) / (near.station - far.station)
        return max(near.half + slope * (station - near.station), BAR)

    # The roof clears the highest rail it spans, not the average one, so it
    # stands clear of the sheer everywhere rather than only amidships.
    stations = np.linspace(source(awning.span[0]), source(awning.span[1]), 200)
    highest = float(max(lines.sheer_height.value(float(x)) for x in stations)) * factor
    roof = highest + awning.rise * lines.depth * factor

    start, end = (spec.length * f for f in awning.span)
    nodes = [(start, carried_to(start, feet[0], feet[1]))]
    nodes += [(f.station, f.half) for f in feet]
    nodes += [(end, carried_to(end, feet[-1], feet[-2]))]

    # Half the topsail's height, so any two-apart pair of bars spans it exactly.
    sail_width, sail_height = sail_sizes(rig)[1]
    pitch = sail_height / 2.0
    bars = tuple(np.arange(start, end + 1e-9, pitch))

    return Frame(
        roof=roof,
        feet=tuple(feet),
        nodes=tuple(nodes),
        bars=bars,
        clip=sail_width / 2.0,
        neck=neck_radius(spec, lines, rig),
        clip_length=rig.clip_length,
    )


def _span(
    a: tuple[float, float], b: tuple[float, float], z: float, section: float, edge: float
) -> Part:
    """A bar between two points in plan, at height `z`.

    Placed by its midpoint and bearing, which is the least fiddly way to lay a
    box along an arbitrary line and works for the crossbars too. Filleted before
    it is turned, while its length still runs along x and the four edges to
    round off are the ones parallel to it.
    """
    length = float(np.hypot(b[0] - a[0], b[1] - a[1]))
    bearing = float(np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])))
    bar = Box(length, section, section)
    bar = fillet(bar.edges().filter_by(Axis.X), edge)
    middle = Pos(0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), z)
    return as_part(middle * (Rot(0.0, 0.0, bearing) * bar), "a bar")


def _crossbar(shape: Frame, station: float, edge: float) -> Part:
    """One crossbar, necked down wherever a sail can reach.

    The neck is the yard's trick again: cut the square away over the clip's
    length, put a cylinder back. The bar runs athwartships, so the cut is
    `clip_length` deep in y and the neck lies along y too. Bars too far aft to
    reach the sail's width are left plain rather than necked into nothing.
    """
    half = shape.half_at(station)
    bar = _span((station, -half), (station, half), shape.roof, BAR, edge)
    if half < shape.clip + BAR:
        return as_part(bar, "a crossbar")
    lengthwise = Rot(-90.0, 0.0, 0.0)
    for side in (-1.0, 1.0):
        at = Pos(station, side * shape.clip, shape.roof)
        bar -= at * Box(2.0 * BAR, shape.clip_length, 1.2 * BAR)
        bar += at * (lengthwise * Cylinder(shape.neck, shape.clip_length))
    return as_part(bar, "a crossbar")


def upright_frame(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The frame standing in the boat, in the hull's own coordinates."""
    shape = frame(spec, lines, awning, rig)

    parts = []
    for side in (-1.0, 1.0):
        for a, b in zip(shape.nodes, shape.nodes[1:], strict=False):
            parts.append(
                _span((a[0], side * a[1]), (b[0], side * b[1]), shape.roof, BAR, awning.edge)
            )
    parts += [_crossbar(shape, float(x), awning.edge) for x in shape.bars]

    for foot in shape.feet:
        for side in (-1.0, 1.0):
            height = shape.roof - foot.base
            leg = Pos(foot.station, side * foot.half, foot.base + height / 2.0) * Box(
                BAR, BAR, height
            )
            # Shy of the socket's bottom, so the leg seats on the boss rather
            # than standing on the tip of its own peg.
            peg = SOCKET_DEPTH - TOLERANCE
            parts.append(leg)
            parts.append(
                Pos(foot.station, side * foot.half, foot.base - peg / 2.0)
                * Cylinder(BAR / 2.0, peg)
            )

    whole = parts[0]
    for extra in parts[1:]:
        whole += extra
    return as_part(whole, "the awning frame")


def awning_part(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The frame rolled over, roof down on the bed, ready to print.

    Roof down because the roof is the one flat, connected plane in the part: the
    legs then rise off it as plain columns with nothing to bridge. The other way
    up the legs print first as thin towers and the whole roof has to span
    between them.
    """
    rolled = Rot(180.0, 0.0, 0.0) * upright_frame(spec, lines, awning, rig)
    return as_part(Pos(0.0, 0.0, -rolled.bounding_box().min.Z) * rolled, "laying the awning down")


def fit_awning(
    hull: Part, spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None
) -> Part:
    """Add the bosses to the decks and bore the sockets.

    The bosses stand the sockets up off the decks. A deck is solid down to the
    outside of the hull, so a socket bored straight into it would take most of
    its depth out of the bottom; in a boss, most of the hole is above the deck
    and the hull under it keeps its thickness.
    """
    shape = frame(spec, lines, awning, rig)
    bore = BAR + 2.0 * TOLERANCE

    fitted = hull
    for foot in shape.feet:
        if foot.socket_floor - foot.bottom < FLOOR:
            raise RuntimeError(
                f"the socket at {foot.station:.0f}mm leaves only "
                f"{foot.socket_floor - foot.bottom:.2f}mm of hull under it"
            )
        for side in (-1.0, 1.0):
            at = (foot.station, side * foot.half)
            fitted = as_part(
                fitted
                + Pos(*at, foot.deck + BOSS_HEIGHT / 2.0) * Cylinder(BOSS / 2.0, BOSS_HEIGHT),
                "setting an awning boss",
            )
    for foot in shape.feet:
        for side in (-1.0, 1.0):
            # A hair proud of the boss so the cut does not end on its top face.
            depth = SOCKET_DEPTH + 1.0
            fitted = as_part(
                fitted
                - Pos(foot.station, side * foot.half, foot.socket_floor + depth / 2.0)
                * Cylinder(bore / 2.0, depth),
                "boring an awning socket",
            )
    return fitted
