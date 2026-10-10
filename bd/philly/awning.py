"""The awning frame over the after part of the boat.

The real boat carried a light frame over its after part: stanchions off the
deck, a rail over the top, crossbars across, and canvas over that for shade.
Here the frame is a separate printed part that drops into sockets in the decks
and lifts straight out again, and the canvas is a thin plate that clips onto it
the way the sails clip onto the yards.

The uprights are *stanchions* on Falconer's own authority -- his 1769 entry for
AWNING has it supported by "a range of light posts, called stanchions, which are
erected along the ship's side on the right and left". He gives no word at all
for the canvas's upper surface, so that is just its top.

The frame is its stanchions: it runs from the first pair to the last, with a
crossbar over every pair, so each stands on something and both ends are closed.
The canvas clips to the two end crossbars, on necks that are `rig.neck_radius`
-- the same number the canvas's corner cringles are cut for, taken from rig.py
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
    Mode,
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

# How a knee is proportioned: the angle its diagonal leans off the stanchion,
# how far short of the boss its taper ends, and how wide the three bars it is
# made of are. A knee is hollow -- what it is for is the taper at each toe and
# the diagonal between them, and the middle of a solid one is material doing
# nothing but hiding the boat.
#
# The angle used to be 45 degrees because that is the model's overhang limit,
# but nothing here was ever bound by it. Laid roof-down a knee's outer face
# points up, so its profile shrinks going up whatever the angle; the only face
# that leans is the hole's, and leaning the diagonal nearer the stanchion makes
# that one shallower, not steeper. So it is free to be chosen for strength
# instead, and the strongest place to take it is as far down the stanchion as
# the boss allows.
KNEE_ANGLE = 30.0
KNEE_CLEAR = 1.0
KNEE_WEB = 1.4


def knee_reach(free: float) -> tuple[float, float]:
    """How far one knee runs along its bar and down its stanchion.

    `free` is the stanchion standing clear between the boss and the bar's
    underside. A knee stops adding section where its profile meets the
    stanchion's face, half a bar in, so the taper ends `KNEE_CLEAR` above the
    boss; the triangle itself runs on past it, buried in the stanchion.
    """
    lean = np.tan(np.radians(KNEE_ANGLE))
    along = (free - KNEE_CLEAR) * lean + BAR / 2.0
    return float(along), float(along / lean)


def knee_section(edge: float) -> float:
    """How wide a knee is: the flat of the bar it sits under, between its fillets.

    As wide as the bar, a knee stood its outer edge on the bar's rounded corner
    and left a lip hanging over nothing. Narrowing it to the flat fixes a second
    thing for free. Knees meet at a stanchion from the directions its bars run, and
    two slabs of half-width w crossing at an angle t overlap out to w / sin(t/2)
    from the stanchion's centre. The tightest angle in this frame is 64 degrees, where
    a rail meets the crossbar on the trapezoid stretch aft: at the bar's full
    width that reaches 3.2mm, past the stanchion's 2.4mm half-diagonal, so the two
    hypotenuses crossed in open air and left a spike. At the flat's width it
    reaches 2.07mm and the crossing is buried inside the stanchion.
    """
    return BAR - 2.0 * edge


# The step each stanchion is socketed into, how deep the socket is bored, and how
# far it reaches below the deck. Square, like the socket and the stanchion it takes: a
# round pad leaves only 0.7mm over a square hole's corners, where a square one
# leaves 1.8 all round. Its upright corners are rounded off, which is kinder to
# a hand and quicker to print, and which also buys back a little of the room the
# side of the boat takes away from it -- see `_pad`.
#
# The depth is what steadies the frame; the drop is only so the cut does not end
# on the deck's own face, because down is the one direction a socket cannot grow
# in -- see SIDE_PLANKING. Everything between is boss. Where a bench covers the
# deck it gives most of that depth itself, so a pair standing on one shows a
# 1.8mm pad rather than an 8mm block, for exactly the same hold.
BOSS = 7.0
BOSS_ROUND = 1.0
SOCKET_DEPTH = 8.5
SOCKET_DROP = 0.5

# The two halves of the lead-in: how far the chamfer on a stanchion's foot runs back
# up it, and how far the one round the mouth of its socket runs down. Between
# them a pair dropped in a millimetre out of true still finds its holes rather
# than standing on their rims. The mouth's is the smaller of the two because it
# is cut out of the boss's collar, which is only 1.5mm thick to begin with.
FOOT_CHAMFER = 0.8
MOUTH_CHAMFER = 0.6

# The foot proper: a solid right triangle on the stanchion's inboard face, its
# square corner on the mouth plane, its hypotenuse leaning `FOOT_ANGLE` off the
# leg and running to the bottom of the socket. The reach inboard falls out of
# that angle and the socket's depth.
#
# A triangle rather than a swelling because no length of the leg may be left
# plain bar. A swelling that tapers back in leaves a stub below it, and a stub
# is what snaps -- so the triangle backs the whole of the spigot, and above the
# mouth plane the knee carries the leg.
#
# A square peg in a closed hole can be no thicker than its bore, so the only
# section the mouth plane could ever have was the bar's own -- and the mouth
# plane is where a held foot bends hardest. Opening the boss toward the
# centreline lifts that limit: the socket becomes a keyhole, a channel running
# inboard from the bore, and the foot can be as deep as the deck inboard of it
# is clear. Inboard rather than any other way because the frame fails by
# splaying: a stanchion whose head goes outboard is in tension on its inboard
# face, exactly where the triangle puts its material.
FOOT_ANGLE = 30.0
FOOT_REACH = float(SOCKET_DEPTH * np.tan(np.radians(FOOT_ANGLE)))

# The least a stanchion stands off the inside of the hull.
SIDE_GAP = 0.3

# How far inside the planking a boss must keep. Not `SIDE_PLANKING`, which is a
# socket's rule: a hole takes material away and wants some left beside it, while
# a boss puts material in and only has to stop short of the surface. A token
# margin, so it beds into the planking rather than meeting it tangentially.
SKIN = 0.2

# Planking that must be left under a socket. A deck is solid from the bottom of
# the hull up, so a socket's floor is also the hull's bottom, and anything
# thinner than the planking there is a leak waiting to happen.
BOTTOM_PLANKING = 2.0

# Planking that must be left outboard of a socket, which is the real limit on
# how deep one can go. The side closes in as it falls and the stanchions stand
# close to it, so every millimetre a hole drops below the deck costs about a
# fifth of one off the planking beside it. At the bottom of the hull the inside
# is 3 to 4.5mm narrower than where the stanchions step, so a socket bored to the
# bilge would come out through the side. Dropping 2mm below the deck, as they
# used to, left 0.67mm beside the aft pair.
SIDE_PLANKING = 1.0


@dataclass(frozen=True)
class Awning:
    """The frame's extent and proportions. Fractions of the overall length."""

    stanchions: tuple[float, ...] = (0.412, 0.545, 0.74, 0.82, 0.885)
    """where the pairs of stanchions stand, which is also where the frame ends

    The first two pairs stand between the middle platform's knees, the second
    of them midway between the two 9-pounders' carriages -- dead midway, which
    it had not been. At 0.57 it stood 19mm clear of the forward carriage and
    3.8 of the after one, and its knee reached down into the after one's
    bracket once the knees were drawn to the boss. At 0.545 it has 11.5mm
    either side and the gun can still run out under the frame. The next two stand on the
    quarterdeck's benches, and the last on the deck just aft of them, which
    carries the frame nearly to the transom as the museum's model has it.
    Further aft the hull closes in fast -- the inside narrows from 15mm of
    half-width at 0.90 to 11mm at 0.92 -- and a pair there pinches the frame to a
    point. At 0.885 rather than 0.895 or 0.90, and the reason is the boss rather
    than the stanchion. Dodging the quarterdeck's seams moves this pair outboard,
    which the stanchion has room for at any of the three; the boss round its socket
    does not, and at 0.895 its corner nearest the transom stood 1.1mm outside
    the planking. Pulling the pair in instead is no good, because the next place
    clear of the seams is 3.6mm in and pinches the frame. Three millimetres
    forward costs nothing and the pair stays where it was, 13.6mm off the
    centreline.
    """
    headroom: float = 1828.8
    """standing room under the canvas, in real-world millimetres: six feet

    Measured over the deck rather than as a clearance over the rail, because
    standing room is the thing it is for. Philadelphia II, the full-size
    recreation, carries her awning high enough to stand under amidships. Taken
    over the highest deck a pair stands on -- the middle platform --
    since the benches aft are to sit on, not to stand on, and the quarterdeck
    they stand on is lower still.
    """
    inset: float = 2.5
    """how far inboard of the hull's inside face an stanchion's centreline stands"""
    edge: float = 0.6
    """how far the bars' long edges are rounded off"""

    def __post_init__(self) -> None:
        if len(self.stanchions) < 2:
            raise ValueError("an awning needs at least two pairs of stanchions")
        for station in self.stanchions:
            if not 0.0 <= station <= 1.0:
                raise ValueError(f"the stanchion at {station} is off the boat")
        if list(self.stanchions) != sorted(set(self.stanchions)):
            raise ValueError("the stanchions are not in order bow to stern")
        if self.headroom <= 0.0:
            raise ValueError(f"an awning needs some headroom under it, got {self.headroom}")


