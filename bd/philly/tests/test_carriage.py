"""The carriage, the trunnion pegs, the cap squares, and the four together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a peg that binds instead of pivoting, a cap square that fouls the
barrel, a rimbase that will not pass where it has to. Nothing holding the gun
is a spring -- an earlier version held it by flexing the brackets, which worked
out at three times the strain PLA takes -- so these are about whether things
clear each other, and whether what should be captive is. The clamps that hold
the carriage on its slide do spring, and are tested in test_slide.py.
"""

from __future__ import annotations

import math

import pytest
from build123d import Axis, Vector
from conftest import steepest_overhang

from cannon.assembly import assembly
from cannon.cannon import NINE_POUNDER, CannonSpec, base_ring_radius, cannon
from cannon.cap_square import CapSquareSpec, cap_square
from cannon.carriage import CarriageSpec, carriage
from cannon.trunnion import TrunnionSpec, trunnion

SPEC = CarriageSpec()
PEGS = SPEC.pegs
STRAPS = CapSquareSpec(carriage=SPEC)
LIMIT = math.sin(math.radians(PEGS.max_overhang)) + 1e-6


class TestTrunnion:
    """A shank in the barrel, a rimbase against the bracket, a journal in the bed."""

    @pytest.fixture(scope="class")
    def peg(self):
        return trunnion(PEGS)

    def test_it_is_one_valid_solid(self, peg):
        assert peg.is_valid
        assert len(peg.solids()) == 1

    def test_it_prints_shank_down(self, peg):
        box = peg.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.rimbase) < 1e-6, "the rimbase is the widest part"
        height = PEGS.into_barrel + PEGS.stand_off + PEGS.journal
        assert abs(box.size.Z - height) < 1e-6

    def test_the_rimbase_cannot_follow_the_journal_into_the_bed(self):
        """What keeps the peg from working out of the barrel: the collar will not fit."""
        assert PEGS.rimbase > PEGS.bed

    def test_nothing_overhangs(self, peg):
        assert steepest_overhang(peg) <= LIMIT


BROADSIDE = CarriageSpec(gun=NINE_POUNDER, axis_height=14.64, elevation=4.0)


class TestEitherCarriage:
    """Both carriages print, and both carry their guns where they are meant to."""

    @pytest.fixture(scope="class", params=[SPEC, BROADSIDE], ids=["12-pounder", "9-pounder"])
    def spec(self, request):
        return request.param

    @pytest.fixture(scope="class")
    def truck(self, spec):
        return carriage(spec)

    def test_it_is_one_valid_solid(self, spec, truck):
        assert truck.is_valid
        assert len(truck.solids()) == 1

    def test_it_sits_flat_on_the_bed(self, spec, truck):
        assert abs(truck.bounding_box().min.Z) < 1e-6

    def test_nothing_overhangs(self, spec, truck):
        """The rail's hook, the tunnel's roof, the jaws' lead-ins and the trucks'
        cones all lean at 45 degrees, and no further."""
        assert steepest_overhang(truck) <= LIMIT

    def test_the_trunnions_are_at_the_height_asked_for(self, spec):
        parts = {part.label: part for part in assembly(spec, elevation=0.0).children}
        box = parts["trunnion+1"].bounding_box()
        assert abs(box.center().Z - spec.axis_height) < 1e-6

    def test_the_breech_rests_on_the_quoin(self, spec, truck):
        """At the set elevation the gun clears the quoin by a hair; half a degree
        more and the breech would be in it, so it is the quoin holding it there."""
        resting = {p.label: p for p in assembly(spec).children}["cannon"]
        assert (resting & truck).volume < 1e-9
        raised = {p.label: p for p in assembly(spec, elevation=spec.elevation + 0.5).children}
        assert (raised["cannon"] & truck).volume > 1e-3

    def test_the_gun_balances_aft_of_its_trunnions(self, spec):
        """Or it would tip muzzle-down off the quoin instead of resting on it."""
        gun = cannon(spec.gun)
        assert spec.gun.trunnions_at * spec.gun.length * spec.gun.scale < gun.center().Z


