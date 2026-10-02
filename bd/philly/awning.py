"""The awning frame over the after part of the boat.

The real boat carried a light frame over its after part: uprights off the
deck, a rail over the top, crossbars across, and canvas over that for shade.
Here the frame is a separate printed part that drops into sockets in the decks
and lifts straight out again, and the canvas is a thin plate that clips onto it
the way the sails clip onto the yards.

The frame is its legs: it runs from the first pair to the last, with a crossbar
over every pair, so each crossbar stands on something and both ends are closed.
The canvas clips to the two end crossbars, on necks that are `rig.neck_radius`
-- the same number the canvas's corner eyes are cut for, taken from rig.py
rather than copied.

Millimetres of the finished model throughout, as rig.py is; the hull arrives
already scaled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import (
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Part,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    chamfer,
    extrude,
    fillet,
)

from details import bench_top
from hull import HullSpec, Scaled, as_part, clear_of_seams, deck_at, on_the_bed
from lines import HullLines
from rig import TOLERANCE, Rig, neck, neck_radius, sail

# Square section for every member. The frame is handled, so nothing thinner.
BAR = 3.4

# How far a knee reaches along a bar and down a leg from the corner they make.
KNEE = 6.0


def knee_section(edge: float) -> float:
    """How wide a knee is: the flat of the bar it sits under, between its fillets.

    As wide as the bar, a knee stood its outer edge on the bar's rounded corner
    and left a lip hanging over nothing. Narrowing it to the flat fixes a second
    thing for free. Knees meet at a leg from the directions its bars run, and
    two slabs of half-width w crossing at an angle t overlap out to w / sin(t/2)
    from the leg's centre. The tightest angle in this frame is 64 degrees, where
    a rail meets the crossbar on the trapezoid stretch aft: at the bar's full
    width that reaches 3.2mm, past the leg's 2.4mm half-diagonal, so the two
    hypotenuses crossed in open air and left a spike. At the flat's width it
    reaches 2.07mm and the crossing is buried inside the leg.
    """
    return BAR - 2.0 * edge


# The step each upright is socketed into, how deep the socket is bored, and how
# far it reaches below the deck. Square, like the socket and the leg it takes: a
# round pad leaves only 0.7mm over a square hole's corners, where a square one
# leaves 1.8 all round. Its upright corners are rounded off, which is kinder to
# a hand and quicker to print, and which also buys back a little of the room the
# side of the boat takes away from it -- see `_pad`.
#
# The depth is what steadies the frame; the drop is only so the cut does not end
# on the deck's own face, because down is the one direction a socket cannot grow
# in -- see SIDE_FLOOR. Everything between is boss. Where a bench covers the
# deck it gives most of that depth itself, so a pair standing on one shows a
# 1.8mm pad rather than an 8mm block, for exactly the same hold.
BOSS = 7.0
BOSS_ROUND = 1.0
SOCKET_DEPTH = 8.5
SOCKET_DROP = 0.5

# The two halves of the lead-in: how far the chamfer on a leg's foot runs back
# up it, and how far the one round the mouth of its socket runs down. Between
# them a pair dropped in a millimetre out of true still finds its holes rather
# than standing on their rims. The mouth's is the smaller of the two because it
# is cut out of the boss's collar, which is only 1.5mm thick to begin with.
FOOT_CHAMFER = 0.8
MOUTH_CHAMFER = 0.6

# The least an upright stands off the inside of the hull.
SIDE_GAP = 0.3

# How far inside the planking a boss must keep. Not `SIDE_FLOOR`, which is a
# socket's rule: a hole takes material away and wants some left beside it, while
# a boss puts material in and only has to stop short of the surface. A token
# margin, so it beds into the planking rather than meeting it tangentially.
SKIN = 0.2

# Material that must be left under a socket. A deck is solid from the bottom of
# the hull up, so a socket's floor is also the hull's bottom, and anything
# thinner than a wall there is a leak waiting to happen.
FLOOR = 2.0

# Planking that must be left outboard of a socket, which is the real limit on
# how deep one can go. The side closes in as it falls and the uprights stand
# close to it, so every millimetre a hole drops below the deck costs about a
# fifth of one off the planking beside it. At the bottom of the hull the inside
# is 3 to 4.5mm narrower than where the legs step, so a socket bored to the
# bilge would come out through the side. Dropping 2mm below the deck, as they
# used to, left 0.67mm beside the aft pair.
SIDE_FLOOR = 1.0


@dataclass(frozen=True)
class Awning:
    """The frame's extent and proportions. Fractions of the overall length."""

    legs: tuple[float, ...] = (0.412, 0.57, 0.74, 0.82, 0.885)
    """where the pairs of uprights stand, which is also where the frame ends

    The first two pairs stand between the middle platform's knees, the second
    of them between the two 9-pounders' carriages. The next two stand on the
    quarterdeck's benches, and the last on the deck just aft of them, which
    carries the frame nearly to the transom as the museum's model has it.
    Further aft the hull closes in fast -- the inside narrows from 15mm of
    half-width at 0.90 to 11mm at 0.92 -- and legs there pinch the frame to a
    point. At 0.885 rather than 0.895 or 0.90, and the reason is the boss rather
    than the upright. Dodging the quarterdeck's seams moves this pair outboard,
    which the upright has room for at any of the three; the boss round its socket
    does not, and at 0.895 its corner nearest the transom stood 1.1mm outside
    the planking. Pulling the pair in instead is no good, because the next place
    clear of the seams is 3.6mm in and pinches the frame. Three millimetres
    forward costs nothing and the pair stays where it was, 13.6mm off the
    centreline.
    """
    headroom: float = 1828.8
    """standing room under the roof, in real-world millimetres: six feet

    Measured over the deck rather than as a clearance over the rail, because
    standing room is the thing it is for. Philadelphia II, the full-size
    recreation, carries her awning high enough to stand under amidships. Taken
    over the highest deck a pair of legs stands on -- the middle platform --
    since the benches aft are to sit on, not to stand on, and the quarterdeck
    they stand on is lower still.
    """
    inset: float = 2.5
    """how far inboard of the hull's inside face an upright's centreline stands"""
    edge: float = 0.6
    """how far the bars' long edges are rounded off"""

    def __post_init__(self) -> None:
        if len(self.legs) < 2:
            raise ValueError("an awning needs at least two pairs of legs")
        for leg in self.legs:
            if not 0.0 <= leg <= 1.0:
                raise ValueError(f"the leg at {leg} is off the boat")
        if list(self.legs) != sorted(set(self.legs)):
            raise ValueError("the legs are not in order bow to stern")
        if self.headroom <= 0.0:
            raise ValueError(f"an awning needs some headroom under it, got {self.headroom}")


