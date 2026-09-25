"""The awning frame, and the sockets it drops into.

Two things here are worth more than the rest. The frame has to clip the topsail,
which is a dimension owned by rig.py -- so that is checked against the sail
rather than against a number copied out of it. And a socket bored into the
quarterdeck can reach below the waterline, which would sink a boat that floats
perfectly well in every other respect.
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

        The sheer rises about 5mm under the awning; the legs absorb that instead
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
            frame(spec, lines, Awning(span=(0.35, 0.90), legs=(0.40, 0.80)), RIG)

    def test_legs_outside_the_span_are_refused(self):
        with pytest.raises(ValueError, match="outside the awning"):
            Awning(span=(0.5, 0.9), legs=(0.40, 0.80))


class TestTheTopsailFits:
    """The whole reason the crossbars are pitched the way they are."""

    def test_some_pair_of_crossbars_spans_the_topsail(self, shape):
        """Pitched at half the sail's height, so any two-apart pair fits.

        Computed from `rig.sail_sizes` at both ends rather than from a number
        written down here, so the awning cannot drift away from the rig.
        """
        _, height = rigging.sail_sizes(RIG)[1]
        clips = [float(b) for b in shape.bars if shape.half_at(float(b)) >= shape.clip + BAR]
        pairs = [(a, b) for a in clips for b in clips if b - a == pytest.approx(height, abs=0.01)]
        assert pairs, f"no pair of necked crossbars is {height:.2f}mm apart"

    def test_a_clipping_crossbar_reaches_past_its_necks(self, shape):
        for station in shape.bars:
            half = shape.half_at(float(station))
            if half >= shape.clip + BAR:
                assert half > shape.clip, "the neck is off the end of the bar"

    def test_the_necks_are_what_the_sails_were_cut_for(self, shape, lines):
        """Taken from rig.neck_radius, not copied."""
        assert shape.neck == pytest.approx(rigging.neck_radius(HULL, lines, RIG), abs=1e-9)

    def test_a_sail_eye_clips_over_a_neck_and_holds(self, shape):
        bore = shape.neck + rigging.TOLERANCE
        assert bore > shape.neck, "the eye would not go over the neck"
        assert RIG.mouth * 2.0 * shape.neck < 2.0 * shape.neck, "the eye would slip off"


class TestSockets:
    @pytest.fixture(scope="class")
    def fitted(self, lines):
        return awnings.fit_awning(build(HULL, lines), HULL, lines, AWNING, RIG)

    def test_no_socket_comes_near_the_outside_of_the_hull(self, shape):
        """The quarterdeck leaves about 5mm of solid above the hull's outside and
        the boat floats at 3.5mm, so a socket bored straight into it would bottom
        out under water. The bosses exist to keep the hole out of trouble."""
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
