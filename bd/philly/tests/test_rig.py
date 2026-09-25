"""The mast, its socket, and the sails.

The socket is cut into a hull that has to stay watertight, and the mast, the
yards and the sails have to fit each other without ever being measured against
each other by hand. So these check the fits numerically rather than trusting
that three separate formulas agree.
"""

from __future__ import annotations

import numpy as np
import pytest
from build123d import Vector
from conftest import DECKS, STATIONS

import rig as rigging
from export import write_3mf
from hull import Deck, HullSpec, build
from rig import TOLERANCE, Rig, fit_mast, mast_width, sail_sizes, stand_off, step, yards

SPEC = HullSpec(stations=STATIONS, decks=DECKS)
RIG = Rig()


class TestStep:
    def test_the_mast_stands_in_the_forward_well(self, lines):
        """The station comes from the decks, not from a number in the source."""
        seat = step(SPEC, lines)
        well = 0.5 * (DECKS[0].end + DECKS[1].start)
        assert seat.station == pytest.approx(SPEC.length * well, abs=0.5)

    def test_moving_a_deck_moves_the_mast(self, lines):
        """Which is the whole reason the station is derived rather than written."""
        moved = HullSpec(
            stations=STATIONS,
            decks=(Deck(0.0, 0.10, 0.5), DECKS[1], DECKS[2]),
        )
        assert step(moved, lines).station < step(SPEC, lines).station

    def test_the_bar_sits_one_bar_width_below_the_rail(self, lines):
        seat = step(SPEC, lines)
        factor = SPEC.length / lines.length
        rail = lines.sheer_height.value(seat.station / factor) * factor
        assert rail - seat.bar_top == pytest.approx(seat.bar_size, abs=1e-6)

    def test_a_hull_with_no_well_is_refused(self, lines):
        """A mast socket in the middle of a platform would be nonsense."""
        decked = HullSpec(stations=STATIONS, decks=(Deck(0.0, 1.0, 0.5),))
        with pytest.raises(ValueError, match="no well"):
            step(decked, lines)


class TestFitting:
    @pytest.fixture(scope="class")
    def fitted(self, lines):
        return fit_mast(build(SPEC, lines), SPEC, lines)

    def test_the_fitted_hull_is_one_watertight_solid(self, fitted):
        assert fitted.is_valid
        assert len(fitted.solids()) == 1

    def test_the_bar_does_not_break_out_through_the_side(self, fitted, lines):
        """It is deliberately run into the wall, so this is the check that it
        stops there. Measured at the bar's top, the inside of the hull is at its
        widest over the bar's height, which leaves the bar overlapping into the
        wall lower down -- by less than the wall is thick, or it would show."""
        bare = build(SPEC, lines).bounding_box()
        assert pytest.approx(bare.max.Y, abs=1e-6) == fitted.bounding_box().max.Y
        assert pytest.approx(bare.min.Y, abs=1e-6) == fitted.bounding_box().min.Y

    def test_the_bar_reaches_the_hull_on_both_sides(self, fitted, lines):
        """Probing just inboard of the wall, at the bar's height, off the tube."""
        seat = step(SPEC, lines)
        z = seat.bar_top - seat.bar_size / 2.0
        for side in (-1.0, 1.0):
            at = Vector(seat.station, side * (seat.bar_half_length - 0.2), z)
            assert fitted.is_inside(at), "the bar stops short of the hull"

    def test_the_bore_does_not_pierce_the_bottom(self, fitted, lines):
        """A hole here is a hole in the boat, and the boat is meant to float."""
        seat = step(SPEC, lines)
        below = Vector(seat.station, 0.0, seat.floor - seat.wall / 2.0)
        assert fitted.is_inside(below), "the bore went through the hull's bottom"

    def test_the_bore_is_open_from_the_top(self, fitted, lines):
        seat = step(SPEC, lines)
        for height in (seat.top - 1.0, seat.bar_top, seat.floor + 1.0):
            assert not fitted.is_inside(Vector(seat.station, 0.0, height)), (
                f"the bore is blocked at z={height:.1f}"
            )

    def test_the_tube_wall_is_where_it_should_be(self, fitted, lines):
        seat = step(SPEC, lines)
        z = seat.top - 1.0  # above the rail, so only the tube is up here
        inside = Vector(seat.station, seat.bore_radius + seat.wall / 2.0, z)
        outside = Vector(seat.station, seat.tube_radius + 0.5, z)
        assert fitted.is_inside(inside), "the tube has no wall"
        assert not fitted.is_inside(outside), "the tube is fatter than it claims"

    def test_fitting_the_mast_adds_material(self, fitted, lines):
        assert fitted.volume > build(SPEC, lines).volume