@dataclass(frozen=True)
class Foot:
    """One pair of uprights: where they stand and what they stand on."""

    station: float
    """along the length, in millimetres"""
    half: float
    """the centreline's distance from the centreline of the boat"""
    deck: float
    """the height of the deck the socket is bored into"""
    step: float
    """what the pair stands on: the deck, or a bench's seat where one covers it"""
    bottom: float
    """the outside of the hull below it, which a socket must not reach"""

    @property
    def socket_floor(self) -> float:
        """Just under the deck, wherever the pair happens to step."""
        return self.deck - SOCKET_DROP

    @property
    def base(self) -> float:
        """The top of the boss, which is where an upright actually starts."""
        return self.socket_floor + SOCKET_DEPTH

    @property
    def boss(self) -> float:
        """How far the boss stands proud of what the pair steps on.

        A whole socket's worth on bare deck; on a bench, only what the bench
        does not already give.
        """
        return self.base - self.step


@dataclass(frozen=True)
class Frame:
    """Everything solved once, so the frame and the hull's sockets agree."""

    roof: float
    """the roof's height: planar, so one number"""
    feet: tuple[Foot, ...]
    nodes: tuple[tuple[float, float], ...]
    """the side rail as (station, half-width) points, one at each pair of legs"""
    clips: tuple[float, float]
    """how far out along the first and the last crossbar the canvas clips on"""
    neck: float
    """the clip neck's radius -- what the canvas's corner eyes were cut for"""
    clip_length: float

    @property
    def bars(self) -> tuple[float, ...]:
        """Crossbar stations: one over every pair of legs."""
        return tuple(station for station, _ in self.nodes)

    def half_at(self, station: float) -> float:
        """The side rail's offset at any station, along the polyline through the feet."""
        return float(np.interp(station, [n[0] for n in self.nodes], [n[1] for n in self.nodes]))


