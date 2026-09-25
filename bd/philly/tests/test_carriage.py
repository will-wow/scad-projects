"""The carriage, the trunnion pegs, the cap squares, and the four together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a peg that binds instead of pivoting, a cap square that fouls the
barrel, a rimbase that will not pass where it has to. Nothing here is a spring
-- an earlier version held the gun by flexing the brackets, which worked out at
three times the strain PLA takes -- so these are about whether things clear
each other, and whether what should be captive is.
"""

from __future__ import annotations

import math

import pytest
from build123d import Axis, Vector
from conftest import steepest_overhang

from cannon.assembly import assembly
from cannon.cannon import CannonSpec, base_ring_radius, cannon
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


class TestCarriage:
    @pytest.fixture(scope="class")
    def truck(self):
        return carriage(SPEC)

    def test_it_is_one_valid_solid(self, truck):
        assert truck.is_valid
        assert len(truck.solids()) == 1

    def test_it_sits_flat_on_the_bed(self, truck):
        assert abs(truck.bounding_box().min.Z) < 1e-6

    def test_nothing_overhangs(self, truck):
        """The rail's hook is an undercut; only its 45-degree underside makes it printable."""
        assert steepest_overhang(truck) <= LIMIT

    def test_the_trunnion_bed_is_open_at_the_top(self, truck):
        """The gun drops in, so nothing may roof the bed -- there is no support under one."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        axis = SPEC.bed + SPEC.axis_height
        assert not truck.is_inside(Vector(0, y, axis)), "the bed itself"
        assert not truck.is_inside(Vector(0, y, axis + PEGS.bed / 2 - 0.1)), "and the way in"
        assert truck.is_inside(Vector(0, y, axis - PEGS.bed / 2 - 0.3)), "metal under it"

    def test_the_rail_hooks_out_over_the_bracket(self, truck):
        """The hook is what a cap square catches under; without it the strap lifts off."""
        rail_top = SPEC.bed + SPEC.top
        outside = SPEC.gap / 2 + SPEC.bracket + SPEC.flare / 2
        assert truck.is_inside(Vector(-4, outside, rail_top - SPEC.flare / 4)), "the hook"
        assert not truck.is_inside(Vector(-4, outside, rail_top - SPEC.flare)), "clear beneath it"

    def test_the_detent_stands_proud_of_the_rail(self, truck):
        rail_top = SPEC.bed + SPEC.top
        y = SPEC.gap / 2 + SPEC.bracket / 2
        assert truck.is_inside(Vector(SPEC.detent_at, y, rail_top + SPEC.detent / 2))
        assert not truck.is_inside(Vector(SPEC.detent_at - 1, y, rail_top + SPEC.detent / 2))

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring passes between them on the way in; it is the widest thing there."""
        assert SPEC.gap / 2 > base_ring_radius(SPEC.gun)

    def test_the_quoin_carries_the_breech(self, truck):
        top = SPEC.bed + SPEC.quoin_height
        assert truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top - 0.2)), "the wedge is there"
        assert not truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top + 0.2)), "and stops there"
        gap = SPEC.axis_height - SPEC.gun_radius(SPEC.quoin_to) - SPEC.quoin_height
        assert abs(gap - SPEC.clearance) < 1e-6, "the breech clears it by the stated play"


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
        assert SPEC.bed + SPEC.axis_height < strap.min.Z, "it sits above the trunnion"
        assert -PEGS.bed / 2 > strap.min.X, "and spans the bed"
        assert PEGS.bed / 2 < strap.max.X

    def test_the_gun_elevates_on_its_trunnions(self, parts):
        """The muzzle rises and the trunnion axis stays put: it swings, it does not slide."""
        level = parts["cannon"].faces().sort_by(Axis.X)[0].center()
        raised = {p.label: p for p in assembly(elevation=6.0).children}["cannon"]
        muzzle = raised.faces().sort_by(Axis.X)[0].center()
        assert muzzle.Z > level.Z + 1.0
        assert muzzle.X > level.X, "swung back, not lifted bodily"

    def test_the_gun_sits_below_the_rail(self, parts, lines):
        """Why the carriage is as low as it is. It used to stand proud of the bulwark."""
        from main import HULL

        deck = next(d for d in HULL.decks if d.start < 0.5 < d.end)
        factor = HULL.length / lines.length
        deck_top = deck.height * lines.depth * factor
        rail = lines.sheer_height.value(0.5 * lines.length) * factor
        top = max(part.bounding_box().max.Z for part in parts.values())
        assert deck_top + top < rail, "the whole gun clears the bulwark amidships"


def test_the_gun_can_be_built_without_sockets():
    """The barrel alone is still a model in its own right."""
    assert cannon(CannonSpec(trunnions=None)).is_valid
    assert TrunnionSpec().socket >= TrunnionSpec().shank