class TestMast:
    @pytest.fixture(scope="class")
    def part(self, lines):
        return rigging.mast(SPEC, lines, RIG)

    def test_the_mast_is_one_solid_of_the_right_length(self, part):
        assert part.is_valid
        assert len(part.solids()) == 1
        assert pytest.approx(RIG.mast_length, abs=0.01) == part.bounding_box().size.X

    def test_the_mast_lies_on_a_flat_not_an_edge(self, part, lines):
        """Six flats, so it can print lying down -- but only if one faces the bed.

        A hexagon is narrower across its flats than across its corners, so this
        also catches the shaft being rotated the wrong way: on its corners the
        part would measure the wider figure.
        """
        width = mast_width(SPEC, lines)
        box = part.bounding_box()
        assert pytest.approx(width, abs=0.01) == box.size.Z
        assert pytest.approx(0.0, abs=1e-6) == box.min.Z, "not sitting on the bed"
        assert width < 2.0 * width / np.sqrt(3.0)  # flats really are the narrow way

    def test_the_round_base_fits_the_bore_with_clearance(self, lines):
        seat = step(SPEC, lines)
        assert seat.bore_radius - mast_width(SPEC, lines) / 2.0 == pytest.approx(
            TOLERANCE, abs=1e-6
        )

    def test_the_round_base_outlasts_the_tube(self, lines):
        """So the hexagon never reaches the bore and jams part way down."""
        seat = step(SPEC, lines)
        base = seat.socket + TOLERANCE
        assert base > seat.socket

    def test_the_hexagon_cannot_enter_the_bore(self, lines):
        """It is wider across the corners than the hole, which is what seats it."""
        seat = step(SPEC, lines)
        across_corners = 2.0 * mast_width(SPEC, lines) / np.sqrt(3.0)
        assert across_corners / 2.0 > seat.bore_radius

    def test_the_yards_lie_on_the_bed(self, part):
        """The reason they are square, and the thing that made them so.

        Round yards were 2.5mm cylinders on the mast's centreline, which left
        them hanging 1.25mm clear of the bed for the whole 72mm of their length
        with nothing underneath. Square and mast-width, they rest on it.
        """
        for height, half in yards(RIG):
            for fraction in (0.2, 0.5, 0.8):
                at = Vector(height, half * fraction, 0.15)
                assert part.is_inside(at), f"the yard at {height:.0f}mm is off the bed"

    def test_a_clip_neck_is_a_short_bridge_rather_than_an_overhang(self, part):
        """Turned down to a neck, so it does leave the bed -- but only over the
        clip's length, and with a square shoulder holding each end."""
        for height, half in yards(RIG):
            neck = half * (1.0 - RIG.clip_inset)
            assert not part.is_inside(Vector(height, neck, 0.15)), "the neck was not turned down"
            assert part.is_inside(Vector(height, neck, 2.5)), "there is no neck to clip onto"
        assert RIG.clip_length < 5.0, "a bridge this long wants supporting"

    def test_the_yards_span_what_the_rig_asks_for(self, part):
        course, _ = RIG.course_span
        assert pytest.approx(course * RIG.mast_length, abs=0.01) == part.bounding_box().size.Y

    def test_the_mast_writes_a_manifold_mesh(self, part, tmp_path):
        write_3mf(part, tmp_path / "mast.3mf")


