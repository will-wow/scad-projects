"""The awning frame, its canvas, and the sockets it drops into.

Two things here are worth more than the rest. The canvas has to clip onto the
frame's necks, which are a dimension owned by rig.py -- so that is checked
against the canvas's own cringles rather than against a number copied out of it.
And a socket bored into a deck is bored into the bottom of the hull, which
would leak a boat that floats perfectly well in every other respect.
"""

from __future__ import annotations

import math
import os
from dataclasses import replace

import pytest
from build123d import Vector

os.environ.setdefault("PREVIEW", "1")

import awning as awnings  # noqa: E402
import details  # noqa: E402
import rig as rigging  # noqa: E402
from awning import (  # noqa: E402
    BAR,
    BOSS,
    BOSS_ROUND,
    BOTTOM_PLANKING,
    FOOT_ANGLE,
    FOOT_CHAMFER,
    FOOT_RISE,
    FOOT_TAPER,
    FOOT_TOE,
    KNEE_ANGLE,
    KNEE_CLEAR,
    KNEE_WEB,
    MOUTH_CHAMFER,
    SIDE_PLANKING,
    SOCKET_DEPTH,
    SOCKET_DROP,
    Awning,
    frame,
    knee_reach,
    knee_section,
)
from hull import Deck, HullSpec, build, inner_half_width  # noqa: E402
from main import AWNING, HULL, RIG  # noqa: E402


@pytest.fixture(scope="module")
def shape(lines):
    return frame(HULL, lines, AWNING, RIG)


@pytest.fixture(scope="module")
def part(lines):
    """Print-ready: rolled over, roof on the bed."""
    return awnings.awning_part(HULL, lines, AWNING, RIG)


@pytest.fixture(scope="module")
def upright(lines):
    """Standing in the boat, which is where its corners are easiest to reason about."""
    return awnings.upright_frame(HULL, lines, AWNING, RIG)