# Points round the outboard half of a boss, for measuring it against the side.
PAD_SAMPLES = 9


def _pad(half: float, round_: float) -> list[tuple[float, float]]:
    """The outboard edge of a boss in plan: a square with its corners rounded.

    As (along, outboard) offsets from the socket's centre. Only the outboard
    half, since that is the side the planking is on.

    This is sampled rather than measured at one station because the side of the
    boat falls away in plan as well as in section. The after pair stands where it
    falls away fastest: its boss's corner nearest the transom reached 2.1mm
    outside the planking and printed as a blister on the hull. Measured at the
    station alone -- which is what the socket needs, being narrow -- the boss
    looked as though it fitted.
    """
    straight = half - round_
    edge = [(along, half) for along in np.linspace(-straight, straight, PAD_SAMPLES)]
    for side in (-1.0, 1.0):
        turn = np.linspace(0.0, np.pi / 2.0, PAD_SAMPLES)
        edge += [
            (side * (straight + round_ * np.sin(t)), straight + round_ * np.cos(t)) for t in turn
        ]
    return [(float(along), float(out)) for along, out in edge]


def _foot(hull: Scaled, awning: Awning, leg: float) -> Foot:
    """One pair of uprights solved against the hull, with the height of its deck.

    The offset comes from `Scaled.inside` at the height of whatever the pair
    steps on -- the narrowest the inside gets over an upright's length, since
    the side flares outward going up. Measuring at the rail instead would put
    the feet through the planking.

    Two things can pull a pair further in than `inset` alone: the socket under
    it, which is below the deck where the side has closed in further (see
    `SIDE_FLOOR`), and the seams on a bare deck, which its boss must not end
    hard by.

    """
    spec = hull.spec
    deck = deck_at(spec, leg)
    if deck is None:
        raise ValueError(
            f"the leg at {leg:.3f} stands over open bilge; there is nothing to bore a socket in"
        )
    station = hull.station(leg)
    seat = bench_top(spec, hull.lines, leg)
    standing = hull.deck(deck)
    step = standing if seat is None else seat
    floor = standing - SOCKET_DROP

    # The tightest the inside gets along the upright's own length: toward the
    # transom the hull closes in fast enough that its after face is nearer the
    # side than its middle.
    def tightest(z: float, wall: float | None = None) -> float:
        return min(hull.inside(station + d, z, wall) for d in (-BAR / 2.0, 0.0, BAR / 2.0))

    half = tightest(step) - awning.inset
    # And no further out than the socket under it can go. The side closes in as
    # it falls and the socket's floor is below the deck, so it is the floor, not
    # the deck, that decides how far outboard a leg may stand if `SIDE_FLOOR` of
    # planking is to be left outboard of the hole.
    cap = tightest(floor, SIDE_FLOOR) - (BAR + 2.0 * TOLERANCE) / 2.0
    # The pad round the socket is wider than the hole and reaches further fore
    # and aft, so it is the boss, not the socket, that the side of the boat
    # catches first. Taken at the boss's own foot, the lowest it stands.
    cap = min(
        cap,
        min(
            hull.inside(station + along, step, SKIN) - out
            for along, out in _pad(BOSS / 2.0, BOSS_ROUND)
        ),
    )
    room = cap - half
    if seat is None:
        # On bare deck the boss must not end hard by a seam, and dodging one must
        # not push the upright into the side where it rises off the boss -- the
        # boss itself is meant to merge into the planking -- nor past what the
        # socket under it allows. A negative `room` is the cap already breached,
        # and asks the dodge for a move inboard.
        room = min(tightest(floor + SOCKET_DEPTH) - SIDE_GAP - BAR / 2.0 - half, room)
        edges = (half - BOSS / 2.0, half + BOSS / 2.0)
        half += clear_of_seams(spec, deck, edges, outboard=room)
    return Foot(
        station=station,
        half=min(half, cap),
        deck=standing,
        step=step,
        bottom=hull.bottom(station),
    )


