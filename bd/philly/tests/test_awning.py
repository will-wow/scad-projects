"""The awning frame, its canvas, and the sockets it drops into.

Two things here are worth more than the rest. The canvas has to clip onto the
frame's necks, which are a dimension owned by rig.py -- so that is checked
against the canvas's own eyes rather than against a number copied out of it.
And a socket bored into a deck is bored into the bottom of the hull, which
would leak a boat that floats perfectly well in every other respect.
"""

from __future__ import annotations

import os

import pytest
from build123d import Vector

os.environ.setdefault("PREVIEW", "1")

import awning as awnings  # noqa: E402
import rig as rigging  # noqa: E402
from awning import BAR, BOSS_HEIGHT, FLOOR, SOCKET_DEPTH, Awning, frame  # noqa: E402
from hull import Deck, HullSpec, build  # noqa: E402
from main import AWNING, HULL, RIG  # noqa: E402


@pytest.fixture(scope="module")
def shape(lines):
    return frame(HULL, lines, AWNING, RIG)


@pytest.fixture(scope="module")
def part(lines):
    """Print-ready: rolled over, roof on the bed."""
    return awnings.awning_part(HULL, lines, AWNING, RIG)


class TestFrame:
    def test_the_frame_is_one_solid(self, part):
        assert part.is_valid
        assert len(part.solids()) == 1

    def test_every_member_is_thick_enough_to_handle(self):
        """The user's floor, and the reason the bars are square rather than round."""
        assert BAR >= 3.0

    def test_the_roof_is_planar(self, shape, lines):
        """Which is what lets it print roof-down with nothing to support.

        The sheer rises toward the transom under the awning; the legs absorb that instead
        of the roof following it.
        """
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        box = upright.bounding_box()
        assert pytest.approx(shape.roof + BAR / 2.0, abs=1e-6) == box.max.Z
        for station in shape.bars:
            at = Vector(float(station), 0.0, shape.roof)
            assert upright.is_inside(at), f"no roof at {station:.0f}mm"

    def test_it_prints_roof_down_on_the_bed(self, part, shape):
        """Roof down because the roof is the one flat connected plane: the legs
        then rise off it as plain columns with nothing to bridge."""
        assert pytest.approx(0.0, abs=1e-6) == part.bounding_box().min.Z
        for station in shape.bars:
            at = Vector(float(station), 0.0, 0.15)
            assert part.is_inside(at), f"the crossbar at {station:.0f}mm is off the bed"

    def test_the_legs_stand_on_the_decks(self, shape):
        for foot in shape.feet:
            assert foot.deck > 0.0
            assert foot.base - foot.deck == pytest.approx(BOSS_HEIGHT, abs=1e-9)

    def test_a_leg_over_open_bilge_is_refused(self, lines):
        """There would be nothing to bore a socket into."""
        spec = HullSpec(stations=8, decks=(Deck(0.0, 0.30, 0.5),), bulge=HULL.bulge)
        with pytest.raises(ValueError, match="open bilge"):
            frame(spec, lines, Awning(legs=(0.40, 0.80)), RIG)

    def test_legs_out_of_order_are_refused(self):
        with pytest.raises(ValueError, match="not in order"):
            Awning(legs=(0.60, 0.40))

    def test_the_frame_ends_at_its_legs(self, shape):
        """So both ends are closed by a crossbar standing on something, rather
        than rails running on past the last legs with nothing across them."""
        stations = [foot.station for foot in shape.feet]
        assert [n[0] for n in shape.nodes] == stations
        assert list(shape.bars) == stations

    def test_there_is_a_crossbar_over_every_pair_of_legs(self, lines, shape):
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        for foot in shape.feet:
            at = Vector(foot.station, 0.0, shape.roof)
            assert upright.is_inside(at), f"no crossbar over the legs at {foot.station:.0f}mm"

    def test_the_corners_are_filled_to_the_roof(self, lines, shape):
        """The rails and crossbars stop at the leg's centre; the leg has to run
        up to their tops, or each end corner prints with a notch in the roof."""
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        top = shape.roof + BAR / 2.0 - 0.1
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
        """Each eye's bore is where a neck is: hollow on the neck's axis, with
        the eye's ring around it."""
        for station, clip in zip((shape.bars[0], shape.bars[-1]), shape.clips, strict=True):
            for side in (-1.0, 1.0):
                axis = Vector(station, side * clip, shape.roof)
                ring = Vector(station, side * clip, shape.roof + shape.neck + 0.8)
                assert not rigged.is_inside(axis), "the bore is not over the neck"
                assert rigged.is_inside(ring), f"no eye at {station:.0f}mm"

    def test_only_the_end_crossbars_are_necked(self, lines, shape):
        """Just under the square bar's top face: air over a neck, bar elsewhere.

        The middle bars are probed at the aft neck's offset, which is the
        narrowest and so lies on every bar."""
        upright = awnings.upright_frame(HULL, lines, AWNING, RIG)
        just_under = shape.roof + shape.neck + 0.2
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
        assert shape.roof + BAR / 2.0 + RIG.sail_thickness < rigged.bounding_box().max.Z
        middle = Vector(0.5 * (shape.bars[0] + shape.bars[-1]), 0.0, shape.roof + BAR / 2.0)
        assert not rigged.is_inside(middle), "the plate is sitting in the bars"

    def test_the_necks_are_what_the_eyes_were_cut_for(self, shape, lines):
        """Taken from rig.neck_radius, not copied."""
        assert shape.neck == pytest.approx(rigging.neck_radius(HULL, lines, RIG), abs=1e-9)

    def test_an_eye_clips_over_a_neck_and_holds(self, shape):
        bore = shape.neck + rigging.TOLERANCE
        assert bore > shape.neck, "the eye would not go over the neck"
        assert RIG.mouth * 2.0 * shape.neck < 2.0 * shape.neck, "the eye would slip off"


class TestSockets:
    @pytest.fixture(scope="class")
    def fitted(self, lines):
        return awnings.fit_awning(build(HULL, lines), HULL, lines, AWNING, RIG)

    def test_no_socket_comes_near_the_outside_of_the_hull(self, shape):
        """A deck is solid down to the outside of the hull, so a socket's floor
        is the boat's bottom. The bosses exist to keep the hole out of it."""
        for foot in shape.feet:
            left = foot.socket_floor - foot.bottom
            assert left >= FLOOR, (
                f"only {left:.2f}mm of hull under the socket at {foot.station:.0f}"
            )

    def test_the_sockets_are_bored_and_the_bosses_are_solid(self, fitted, shape):
        for foot in shape.feet:
            for side in (-1.0, 1.0):
                bore = Vector(foot.station, side * foot.half, foot.base - SOCKET_DEPTH / 2.0)
                beside = Vector(foot.station, side * foot.half + BAR, foot.deck + 1.0)
                assert not fitted.is_inside(bore), "the socket was not bored"
                assert fitted.is_inside(beside), "there is no boss around the socket"

    def test_fitting_the_awning_leaves_one_solid_no_wider_than_before(self, fitted, lines):
        assert fitted.is_valid
        assert len(fitted.solids()) == 1
        bare = build(HULL, lines).bounding_box()
        assert pytest.approx(bare.max.Y, abs=1e-6) == fitted.bounding_box().max.Y

    def test_a_peg_fits_its_socket_with_clearance(self):
        """Loose enough to lift out, which is the point of the whole part."""
        assert (
            pytest.approx(rigging.TOLERANCE, abs=1e-9)
            == (BAR + 2.0 * rigging.TOLERANCE) / 2.0 - BAR / 2.0
        )