class TestFrame:
    def test_the_frame_is_one_solid(self, part):
        assert part.is_valid
        assert len(part.solids()) == 1

    def test_every_member_is_thick_enough_to_handle(self):
        """The user's floor, and the reason the bars are square rather than round."""
        assert BAR >= 3.0

    def test_the_roof_is_planar(self, shape, lines):
        """Which is what lets it print roof-down with nothing to support.

        The sheer rises toward the transom under the awning; the stanchions absorb that instead
        of the roof following it.
        """
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        box = upright.bounding_box()
        assert pytest.approx(shape.top + BAR / 2.0, abs=1e-6) == box.max.Z
        for station in shape.bars:
            at = Vector(float(station), 0.0, shape.top)
            assert upright.is_inside(at), f"no roof at {station:.0f}mm"

    def test_it_prints_roof_down_on_the_bed(self, part, shape):
        """Roof down because the roof is the one flat connected plane: the stanchions
        then rise off it as plain columns with nothing to bridge."""
        assert pytest.approx(0.0, abs=1e-6) == part.bounding_box().min.Z
        for station in shape.bars:
            at = Vector(float(station), 0.0, 0.15)
            assert part.is_inside(at), f"the crossbar at {station:.0f}mm is off the bed"

    def test_the_legs_stand_on_the_decks(self, shape):
        for foot in shape.feet:
            assert foot.deck > 0.0
            assert foot.step >= foot.deck, "a pair steps on its deck or on a bench over it"
            assert foot.base - foot.socket_floor == pytest.approx(SOCKET_DEPTH, abs=1e-9)

    def test_a_leg_over_open_bilge_is_refused(self, lines):
        """There would be nothing to bore a socket into."""
        spec = HullSpec(stations=8, decks=(Deck(0.0, 0.30, 0.5),), bulge=HULL.bulge)
        with pytest.raises(ValueError, match="open bilge"):
            frame(spec, lines, Awning(stanchions=(0.40, 0.80)), RIG)

    def test_legs_out_of_order_are_refused(self):
        with pytest.raises(ValueError, match="not in order"):
            Awning(stanchions=(0.60, 0.40))

    def test_the_frame_ends_at_its_legs(self, shape):
        """So both ends are closed by a crossbar standing on something, rather
        than rails running on past the last stanchions with nothing across them."""
        stations = [foot.station for foot in shape.feet]
        assert [n[0] for n in shape.nodes] == stations
        assert list(shape.bars) == stations

    def test_there_is_a_crossbar_over_every_pair_of_legs(self, lines, shape):
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        for foot in shape.feet:
            at = Vector(foot.station, 0.0, shape.top)
            assert upright.is_inside(at), f"no crossbar over the stanchions at {foot.station:.0f}mm"

    def test_every_leg_is_kneed_into_the_bars_it_meets(self, upright, shape):
        """The stanchion's root under the bars is what broke when the boat was dropped.
        Every corner gets a triangle: inboard along the crossbar, and along each
        rail the stanchion has. An end stanchion has one rail, which is why it is the stanchion
        that wants them.

        Probed in the middle of the diagonal, which outside the stanchion's own
        square is the whole of a knee: the corner itself is filled by the
        stanchion, which runs up through the bars to the roof.
        """
        for index, foot in enumerate(shape.feet):
            ends = index in (0, len(shape.feet) - 1)
            beside = [shape.nodes[i] for i in (index - 1, index + 1) if 0 <= i < len(shape.feet)]
            reach, drop = knee_reach(shape.top - BAR / 2.0 - foot.base)
            # Half way across the diagonal, between the hole and the outer face.
            towards = 0.5 * (2.0 - KNEE_WEB * math.hypot(reach, drop) / (reach * drop))
            for side in (-1.0, 1.0):
                corner = Vector(foot.station, side * foot.half, shape.top - BAR / 2.0)
                along = [Vector(0.0, -side, 0.0)] + [
                    Vector(x - foot.station, side * (half - foot.half), 0.0) for x, half in beside
                ]
                assert len(along) == (2 if ends else 3)
                for bar in along:
                    at = corner + bar.normalized() * (towards * reach / 2.0)
                    at -= Vector(0.0, 0.0, towards * drop / 2.0)
                    assert upright.is_inside(at), f"a bar at {foot.station:.0f}mm has no knee"

    def test_a_knee_sits_on_the_flat_of_its_bar(self):
        """As wide as the bar, a knee stood its outer edge on the bar's rounded
        corner and left a lip hanging over nothing."""
        assert knee_section(AWNING.edge) == pytest.approx(BAR - 2.0 * AWNING.edge, abs=1e-9)

    def test_knees_cross_inside_their_leg_rather_than_in_the_air(self, shape):
        """Two slabs of half-width w meeting at an angle t overlap out to
        w / sin(t/2) from the stanchion's centre. Past the stanchion's half-diagonal that
        crossing is in open air, and the two hypotenuses leave a spike where they
        cut each other. The tightest angle here is 64 degrees, where a rail meets
        the crossbar on the trapezoid stretch aft.
        """
        reach = knee_section(AWNING.edge) / 2.0
        buried = BAR / 2.0 * math.sqrt(2.0)
        nodes = list(shape.nodes)
        for index, foot in enumerate(shape.feet):
            for side in (-1.0, 1.0):
                beside = [nodes[i] for i in (index - 1, index + 1) if 0 <= i < len(nodes)]
                bearings = sorted(
                    [-90.0 * side]
                    + [
                        math.degrees(math.atan2(side * (h - foot.half), x - foot.station))
                        for x, h in beside
                    ]
                )
                for lower, upper in zip(bearings, bearings[1:], strict=False):
                    gap = upper - lower
                    crossing = reach / math.sin(math.radians(gap) / 2.0)
                    assert crossing <= buried, (
                        f"knees {gap:.0f} degrees apart at {foot.station:.0f}mm "
                        f"cross {crossing:.2f}mm out, past the stanchion's {buried:.2f}mm"
                    )

    def _crossbar_knee(self, shape, index: int):
        """A middle pair's inboard knee: the one that runs straight down -y, so a
        probe needs no bearing, and the one that gets its full reach."""
        foot = shape.feet[index]
        along, down = knee_reach(shape.top - BAR / 2.0 - foot.base)
        corner = (foot.station, foot.half, shape.top - BAR / 2.0)

        def on_the_diagonal(towards: float) -> Vector:
            """A point `towards` of the way from the corner to the diagonal."""
            return Vector(
                corner[0], corner[1] - towards * along / 2.0, corner[2] - towards * down / 2.0
            )

        return foot, along, down, on_the_diagonal

    def test_a_knee_is_a_taper_rather_than_a_block(self, upright, shape):
        """Material inside its diagonal and air outside it, so the section a knee
        adds to the stanchion goes to nothing at the toe instead of stopping in a
        step. That taper is most of what a knee buys."""
        _, _, _, on_the_diagonal = self._crossbar_knee(shape, 2)
        for towards, solid in ((0.9, True), (1.1, False)):
            assert upright.is_inside(on_the_diagonal(towards)) == solid, (
                f"the diagonal is in the wrong place at {towards:.1f} of the way out"
            )

    def test_a_knee_is_a_diagonal_and_two_toes(self, upright, shape):
        """The middle of a solid knee does little but hide the boat, so it is cut
        out. What has to stay is the diagonal and the taper at each toe -- which
        is what a bar landing flat on the stanchion would throw away.

        Walked out from the right-angled corner toward the diagonal: the land
        buried in the stanchion, then the hole, then the diagonal.
        """
        _, along, down, on_the_diagonal = self._crossbar_knee(shape, 2)
        shrunk = 1.0 - KNEE_WEB * math.hypot(along, down) / (along * down)
        enters = 2.0 * KNEE_WEB / along
        assert 0.0 < enters < shrunk < 1.0, "the hole is not inside the knee"
        for towards, solid in (
            (0.5 * enters, True),
            (0.5 * (enters + shrunk), False),
            (0.5 * (shrunk + 1.0), True),
        ):
            assert upright.is_inside(on_the_diagonal(towards)) == solid, (
                f"the knee is wrong {towards:.2f} of the way out to its diagonal"
            )

    def test_no_knee_leaves_a_land_lying_along_its_bar(self, upright, shape):
        """The hole is cut up through the bar's own face, so what meets the bar
        is the diagonal's toe and nothing else. A land left along there is a
        knee's section wide against the bar's full width, and a row of them
        reads as a second rail hung under the first.

        Probed just under the bar, between the stanchion and the toe.
        """
        foot, along, down, _ = self._crossbar_knee(shape, 2)
        shrunk = 1.0 - KNEE_WEB * math.hypot(along, down) / (along * down)
        under = shape.top - BAR / 2.0 - KNEE_WEB / 2.0
        for name, out in (
            ("mid-reach", 0.5 * along),
            ("just inboard of the toe", along * shrunk - KNEE_WEB),
        ):
            at = Vector(foot.station, foot.half - out, under)
            assert not upright.is_inside(at), f"the knee lands on its bar {name}"
        # The toe itself is still there, and tapers.
        toe = Vector(foot.station, foot.half - 0.5 * along * (1.0 + shrunk), under)
        assert upright.is_inside(toe), "the knee has no toe on its bar"

    def test_a_knee_braces_the_stanchion_down_to_its_boss(self, shape):
        """The taper ends `KNEE_CLEAR` above the boss, so the whole of a
        stanchion is braced rather than just its head."""
        for foot in shape.feet:
            free = shape.top - BAR / 2.0 - foot.base
            along, down = knee_reach(free)
            # A knee stops adding section where its profile meets the stanchion's
            # face, half a bar in from the centreline.
            toe = down * (1.0 - BAR / (2.0 * along))
            assert toe == pytest.approx(free - KNEE_CLEAR, abs=0.01), (
                f"the knee at {foot.station:.0f}mm tapers out {free - toe:.2f}mm above its boss"
            )
            assert math.degrees(math.atan2(along, down)) == pytest.approx(KNEE_ANGLE, abs=1e-9)

    def test_a_foot_is_the_bar_wide_and_no_wider(self, upright, shape):
        """Nothing stands proud of the leg but the foot, and that only inboard.
        The lead-in round the mouth is the hull's alone.
        """
        for foot in shape.feet:
            for under in (0.0, 1.0, 0.5 * SOCKET_DEPTH):
                z = foot.base - under
                for off, solid in ((-0.05, True), (0.05, False)):
                    at = Vector(foot.station, foot.half + BAR / 2.0 + off, z)
                    assert upright.is_inside(at) == solid, (
                        f"the foot at {foot.station:.0f}mm is not the bar's width "
                        f"outboard, {under:.2f} under its mouth"
                    )
                for off, solid in ((-0.05, True), (0.05, False)):
                    at = Vector(foot.station + BAR / 2.0 + off, foot.half, z)
                    assert upright.is_inside(at) == solid, (
                        f"the foot at {foot.station:.0f}mm is not the bar's width "
                        f"fore and aft, {under:.2f} under its mouth"
                    )

    def test_no_length_of_a_leg_is_left_plain_bar(self, upright, shape):
        """What snaps is a straight stick, so there is not one anywhere on a leg.

        Walked the whole length of it, from the bottom of the socket to the
        apex, measuring how far the foot stands in from the stanchion's inboard
        face. At and below the mouth plane it is the full `FOOT_TOE`; above the
        knuckle it tapers away at `FOOT_ANGLE`, and by then the knee has taken
        over. The knee may add more; it may not add less.
        """
        assert FOOT_RISE > KNEE_CLEAR, "the knee does not reach the foot"
        assert FOOT_TAPER < FOOT_RISE, "the taper runs below the mouth plane"
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                face = foot.half - BAR / 2.0
                for up in (0.05, 0.25 * FOOT_RISE, 0.5 * FOOT_RISE, 0.75 * FOOT_RISE):
                    want = min(FOOT_TOE, (FOOT_RISE - up) * math.tan(math.radians(FOOT_ANGLE)))
                    at = Vector(foot.station, side * (face - want + 0.1), foot.base + up)
                    assert upright.is_inside(at), (
                        f"the foot at {foot.station:.0f}mm is not {want:.2f}mm in, "
                        f"{up:.2f}mm up its leg"
                    )
                # And at the mouth plane and below it, all the way to the bottom
                # of the socket, it is the toe's full width and prismatic.
                buried = foot.base - foot.socket_floor
                for down in (0.0, 0.3 * buried, 0.7 * buried, buried - FOOT_CHAMFER - 0.1):
                    at = Vector(foot.station, side * (face - FOOT_TOE + 0.1), foot.base - down)
                    assert upright.is_inside(at), (
                        f"the foot at {foot.station:.0f}mm is not {FOOT_TOE}mm in, "
                        f"{down:.2f}mm below its mouth"
                    )

    def test_the_bottom_of_a_stanchion_is_wider_than_its_bar(self, upright, shape):
        """The one that stops this coming back. Every time a leg has snapped it
        has snapped where the section was the bar's own 3.4mm square, and the
        bottom of the leg is the last place that was still true: the foot used
        to stop on the deck, which left the two pairs on the benches 6.7mm of
        plain stick below it, because a seat stands 6.2mm up while the socket
        still reaches 8.5mm down.

        Measured athwartships across the bottom of each leg, above the lead-in
        chamfer, by walking inboard from the stanchion's own face.
        """
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                face = foot.half - BAR / 2.0
                z = foot.socket_floor + FOOT_CHAMFER + 0.1
                reach = 0.0
                for step in range(1, int(FOOT_TOE / 0.05) + 4):
                    at = Vector(foot.station, side * (face - step * 0.05), z)
                    if not upright.is_inside(at):
                        break
                    reach = step * 0.05
                assert reach == pytest.approx(FOOT_TOE, abs=0.06), (
                    f"the bottom of the leg at {foot.station:.0f}mm is "
                    f"{BAR + reach:.2f}mm across, not {BAR + FOOT_TOE:.2f}"
                )
                assert reach >= BAR / 2.0, (
                    "the bottom of the leg is barely wider than the bar it is made of"
                )

    def test_the_corners_are_filled_to_the_roof(self, lines, shape):
        """The rails and crossbars stop at the stanchion's centre; the stanchion has to run
        up to their tops, or each end corner prints with a notch in the roof."""
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        top = shape.top + BAR / 2.0 - 0.1
        for foot in (shape.feet[0], shape.feet[-1]):
            outward = -1.0 if foot is shape.feet[0] else 1.0
            corner = Vector(foot.station + outward * BAR / 4.0, foot.half + BAR / 4.0, top)
            assert upright.is_inside(corner), f"the corner at {foot.station:.0f}mm is notched"