class TestSails:
    @pytest.fixture(scope="class")
    def part(self, lines):
        return rigging.sails(SPEC, lines, RIG)

    def test_there_are_two_sails_lying_flat(self, part):
        assert part.is_valid
        assert len(part.solids()) == 2
        assert pytest.approx(0.0, abs=1e-6) == part.bounding_box().min.Z

    def test_each_sail_spans_its_pair_of_yards(self):
        """The sail's height is the gap between the yards it hangs from.

        Computed twice from different ends -- the yards from the rig, the sail
        from `sail_sizes` -- so this is what catches the two drifting apart.
        """
        for (_, height), pair in zip(sail_sizes(RIG), (RIG.course, RIG.topsail), strict=True):
            assert height == pytest.approx((pair[1] - pair[0]) * RIG.mast_length, abs=1e-6)

    def test_each_sail_is_as_wide_as_its_yards_clip_necks_are_apart(self):
        for (width, _), span in zip(sail_sizes(RIG), RIG.course_span, strict=True):
            half = span * RIG.mast_length / 2.0
            neck = half * (1.0 - RIG.clip_inset)
            assert width == pytest.approx(2.0 * neck, abs=1e-6)

    def test_a_corner_clips_over_its_neck_and_holds(self, lines):
        """The bore clears the neck; the mouth does not, so it snaps on.

        This is what the necked yard bought beyond printability. When the yard
        was a plain cylinder with a shallow groove turned in it, the groove's
        floor was narrower than the mouth, so nothing held a sail on at all.
        """
        neck = RIG.neck_width * mast_width(SPEC, lines) / 2.0
        assert neck + TOLERANCE > neck, "the bore does not clear the neck"
        assert RIG.mouth * 2.0 * neck < 2.0 * neck, "the mouth would slip off the neck"

    def test_a_corner_eye_is_open_at_the_top(self, lines):
        """Open upward: away from the bed when printing, and square to the sail
        once it is rigged, so it presses onto both yards at once.

        Probes one sail on its own rather than the printed pair, because the
        pair is shifted sideways to lay it out and an earlier version of this
        aimed at the middle of an edge instead of a corner -- where there is
        nothing either way, so it passed without checking anything.
        """
        width, height = sail_sizes(RIG)[0]
        radius = RIG.neck_width * mast_width(SPEC, lines) / 2.0
        outer = radius + TOLERANCE + RIG.loop_wall
        offset = stand_off(SPEC, lines, RIG)
        one = rigging.sail(RIG, width, height, radius, offset)

        corner = (-height / 2.0, width / 2.0)
        assert one.is_inside(Vector(*corner, offset / 2.0)), "the eye has no neck holding it"
        assert not one.is_inside(Vector(*corner, offset)), "the bore is filled"
        assert not one.is_inside(Vector(*corner, offset + outer - 0.1)), "the mouth is closed"

    def test_the_neck_holds_the_plate_clear_of_the_mast(self, lines):
        """A sail spans the whole yard and the mast stands in the middle of it.

        Without the neck the plate sits a loop-radius from the yard's axis,
        which is inside the mast -- the first assembled render had 130 cubic
        millimetres of sail in the same place as the mast. Measured across the
        mast's corners, because it turns.
        """
        corners = mast_width(SPEC, lines) / np.sqrt(3.0)
        clear = stand_off(SPEC, lines, RIG) - RIG.sail_thickness
        assert clear > corners, f"the plate reaches to {clear:.2f}mm, the mast to {corners:.2f}mm"

    def test_the_sails_write_a_manifold_mesh(self, part, tmp_path):
        """Two separate solids in one file still has to be a sound mesh."""
        write_3mf(part, tmp_path / "sails.3mf")