class TestCarriage:
    @pytest.fixture(scope="class")
    def truck(self):
        return carriage(SPEC)

    def test_the_trunnion_bed_is_open_at_the_top(self, truck):
        """The gun drops in, so nothing may roof the bed -- there is no support under one."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        axis = SPEC.axis_height
        assert not truck.is_inside(Vector(0, y, axis)), "the bed itself"
        assert not truck.is_inside(Vector(0, y, axis + PEGS.bed / 2 - 0.1)), "and the way in"
        assert truck.is_inside(Vector(0, y, axis - PEGS.bed / 2 - 0.3)), "metal under it"

    def test_the_rail_hooks_out_over_the_bracket(self, truck):
        """The hook is what a cap square catches under; without it the strap lifts off."""
        rail_top = SPEC.rail_top
        outside = SPEC.gap / 2 + SPEC.bracket + SPEC.flare / 2
        assert truck.is_inside(Vector(-4, outside, rail_top - SPEC.flare / 4)), "the hook"
        assert not truck.is_inside(Vector(-4, outside, rail_top - SPEC.flare)), "clear beneath it"

    def test_the_detent_stands_proud_of_the_rail(self, truck):
        rail_top = SPEC.rail_top
        y = SPEC.gap / 2 + SPEC.bracket / 2
        assert truck.is_inside(Vector(SPEC.detent_at, y, rail_top + SPEC.detent / 2))
        assert not truck.is_inside(Vector(SPEC.detent_at - 1, y, rail_top + SPEC.detent / 2))

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring passes between them on the way in; it is the widest thing there."""
        assert SPEC.gap / 2 > base_ring_radius(SPEC.gun)

    def test_the_quoin_stands_on_the_bed(self, truck):
        top = SPEC.quoin_top
        assert truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top - 0.2)), "the wedge is there"
        assert not truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top + 0.2)), "and stops there"
        assert top > SPEC.bed_top

    def test_the_hinge_stops_the_cap_square_going_aft(self, truck):
        """Without it the strap slid on past the end of the rail and off, and the gun
        was free to lift out of its beds."""
        y = SPEC.gap / 2 + STRAPS.stand_off + SPEC.bracket / 2
        z = SPEC.rail_top + STRAPS.lift + STRAPS.roof / 2
        assert truck.is_inside(Vector(SPEC.rail_end + SPEC.hinge / 2, y, z))
        assert SPEC.hinge_height >= STRAPS.lift + STRAPS.roof, "as tall as the strap it stops"


class TestCapSquare:
    @pytest.fixture(scope="class")
    def strap(self):
        return cap_square(STRAPS)

    def test_it_is_one_valid_solid(self, strap):
        assert strap.is_valid
        assert len(strap.solids()) == 1

    def test_it_prints_groove_up(self, strap):
        """Fitted the other way up, so every flank of the groove narrows as it rises."""
        box = strap.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.Z - STRAPS.height) < 1e-6
        assert steepest_overhang(strap) <= LIMIT

    def test_it_spans_the_bed_with_room_to_slide(self):
        assert STRAPS.length > PEGS.bed + 2 * STRAPS.travel
        assert STRAPS.travel > 0, "it has to clear the detent before the step stops it"

    def test_it_parks_forward_of_the_detent(self):
        """Where it waits, clear of the bed, while the gun is dropped in -- and the
        same room is what lets it slide off the fore end of the rail entirely."""
        assert SPEC.detent_at - SPEC.steps[0][0] >= STRAPS.length


class TestAssembled:
    @pytest.fixture(scope="class")
    def parts(self):
        return {part.label: part for part in assembly().children}

    @pytest.mark.parametrize(
        ("one", "other"),
        [
            ("carriage", "cannon"),
            ("carriage", "trunnion+1"),
            ("carriage", "cap square+1"),
            ("cannon", "trunnion+1"),
            ("cannon", "cap square+1"),
            ("trunnion+1", "cap square+1"),
        ],
    )
    def test_no_two_parts_share_any_volume(self, parts, one, other):
        """A fit that is 0.05mm too tight is invisible in the viewer."""
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_a_peg_reaches_from_the_barrel_through_its_bracket(self, parts):
        box = parts["trunnion+1"].bounding_box()
        assert abs(box.max.Y - (SPEC.gap / 2 + SPEC.bracket)) < 1e-6, "flush outside"
        assert SPEC.gap / 2 - PEGS.stand_off + 1e-6 > box.min.Y, "and home in the socket"

    def test_the_cap_square_shuts_the_bed(self, parts):
        """Over the trunnion, so the gun cannot lift out until the strap is slid off."""
        strap = parts["cap square+1"].bounding_box()
        assert SPEC.axis_height < strap.min.Z, "it sits above the trunnion"
        assert -PEGS.bed / 2 > strap.min.X, "and spans the bed"
        assert PEGS.bed / 2 < strap.max.X

    def test_the_gun_elevates_on_its_trunnions(self):
        """The muzzle rises and the trunnion axis stays put: it swings, it does not slide."""
        level = {p.label: p for p in assembly(elevation=0.0).children}["cannon"]
        level = level.faces().sort_by(Axis.X)[0].center()
        raised = {p.label: p for p in assembly(elevation=6.0).children}["cannon"]
        muzzle = raised.faces().sort_by(Axis.X)[0].center()
        assert muzzle.Z > level.Z + 1.0
        assert muzzle.X > level.X, "swung back, not lifted bodily"


def test_the_gun_can_be_built_without_sockets():
    """The barrel alone is still a model in its own right."""
    assert cannon(CannonSpec(trunnions=None)).is_valid
    assert TrunnionSpec().socket >= TrunnionSpec().shank