class TestCanvas:
    """The awning's own canvas, clipped to the end crossbars."""

    @pytest.fixture(scope="class")
    def flat(self, lines):
        return awnings.canvas(HULL, lines, AWNING, RIG)

    @pytest.fixture(scope="class")
    def rigged(self, lines):
        return awnings.rigged_canvas(HULL, lines, AWNING, RIG)

    def test_it_is_one_thin_solid_lying_flat(self, flat):
        assert flat.is_valid
        assert len(flat.solids()) == 1
        assert pytest.approx(0.0, abs=1e-6) == flat.bounding_box().min.Z

    def test_its_eyes_sit_on_the_end_crossbars_necks(self, rigged, shape):
        """Each cringle's bore is where a neck is: hollow on the neck's axis, with
        the cringle's ring around it."""
        for station, clip in zip((shape.bars[0], shape.bars[-1]), shape.clips, strict=True):
            for side in (-1.0, 1.0):
                axis = Vector(station, side * clip, shape.top)
                ring = Vector(station, side * clip, shape.top + shape.neck + 0.8)
                assert not rigged.is_inside(axis), "the bore is not over the neck"
                assert rigged.is_inside(ring), f"no cringle at {station:.0f}mm"

    def test_only_the_end_crossbars_are_necked(self, lines, shape):
        """Just under the square bar's top face: air over a neck, bar elsewhere.

        The middle bars are probed at the aft neck's offset, which is the
        narrowest and so lies on every bar."""
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        just_under = shape.top + shape.neck + 0.2
        ends = {shape.bars[0]: shape.clips[0], shape.bars[-1]: shape.clips[1]}
        for station in shape.bars:
            necked = station in ends
            at = Vector(station, ends.get(station, shape.clips[1]), just_under)
            assert upright.is_inside(at) != necked, f"the bar at {station:.0f}mm"

    def test_a_neck_stays_inside_its_rail(self, shape):
        """A square shoulder between the neck and the rail, so the canvas cannot
        slide along into the corner."""
        for foot, clip in zip((shape.feet[0], shape.feet[-1]), shape.clips, strict=True):
            assert clip + shape.clip_length / 2.0 < foot.half - BAR / 2.0

    def test_the_plate_clears_the_bars(self, rigged, shape):
        assert shape.top + BAR / 2.0 + RIG.sail_thickness < rigged.bounding_box().max.Z
        middle = Vector(0.5 * (shape.bars[0] + shape.bars[-1]), 0.0, shape.top + BAR / 2.0)
        assert not rigged.is_inside(middle), "the plate is sitting in the bars"

    def test_a_knee_passes_through_the_cringles_mouth(self, upright, rigged, shape):
        """The end crossbars are necked for the canvas, and a knee there used to
        be cut back to the neck on the grounds that the cringle comes down round
        it. It does not have to be. A knee is the bar's flat wide and the
        cringle's mouth is wider than that, so the knee runs through the gap the
        mouth leaves and the two never meet -- which is worth a test, because it
        is the only thing letting the end pairs have a brace at all."""
        mouth = RIG.mouth * 2.0 * shape.neck
        assert knee_section(AWNING.edge) < mouth, "a knee is too fat for the mouth"
        assert (upright & rigged).volume < 1e-6

    def test_the_necks_are_what_the_eyes_were_cut_for(self, shape, lines):
        """Taken from rig.neck_radius, not copied."""
        assert shape.neck == pytest.approx(rigging.neck_radius(HULL, lines, RIG), abs=1e-9)

    def test_an_eye_clips_over_a_neck_and_holds(self, shape):
        bore = shape.neck + rigging.TOLERANCE
        assert bore > shape.neck, "the cringle would not go over the neck"
        assert RIG.mouth * 2.0 * shape.neck < 2.0 * shape.neck, "the cringle would slip off"