@dataclass(frozen=True)
class Foot:
    """One pair of stanchions: where they stand and what they stand on."""

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
        """The top of the boss, which is where a stanchion actually starts."""
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

    top: float
    """the height of its top: planar, so one number"""
    feet: tuple[Foot, ...]
    nodes: tuple[tuple[float, float], ...]
    """the side rail as (station, half-width) points, one at each pair of stanchions"""
    clips: tuple[float, float]
    """how far out along the first and the last crossbar the canvas clips on"""
    neck: float
    """the clip neck's radius -- what the canvas's corner cringles were cut for"""
    clip_length: float

    @property
    def bars(self) -> tuple[float, ...]:
        """Crossbar stations: one over every pair of stanchions."""
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


def _foot(hull: Scaled, awning: Awning, at: float) -> Foot:
    """One pair of stanchions solved against the hull, with the height of its deck.

    The offset comes from `Scaled.inside` at the height of whatever the pair
    steps on -- the narrowest the inside gets over a stanchion's length, since
    the side flares outward going up. Measuring at the rail instead would put
    the feet through the planking.

    Two things can pull a pair further in than `inset` alone: the socket under
    it, which is below the deck where the side has closed in further (see
    `SIDE_PLANKING`), and the seams on a bare deck, which its boss must not end
    hard by.

    """
    spec = hull.spec
    deck = deck_at(spec, at)
    if deck is None:
        raise ValueError(
            f"the stanchion at {at:.3f} stands over open bilge; "
            "there is nothing to bore a socket in"
        )
    station = hull.station(at)
    seat = bench_top(spec, hull.lines, at)
    standing = hull.deck(deck)
    step = standing if seat is None else seat
    floor = standing - SOCKET_DROP

    # The tightest the inside gets along the stanchion's own length: toward the
    # transom the hull closes in fast enough that its after face is nearer the
    # side than its middle.
    def tightest(z: float, planking: float | None = None) -> float:
        return min(hull.inside(station + d, z, planking) for d in (-BAR / 2.0, 0.0, BAR / 2.0))

    half = tightest(step) - awning.inset
    # And no further out than the socket under it can go. The side closes in as
    # it falls and the socket's floor is below the deck, so it is the floor, not
    # the deck, that decides how far outboard a stanchion may stand if `SIDE_PLANKING` of
    # planking is to be left outboard of the hole.
    cap = tightest(floor, SIDE_PLANKING) - (BAR + 2.0 * TOLERANCE) / 2.0
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
        # not push the stanchion into the side where it rises off the boss -- the
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
    """Solve the frame against the hull it has to sit in; `_foot` solves the stanchions."""
    rig = rig or Rig()
    hull = Scaled(spec, lines)
    feet = [_foot(hull, awning, stanchion) for stanchion in awning.stanchions]

    # Headroom over the deck, so the top is set by what it is for rather than
    # by a clearance over the rail. It still has to clear the rail: the sheer
    # rises toward the transom under the frame, and the check is against the
    # highest of it, not the average, so the top stands clear everywhere rather
    # than only amidships.
    top = max(foot.deck for foot in feet) + awning.headroom * hull.factor
    span = np.linspace(feet[0].station, feet[-1].station, 200)
    highest = max(hull.sheer(float(x)) for x in span)
    if top < highest + BAR:
        raise ValueError(
            f"a top {top:.1f}mm up does not clear the rail at {highest:.1f}mm; "
            "raise the awning's headroom"
        )

    # Each neck just inboard of the rail, with a bar's half-width of square
    # shoulder between them so the canvas cannot slide along into the corner.
    def clip(foot: Foot) -> float:
        return foot.half - BAR - rig.clip_length / 2.0

    return Frame(
        top=top,
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

    Placed by its midpoint and angle, which is the least fiddly way to lay a
    box along an arbitrary line and works for the crossbars too. Filleted before
    it is turned, while its length still runs along x and the four edges to
    round off are the ones parallel to it.
    """
    length = float(np.hypot(b[0] - a[0], b[1] - a[1]))
    angle = float(np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])))
    bar = Box(length, section, section)
    bar = fillet(bar.edges().filter_by(Axis.X), edge)
    middle = Pos(0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), z)
    return as_part(middle * (Rot(0.0, 0.0, angle) * bar), "a bar")


def _knee(
    at: tuple[float, float, float], angle: float, section: float, along: float, down: float
) -> Part:
    """A triangular knee in a corner a stanchion makes with a bar, pointing along it.

    `at` is the corner -- the stanchion's centreline at the bar's underside --
    and both reaches are measured from there, so a knee overlaps both members
    rather than meeting them on a face. What is left of the right-angled
    triangle is its diagonal, `KNEE_WEB` wide, and the toe at each end of it.

    The toes are what a knee is for. The section it adds goes to nothing there
    instead of stopping in a step, and a bar landing flat on the stanchion would
    put that step back at the one height where the bending is worst.

    Nothing else in it earns its keep. The hole is cut up through the bar's own
    face rather than stopping short of it, so no land is left lying along the
    bar: such a land is a knee's section wide against the bar's full width and
    reads as a second rail hung under the first. Where the diagonal lands on the
    bar instead, the toe is `KNEE_WEB / sin` long, which makes that bond and the
    diagonal it anchors equally strong whatever the angle. The land down the
    stanchion stays, being buried inside the stanchion and costing nothing.

    Laid roof-down nothing in it overhangs, at any angle. The outer face points
    up, so each layer of the triangle is narrower than the one beneath it
    whatever its proportions; the diagonal is anchored on the bar at its toe and
    leans `KNEE_ANGLE` off the stanchion from there. Too small a knee has
    nothing worth taking out and stays solid.

    `section` is the bar's flat, not the bar: see `knee_section`.
    """
    # Insetting the diagonal by `KNEE_WEB` scales the triangle about its right
    # angle, by `shrunk`. The hole's other two edges are the stanchion's land
    # and the bar's face, which it is carried up through.
    shrunk = 1.0 - KNEE_WEB * float(np.hypot(along, down)) / (along * down)
    with BuildPart() as knee:
        with BuildSketch(Plane.XZ.offset(-section / 2.0)):
            Polygon((0.0, 0.0), (along, 0.0), (0.0, -down), align=None)
            if along * shrunk > 2.0 * KNEE_WEB:
                web, over = KNEE_WEB, BAR
                Polygon(
                    (web, over),
                    (along * (shrunk + over / down), over),
                    (web, -down * (shrunk - web / along)),
                    align=None,
                    mode=Mode.SUBTRACT,
                )
        extrude(amount=section)
    assert knee.part is not None
    return as_part(Pos(*at) * (Rot(0.0, 0.0, angle) * knee.part), "a knee")


def _foot_triangle(foot: Foot, side: float) -> Part:
    """The right triangle on a stanchion's inboard face that makes its foot a foot.

    Drawn in the athwartships plane and extruded the stanchion's own width, so
    it is solid rather than a fin: it deepens the section against the frame
    splaying and widens it against the frame racking fore and aft at once.

    The square corner is on the mouth plane. One leg runs inboard along that
    plane, the other runs down the stanchion to the bottom of the socket, and
    the hypotenuse closes them at `FOOT_ANGLE` off the leg. So no length of the
    leg is ever plain bar: the triangle backs the whole of the spigot, and above
    the mouth plane the knee carries it.

    The frame lies roof-down with its feet uppermost, so the hypotenuse narrows
    as the print rises and wants nothing under it. The square corner is a ledge
    the width of the reach -- see `foot_overhang`.
    """
    face = side * (foot.half - BAR / 2.0)
    tip = side * (foot.half - BAR / 2.0 - FOOT_REACH)
    with BuildPart() as block:
        with BuildSketch(Plane.YZ.offset(foot.station - BAR / 2.0)):
            Polygon(
                (face, foot.socket_floor),
                (face, foot.base),
                (tip, foot.base),
                align=None,
            )
        extrude(amount=BAR)
    assert block.part is not None
    return as_part(block.part, "a foot")


def _crossbar(shape: Frame, station: float, edge: float, clip: float | None) -> Part:
    """One crossbar, necked where the canvas clips on, if it does.

    It runs athwartships, which is the way `rig.neck` cuts, so the yard's own
    neck serves here unchanged.
    """
    half = shape.half_at(station)
    bar = _span((station, -half), (station, half), shape.top, BAR, edge)
    if clip is None:
        return as_part(bar, "a crossbar")
    for side in (-1.0, 1.0):
        at = Pos(station, side * clip, shape.top)
        bar = neck(bar, at, BAR, shape.neck, shape.clip_length)
    return as_part(bar, "a crossbar")


def upright_frame(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The frame standing in the boat, in the hull's own coordinates."""
    shape = frame(spec, lines, awning, rig)

    parts = []
    for side in (-1.0, 1.0):
        for a, b in zip(shape.nodes, shape.nodes[1:], strict=False):
            parts.append(
                _span((a[0], side * a[1]), (b[0], side * b[1]), shape.top, BAR, awning.edge)
            )
    necked = {shape.bars[0]: shape.clips[0], shape.bars[-1]: shape.clips[1]}
    parts += [_crossbar(shape, x, awning.edge, necked.get(x)) for x in shape.bars]

    section = knee_section(awning.edge)

    for index, foot in enumerate(shape.feet):
        for side in (-1.0, 1.0):
            # One square column from the bars' tops to the socket's floor. Up to
            # those rather than to the middle plane because the rails and the
            # crossbars both stop at the stanchion's centre, and the stanchion
            # is what fills the corner they leave, so it prints flat to the end.
            #
            # Down into the socket at full section, where it used to step to a
            # round peg at the boss. That step was the weakest thing in the
            # frame -- 3.9mm^3 of section against the stanchion's 6.6, with a sharp
            # shoulder on it where the bending is worst -- and the feet snapped
            # off it. The socket is a square hole now, so there is nothing to
            # step down to, and the stanchion beds on the hole's floor.
            height = shape.top + BAR / 2.0 - foot.socket_floor
            stanchion = Pos(foot.station, side * foot.half, foot.socket_floor + height / 2.0) * Box(
                BAR, BAR, height
            )
            # The foot chamfered, so a frame dropped in a little out of place
            # finds its holes instead of standing on their rims.
            footed = chamfer(stanchion.faces().sort_by(Axis.Z)[0].edges(), FOOT_CHAMFER)
            parts.append(as_part(footed, "a stanchion"))

            # The foot, which carries the whole of the leg below the knee: the
            # socket holds it rather than hinging on it, so the bending peaks
            # again right where the stanchion leaves its boss.
            parts.append(_foot_triangle(foot, side))

            # Knees into every bar the stanchion runs into: the crossbar, inboard, and
            # each rail it has. An end stanchion has one rail, which is why it is the
            # one that wants them. Two knees sharing a bar may cross, which is a
            # union and leaves an X-brace between those two stanchions.
            #
            # The crossbar's runs at full reach even where the canvas clips on: a
            # knee is the bar's flat wide and the cringle's mouth is wider than
            # that, so it passes through the gap the mouth leaves.
            corner = (foot.station, side * foot.half, shape.top - BAR / 2.0)
            free = shape.top - BAR / 2.0 - foot.base
            along, down = knee_reach(free)
            parts.append(_knee(corner, -90.0 * side, section, along, down))
            for other in (index - 1, index + 1):
                if not 0 <= other < len(shape.nodes):
                    continue
                run = shape.nodes[other][0] - foot.station
                reach = shape.nodes[other][1] - foot.half
                angle = float(np.degrees(np.arctan2(side * reach, run)))
                parts.append(_knee(corner, angle, section, along, down))

    whole = parts[0]
    for extra in parts[1:]:
        whole += extra
    return as_part(whole, "the awning frame")


def awning_part(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The frame rolled over, roof down on the bed, ready to print.

    Roof down because the roof is the one flat, connected plane in the part: the
    stanchions then rise off it as plain columns with nothing to bridge. The other way
    up the stanchions print first as thin towers and the whole roof has to span
    between them.
    """
    rolled = Rot(180.0, 0.0, 0.0) * upright_frame(spec, lines, awning, rig)
    return on_the_bed(rolled, "laying the awning down")


def canvas_offset(spec: HullSpec, lines: HullLines, rig: Rig | None = None) -> float:
    """How far the canvas's plate stands from its cringles' axes.

    Far enough that, rigged plate-up, it clears the tops of the crossbars the
    cringles hang from. The sails stand off further, but that is to clear the mast;
    the canvas only has the bars to clear.

    Its patches and bolt rope hang under the plate once it is rigged, so it is
    the thickest of those, not the plate, that has to clear them.
    """
    rig = rig or Rig()
    return BAR / 2.0 + max(rig.patch_thickness, rig.rope_thickness) + TOLERANCE


def canvas(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The awning's canvas, flat on the bed and cringles up, ready to print.

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
        depth=shape.bars[-1] - shape.bars[0],
        radius=shape.neck,
        offset=canvas_offset(spec, lines, rig),
        edge=tuple((middle - foot.station, foot.half - inset) for foot in shape.feet[1:-1]),
    )


def rigged_canvas(spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None) -> Part:
    """The canvas clipped onto the frame, in the hull's own coordinates.

    Turned end for end and upside down at once -- a half turn about y -- so the
    plate is on top, the cringles hang under it with their mouths facing down onto
    the necks, and the wider foot goes forward, where the frame is wider.
    """
    rig = rig or Rig()
    shape = frame(spec, lines, awning, rig)
    middle = 0.5 * (shape.bars[0] + shape.bars[-1])
    turned = Rot(0.0, 180.0, 0.0) * canvas(spec, lines, awning, rig)
    return Pos(middle, 0.0, shape.top + canvas_offset(spec, lines, rig)) * turned


def fit_awning(
    hull: Part, spec: HullSpec, lines: HullLines, awning: Awning, rig: Rig | None = None
) -> Part:
    """Add the bosses to the decks and bore the sockets.

    The bosses stand the sockets up off the decks, and that is the only
    direction a socket can grow in. A deck is solid down to the outside of the
    hull, so there is no bilge under one to reach; what a deeper hole runs into
    is the side, which closes in as it falls while the stanchions stand close to
    it. See `SIDE_PLANKING`, which is checked here. In a boss, the extra depth is
    above the deck instead, where the hull is wider, and the planking outboard
    of the hole is untouched.

    A pair standing on a bench gets its boss on the seat, so the bench has to be
    fitted first.

    The holes are square, like the stanchions: a round one needed the stanchion to step down
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
        if foot.socket_floor - foot.bottom < BOTTOM_PLANKING:
            raise RuntimeError(
                f"the socket at {foot.station:.0f}mm leaves only "
                f"{foot.socket_floor - foot.bottom:.2f}mm of hull under it"
            )
        # The planking left outboard of it, offset perpendicular to the side the
        # way the hull measures its own planking. Taken at the socket's floor, which
        # is where the side has closed in the furthest.
        room = at.inside(foot.station, foot.socket_floor, SIDE_PLANKING)
        if foot.half + bore / 2.0 > room:
            raise RuntimeError(
                f"the socket at {foot.station:.0f}mm reaches "
                f"{foot.half + bore / 2.0 - room:.2f}mm past the {SIDE_PLANKING}mm of planking it "
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
            # The channel inboard of the bore that lets the foot's triangle down
            # past the boss. Prismatic, so the frame still lifts straight out
            # though the triangle inside it tapers, and the socket's own depth,
            # since the triangle runs all the way to the bottom.
            run = FOOT_REACH
            deep = SOCKET_DEPTH + 1.0
            edge = foot.half - bore / 2.0
            channel = Pos(
                foot.station,
                side * (edge - run / 2.0),
                foot.base + 1.0 - deep / 2.0,
            ) * Box(bore, run, deep)
            fitted = as_part(fitted - hole - mouth - channel, "boring an awning socket")
    return fitted