def frame(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Frame:
    """Solve the frame against the hull it has to sit in; `_foot` solves the legs."""
    rig = rig or Rig()
    hull = Scaled(spec, lines)
    feet = [_foot(hull, awning, leg) for leg in awning.legs]

    # Headroom over the deck, so the roof is set by what it is for rather than
    # by a clearance over the rail. It still has to clear the rail: the sheer
    # rises toward the transom under the frame, and the check is against the
    # highest of it, not the average, so the roof stands clear everywhere rather
    # than only amidships.
    roof = max(foot.deck for foot in feet) + awning.headroom * hull.factor
    span = np.linspace(feet[0].station, feet[-1].station, 200)
    highest = max(hull.sheer(float(x)) for x in span)
    if roof < highest + BAR:
        raise ValueError(
            f"a roof {roof:.1f}mm up does not clear the rail at {highest:.1f}mm; "
            "raise the awning's headroom"
        )

    # Each neck just inboard of the rail, with a bar's half-width of square
    # shoulder between them so the canvas cannot slide along into the corner.
    def clip(foot: Foot) -> float:
        return foot.half - BAR - rig.clip_length / 2.0

    return Frame(
        roof=roof,
        feet=tuple(feet),
        nodes=tuple((f.station, f.half) for f in feet),
        clips=(clip(feet[0]), clip(feet[-1])),
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


def _knee(at: tuple[float, float, float], bearing: float, section: float, reach: float) -> Part:
    """A triangular knee in a corner a leg makes with a bar, pointing along it.

    `at` is the corner -- the leg's centreline at the bar's underside -- and
    `reach` is measured from there, so a knee overlaps both members rather than
    meeting them on a face. Right-angled and equal-legged, so laid roof-down
    every layer of it is smaller than the one beneath and the hypotenuse carries
    itself. A dropped boat snapped a leg off that corner; see HOW-IT-WORKS.md.

    `section` is the bar's flat, not the bar: see `KNEE_SECTION`.
    """
    with BuildPart() as knee:
        with BuildSketch(Plane.XZ.offset(-section / 2.0)):
            Polygon((0.0, 0.0), (reach, 0.0), (0.0, -reach), align=None)
        extrude(amount=section)
    assert knee.part is not None
    return as_part(Pos(*at) * (Rot(0.0, 0.0, bearing) * knee.part), "a knee")


def _crossbar(shape: Frame, station: float, edge: float, clip: float | None) -> Part:
    """One crossbar, necked where the canvas clips on, if it does.

    It runs athwartships, which is the way `rig.neck` cuts, so the yard's own
    neck serves here unchanged.
    """
    half = shape.half_at(station)
    bar = _span((station, -half), (station, half), shape.roof, BAR, edge)
    if clip is None:
        return as_part(bar, "a crossbar")
    for side in (-1.0, 1.0):
        at = Pos(station, side * clip, shape.roof)
        bar = neck(bar, at, BAR, shape.neck, shape.clip_length)
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
    necked = {shape.bars[0]: shape.clips[0], shape.bars[-1]: shape.clips[1]}
    parts += [_crossbar(shape, x, awning.edge, necked.get(x)) for x in shape.bars]

    section = knee_section(awning.edge)

    # A necked crossbar leaves a knee only the square between the leg and the
    # eye that clips on: the canvas's ring comes down round the neck and its
    # outboard face stands `clip_length / 2` short of the leg's centreline.
    def inboard(station: float) -> float:
        clip = necked.get(station)
        room = KNEE + BAR / 2.0
        if clip is None:
            return room
        return min(room, shape.half_at(station) - clip - shape.clip_length / 2.0)

    for index, foot in enumerate(shape.feet):
        for side in (-1.0, 1.0):
            # One square column from the bars' tops to the socket's floor. Up to
            # the tops rather than the roof's middle plane because the rails and
            # crossbars both stop at the leg's centre, and the leg is what fills
            # the corner they leave, so the roof prints flat to the end.
            #
            # Down into the socket at full section, where it used to step to a
            # round peg at the boss. That step was the weakest thing in the
            # frame -- 3.9mm^3 of section against the leg's 6.6, with a sharp
            # shoulder on it where the bending is worst -- and the feet snapped
            # off it. The socket is a square hole now, so there is nothing to
            # step down to, and the leg beds on the hole's floor.
            height = shape.roof + BAR / 2.0 - foot.socket_floor
            leg = Pos(foot.station, side * foot.half, foot.socket_floor + height / 2.0) * Box(
                BAR, BAR, height
            )
            # The foot chamfered, so a frame dropped in a little out of place
            # finds its holes instead of standing on their rims.
            footed = chamfer(leg.faces().sort_by(Axis.Z)[0].edges(), FOOT_CHAMFER)
            parts.append(as_part(footed, "a leg"))

            # Knees into every bar the leg runs into: the crossbar, inboard, and
            # each rail it has. An end leg has one rail, which is why it is the
            # one that wants them.
            corner = (foot.station, side * foot.half, shape.roof - BAR / 2.0)
            parts.append(_knee(corner, -90.0 * side, section, inboard(foot.station)))
            for other in (index - 1, index + 1):
                if not 0 <= other < len(shape.nodes):
                    continue
                run = shape.nodes[other][0] - foot.station
                across = side * (shape.nodes[other][1] - foot.half)
                bearing = float(np.degrees(np.arctan2(across, run)))
                parts.append(_knee(corner, bearing, section, KNEE + BAR / 2.0))

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
    return on_the_bed(rolled, "laying the awning down")


def canvas_offset(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> float:
    """How far the canvas's plate stands from its eyes' axes.

    Far enough that, rigged plate-up, it clears the tops of the crossbars the
    eyes hang from. The sails stand off further, but that is to clear the mast;
    the canvas only has the bars to clear.

    Its patches and bolt rope hang under the plate once it is rigged, so it is
    the thickest of those, not the plate, that has to clear them.
    """
    rig = rig or Rig()
    return BAR / 2.0 + max(rig.patch_thickness, rig.rope_thickness) + TOLERANCE


def canvas(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The awning's canvas, flat on the bed and eyes up, ready to print.

    It is a sail in all but name -- `rig.sail`, cut to the frame instead of the
    yards: its foot spans the necks on the first crossbar, its head the necks on
    the last, which is narrower because the hull closes in toward the transom.

    Between them it follows the frame rather than running straight from end to
    end, which over a frame that bows out along its sides read as a triangle.
    At each crossbar in between, its edge stands in from the side rail as far as
    it does at the ends, where the corner posts put it.
    """
    rig = rig or Rig()
    shape = frame(spec, lines, awning, rig)
    fore, aft = shape.clips
    # Laid flat the foot is at +x, and rigged it is turned end for end, so a
    # crossbar's station counts back from the middle.
    middle = 0.5 * (shape.bars[0] + shape.bars[-1])
    inset = BAR + TOLERANCE
    return sail(
        rig,
        foot=2.0 * fore,
        head=2.0 * aft,
        height=shape.bars[-1] - shape.bars[0],
        radius=shape.neck,
        offset=canvas_offset(spec, lines, rig),
        edge=tuple((middle - foot.station, foot.half - inset) for foot in shape.feet[1:-1]),
    )


def rigged_canvas(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The canvas clipped onto the frame, in the hull's own coordinates.

    Turned end for end and upside down at once -- a half turn about y -- so the
    plate is on top, the eyes hang under it with their mouths facing down onto
    the necks, and the wider foot goes forward, where the frame is wider.
    """
    rig = rig or Rig()
    shape = frame(spec, lines, awning, rig)
    middle = 0.5 * (shape.bars[0] + shape.bars[-1])
    turned = Rot(0.0, 180.0, 0.0) * canvas(spec, lines, awning, rig)
    return Pos(middle, 0.0, shape.roof + canvas_offset(spec, lines, rig)) * turned


def fit_awning(
    hull: Part, spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None
) -> Part:
    """Add the bosses to the decks and bore the sockets.

    The bosses stand the sockets up off the decks, and that is the only
    direction a socket can grow in. A deck is solid down to the outside of the
    hull, so there is no bilge under one to reach; what a deeper hole runs into
    is the side, which closes in as it falls while the uprights stand close to
    it. See `SIDE_FLOOR`, which is checked here. In a boss, the extra depth is
    above the deck instead, where the hull is wider, and the planking outboard
    of the hole is untouched.

    A pair standing on a bench gets its boss on the seat, so the bench has to be
    fitted first.

    The holes are square, like the legs: a round one needed the leg to step down
    to a round peg, and the peg was the weakest section in the frame.

    Nothing here is clipped to the hull: `frame` has already pulled each pair in
    far enough that its boss fits. See `_pad`.
    """
    shape = frame(spec, lines, awning, rig)
    at = Scaled(spec, lines)
    bore = BAR + 2.0 * TOLERANCE

    fitted = hull
    for foot in shape.feet:
        if foot.boss <= 0.0:
            raise RuntimeError(
                f"the bench at {foot.station:.0f}mm is deeper than the socket; "
                "there is no boss left to bore into"
            )
        if foot.socket_floor - foot.bottom < FLOOR:
            raise RuntimeError(
                f"the socket at {foot.station:.0f}mm leaves only "
                f"{foot.socket_floor - foot.bottom:.2f}mm of hull under it"
            )
        # The planking left outboard of it, offset perpendicular to the side the
        # way the hull measures its own wall. Taken at the socket's floor, which
        # is where the side has closed in the furthest.
        room = at.inside(foot.station, foot.socket_floor, SIDE_FLOOR)
        if foot.half + bore / 2.0 > room:
            raise RuntimeError(
                f"the socket at {foot.station:.0f}mm reaches "
                f"{foot.half + bore / 2.0 - room:.2f}mm past the {SIDE_FLOOR}mm of planking it "
                "must leave outboard of it"
            )
        for side in (-1.0, 1.0):
            place = (foot.station, side * foot.half)
            boss = Box(BOSS, BOSS, foot.boss)
            boss = fillet(boss.edges().filter_by(Axis.Z), BOSS_ROUND)
            fitted = as_part(
                fitted + Pos(*place, foot.step + foot.boss / 2.0) * boss,
                "setting an awning boss",
            )
    for foot in shape.feet:
        for side in (-1.0, 1.0):
            # A hair proud of the boss so the cut does not end on its top face.
            depth = SOCKET_DEPTH + 1.0
            place = (foot.station, side * foot.half)
            hole = Pos(*place, foot.socket_floor + depth / 2.0) * Box(bore, bore, depth)
            # And the mouth chamfered, which is the hull's half of the lead-in.
            # It flares going up, so each layer of the boss sits on a wider one
            # and there is nothing here for the printer to bridge.
            mouth = Pos(*place, foot.base - MOUTH_CHAMFER) * extrude(
                Rectangle(bore, bore), amount=MOUTH_CHAMFER, taper=-45.0
            )
            fitted = as_part(fitted - hole - mouth, "boring an awning socket")
    return fitted