class TestSockets:
    @pytest.fixture(scope="class")
    def fitted(self, built_hull, lines):
        """With the joinery first, as it prints: the aft pairs stand on the benches."""
        joined = details.fit_details(built_hull, HULL, lines)
        return awnings.fit_awning(joined, HULL, lines, AWNING, RIG)

    def test_no_socket_comes_near_the_outside_of_the_hull(self, shape):
        """A deck is solid down to the outside of the hull, so a socket's floor
        is the boat's bottom. The bosses exist to keep the hole out of it."""
        for foot in shape.feet:
            left = foot.socket_floor - foot.bottom
            assert left >= BOTTOM_PLANKING, (
                f"only {left:.2f}mm of hull under the socket at {foot.station:.0f}"
            )

    def test_the_sockets_are_bored_and_the_bosses_are_solid(self, fitted, shape):
        """Probed fore of the hole rather than beside it: a boss is open toward
        the centreline, where the foot's wedge comes through it."""
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                bore = Vector(foot.station, side * foot.half, foot.base - SOCKET_DEPTH / 2.0)
                beside = Vector(foot.station + BOSS / 2.0 - 0.3, side * foot.half, foot.step + 1.0)
                assert not fitted.is_inside(bore), "the socket was not bored"
                assert fitted.is_inside(beside), "there is no boss around the socket"

    def test_a_socket_mouth_is_chamfered_to_guide_a_leg_in(self, fitted, shape):
        """The hull's half of the lead-in -- the stanchion's foot is chamfered to
        match. Probed just outside the bore: open at the mouth, metal once the
        chamfer has run out below it."""
        bore = BAR + 2.0 * rigging.TOLERANCE
        out = bore / 2.0 + MOUTH_CHAMFER / 2.0
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                flared = Vector(foot.station + out, side * foot.half, foot.base - 0.05)
                straight = Vector(
                    foot.station + out, side * foot.half, foot.base - MOUTH_CHAMFER - 0.5
                )
                assert not fitted.is_inside(flared), (
                    f"the socket at {foot.station:.0f}mm has no chamfered mouth"
                )
                assert fitted.is_inside(straight), "the chamfer runs on down the socket"

    def test_the_mouth_chamfer_leaves_the_boss_a_collar(self):
        """It is cut out of a collar only 1.5mm thick to begin with, which is why
        it is the smaller half of the lead-in."""
        mouth = BAR + 2.0 * rigging.TOLERANCE + 2.0 * MOUTH_CHAMFER
        assert (BOSS - mouth) / 2.0 >= 0.8, "the chamfer eats the boss's collar"
        assert MOUTH_CHAMFER < FOOT_CHAMFER

    def test_nothing_it_adds_stands_outside_the_hull(self, fitted, lines):
        """A boss is wider than its socket and reaches further fore and aft, and
        the side of the boat falls away in plan as well as in section, so a boss
        aft can stand outside the planking and print as a blister.

        The beam will not catch it: that pair stands nowhere near the widest part
        of the boat, so a blister there leaves `max.Y` untouched. The bare hull's
        own outer loft is the only honest judge, and a test can afford to build
        one.
        """
        outline = build(replace(HULL, planking=0.0), lines)
        assert (fitted - outline).volume == pytest.approx(0.0, abs=1e-6)

    def test_a_boss_has_its_upright_corners_rounded(self, fitted, shape):
        """Kinder to a hand and quicker to print, and it buys back a little of
        the room the side of the boat takes away from the after pair."""
        assert 0.0 < BOSS_ROUND < BOSS / 2.0
        # A rounded corner's furthest point along the diagonal, per axis.
        reach = BOSS / 2.0 - BOSS_ROUND * (1.0 - math.sqrt(0.5))
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                # Probed on the inboard corners: the outboard ones are buried in
                # the side of the boat, where everything reads as solid.
                middle = foot.step + foot.boss / 2.0
                corner = Vector(
                    foot.station + reach + 0.1, side * (foot.half - reach - 0.1), middle
                )
                flat = Vector(
                    foot.station + BAR / 2.0 + 0.4,
                    side * (foot.half - BOSS / 2.0 + 0.1),
                    middle,
                )
                assert not fitted.is_inside(corner), "the boss still has a square corner"
                assert fitted.is_inside(flat), "the rounding ate the boss's flat"

    def test_a_socket_is_a_keyhole_bored_the_whole_way_down(self, fitted, shape):
        """The foot runs the full length of the leg, so the slot beside the bore
        is cut to the full depth of it -- clean through a bench rather than
        stopping on the seat, which is what left the pairs standing on them a
        length of plain bar underneath.

        Probed at the toe's own offset, which is the furthest in the slot has to
        reach, at heights taken right through whatever the pair stands on.
        """
        bore = BAR + 2.0 * rigging.TOLERANCE
        for foot in shape.feet:
            deep = foot.base - foot.socket_floor
            for side in (-1.0, 1.0):
                for inboard in (bore / 2.0 + 0.2, BAR / 2.0 + FOOT_TOE - 0.1):
                    for up in (0.1, 0.25 * deep, 0.5 * deep, 0.75 * deep, deep - 0.1):
                        at = Vector(
                            foot.station,
                            side * (foot.half - inboard),
                            foot.socket_floor + up,
                        )
                        assert not fitted.is_inside(at), (
                            f"the slot at {foot.station:.0f}mm is blocked "
                            f"{inboard:.1f}mm in, {up:.1f}mm off its floor"
                        )
                # And the floor is still there to bed the leg on.
                under = Vector(
                    foot.station,
                    side * (foot.half - BAR / 2.0 - FOOT_TOE + 0.1),
                    foot.socket_floor - 0.3,
                )
                assert fitted.is_inside(under), (
                    f"the slot at {foot.station:.0f}mm was bored through its floor"
                )
                # Only the bore's width of it: the boss is whole fore and aft.
                beside = Vector(
                    foot.station + bore / 2.0 + 0.3,
                    side * (foot.half - BOSS / 2.0 + 0.2),
                    foot.step + 0.2,
                )
                assert fitted.is_inside(beside), "the slot is wider than the bore"

    def test_a_leg_and_its_foot_drop_into_the_hull_without_touching(self, fitted, lines):
        """Which is the whole point of the part. Every clearance in it -- the
        bore, the slot beside it, the two halves of the lead-in -- comes down to
        this one measurement."""
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        assert (fitted & upright).volume == pytest.approx(0.0, abs=1e-6)

    def test_fitting_the_awning_leaves_one_solid_no_wider_than_before(self, fitted, built_hull):
        assert fitted.is_valid
        assert len(fitted.solids()) == 1
        bare = built_hull.bounding_box()
        assert pytest.approx(bare.max.Y, abs=1e-6) == fitted.bounding_box().max.Y

    def test_a_leg_fits_its_socket_with_clearance(self):
        """Loose enough to lift out, which is the point of the whole part. The
        stanchion goes in at full section, and its foot with it."""
        assert (
            pytest.approx(rigging.TOLERANCE, abs=1e-9)
            == (BAR + 2.0 * rigging.TOLERANCE) / 2.0 - BAR / 2.0
        )

    def test_a_socket_drops_only_far_enough_to_clear_the_deck(self):
        """Down is the one direction it cannot grow in: every millimetre below
        the deck costs planking beside the hole, since the side closes in as it
        falls and the stanchions stand close to it. The drop is there only so the cut
        does not end on the deck's own face."""
        assert SOCKET_DROP < 1.0, "the socket drops into the side"
        assert SOCKET_DEPTH > BAR, "too little of a stanchion gripped to steady the frame"

    def test_a_bench_gives_its_pair_most_of_their_socket(self, shape):
        """A pair on a bench is socketed through it rather than onto it: the hole
        is bored from the deck like every other, so the bench's own height is
        depth that costs nothing to show. The boss is only what is left over, and
        an 8mm block on the seat becomes a pad."""
        on_bench = [f for f in shape.feet if f.step > f.deck]
        on_deck = [f for f in shape.feet if f.step == f.deck]
        assert on_bench and on_deck, "the frame should have some of each"
        for foot in on_bench:
            assert foot.boss < 0.5 * min(f.boss for f in on_deck), "the bench hides nothing"
            assert foot.boss > 0.0, "the socket has no boss left to bore into"
            assert foot.base - foot.socket_floor == pytest.approx(SOCKET_DEPTH, abs=1e-9)

    def test_a_socket_leaves_planking_outboard_of_it(self, shape, lines):
        """The guard that `fit_awning` enforces, checked against the hull itself.
        Bored 2mm below the deck, as they were, the aft pair left 0.67mm."""
        factor = HULL.length / lines.length
        bore = BAR + 2.0 * rigging.TOLERANCE
        for foot in shape.feet:
            room = factor * inner_half_width(
                lines,
                foot.station / factor,
                SIDE_PLANKING / factor,
                foot.socket_floor / factor,
                HULL.bulge,
            )
            assert foot.half + bore / 2.0 <= room, (
                f"the socket at {foot.station:.0f}mm is too near the planking"
            )

    def test_a_foot_is_chamfered_so_it_finds_its_hole(self, part, shape):
        """So a frame dropped in askew finds its sockets rather than standing on
        their rims. Printed roof down the feet are the last thing laid, so the
        chamfer faces up and costs nothing; the longest stanchion is the one at the top
        of the laid part, which is where this probes.
        """
        foot = min(shape.feet, key=lambda f: f.socket_floor)
        top = part.bounding_box().max.Z
        assert pytest.approx(shape.top + BAR / 2.0 - foot.socket_floor, abs=0.01) == top
        # A tenth off the end, the chamfer has taken all but a tenth off each face.
        edge = BAR / 2.0 - FOOT_CHAMFER + 0.1
        for reach, solid in ((edge - 0.05, True), (edge + 0.05, False)):
            at = Vector(foot.station + reach, foot.half, top - 0.1)
            assert part.is_inside(at) == solid, "the foot's end is not chamfered"
