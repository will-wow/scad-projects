"""The carriage, the trunnion pin, and the three of them together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a pin that binds instead of pivoting, a lip that will not give, a
quoin that holds the breech off its seat. Two things here have gone wrong on the
print bed already and are tested against by name -- pegs that fell out of the
barrel, and cap squares too small to hook onto anything -- so these are about
whether what should be captive is, and whether what has to spring can.
"""

from __future__ import annotations

import math

import pytest
from build123d import Axis, Vector
from conftest import steepest_overhang

from cannon.assembly import assembly
from cannon.cannon import NINE_POUNDER, CannonSpec, base_ring_radius, cannon
from cannon.carriage import CarriageSpec, carriage
from cannon.trunnion import TrunnionSpec, trunnion

SPEC = CarriageSpec()
PEGS = SPEC.pegs
LIMIT = math.sin(math.radians(PEGS.max_overhang)) + 1e-6


class TestTrunnion:
    """One pin, bored through the gun, its ends clipped into the brackets."""

    @pytest.fixture(scope="class")
    def pin(self):
        return trunnion(PEGS)

    def test_it_is_one_valid_solid(self, pin):
        assert pin.is_valid
        assert len(pin.solids()) == 1

    def test_it_prints_standing_on_end(self, pin):
        box = pin.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.shank) < 1e-6
        assert abs(box.size.Z - PEGS.length) < 1e-6

    def test_it_is_long_enough_for_either_carriage(self):
        """Short of the outside of a bracket it would have nothing but the detent
        holding it; over-long it only stands a little proud, which looks right."""
        for spec in (SPEC, BROADSIDE):
            assert PEGS.length >= spec.gap + 2 * spec.bracket

    def test_it_grips_the_barrel_along_its_whole_width(self):
        """Two pegs 1.2mm into blind sockets fell out while the gun was going in."""
        assert PEGS.length > 2 * (SPEC.gap / 2 - PEGS.stand_off)

    def test_nothing_overhangs(self, pin):
        assert steepest_overhang(pin) <= LIMIT


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
        """The detent's flanks, the roof over each bed, the tunnel's gable, the jaws'
        lead-ins and the trucks' cones all lean at 45 degrees, and no further."""
        assert steepest_overhang(truck) <= LIMIT

    def test_the_trunnions_are_at_the_height_asked_for(self, spec):
        parts = {part.label: part for part in assembly(spec, elevation=0.0).children}
        box = parts["trunnion"].bounding_box()
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

    def test_the_bed_is_open_at_the_top(self, truck):
        """The gun is pushed straight down into it, so nothing may roof the bed --
        and nothing could, since there is no support under a roof."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        axis = SPEC.axis_height
        assert not truck.is_inside(Vector(0, y, axis)), "the bed itself"
        assert not truck.is_inside(Vector(0, y, SPEC.rail_top - 0.1)), "and the way in"
        assert truck.is_inside(Vector(0, y, axis - PEGS.bed / 2 - 0.3)), "metal under it"

    def test_the_detent_pinches_the_way_in(self, truck):
        """The whole clip in two numbers: the way past is narrower than the pin, and
        the bed beyond it is wider. Without the first the gun drops out; without the
        second it binds instead of turning."""
        assert PEGS.gate < PEGS.shank < PEGS.bed
        y = SPEC.gap / 2 + SPEC.bracket / 2
        crest = SPEC.axis_height + SPEC.crest
        for hand in (1, -1):
            edge = hand * (PEGS.gate / 2 + 0.05)
            assert truck.is_inside(Vector(edge, y, crest)), "the crest, on both lips"
            assert not truck.is_inside(Vector(edge, y, crest + 0.4)), "clear above it"
            assert not truck.is_inside(Vector(edge, y, crest - 0.4)), "and below, in the bed"

    def test_each_lip_is_cut_free_of_the_bracket(self, truck):
        """What makes the lip the spring instead of the bracket. Flexing the bracket
        itself wanted three times the strain PLA takes."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        crest = SPEC.axis_height + SPEC.crest
        inside = PEGS.bed / 2 + SPEC.lip / 2
        assert truck.is_inside(Vector(inside, y, crest)), "the lip"
        assert not truck.is_inside(Vector(PEGS.bed / 2 + SPEC.lip + SPEC.relief / 2, y, crest)), (
            "the slot behind it"
        )
        floor = SPEC.axis_height - SPEC.relief_depth
        assert truck.is_inside(Vector(PEGS.bed / 2 + SPEC.lip + SPEC.relief / 2, y, floor - 0.2)), (
            "and metal under the slot, which is where the lip is anchored"
        )

    def test_a_lip_stays_well_inside_what_pla_takes(self):
        """It bends across the printed layers, which is the weak direction, so this is
        held under one percent rather than the two the material would allow."""
        for spec in (SPEC, BROADSIDE):
            assert spec.lip_strain < 0.01

    def test_a_lip_cannot_be_bent_far_enough_to_break(self):
        """The slot behind it closes first: whatever a child does to the clip, the lip
        cannot travel more than `relief`, and the detent only asks for a fifth of it."""
        for spec in (SPEC, BROADSIDE):
            assert spec.relief > 2 * spec.pegs.snap

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring passes between them on the way in; it is the widest thing there."""
        assert SPEC.gap / 2 > base_ring_radius(SPEC.gun)

    def test_the_quoin_stands_on_the_bed(self, truck):
        top = SPEC.quoin_top
        assert truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top - 0.2)), "the wedge is there"
        assert not truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top + 0.2)), "and stops there"
        assert top > SPEC.bed_top


class TestAssembled:
    @pytest.fixture(scope="class")
    def parts(self):
        return {part.label: part for part in assembly().children}

    @pytest.mark.parametrize(("one", "other"), [("carriage", "cannon"), ("cannon", "trunnion")])
    def test_no_two_parts_share_any_volume(self, parts, one, other):
        """A fit that is 0.05mm too tight is invisible in the viewer."""
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_the_only_metal_the_carriage_and_the_pin_share_is_the_detents(self, parts):
        """That overlap is the click: four detents, each standing `snap`/2 into the
        pin's path. If this ever comes out as nothing, the gun drops straight out."""
        shared = parts["carriage"] & parts["trunnion"]
        assert shared is not None and 0 < shared.volume < 0.2
        box = shared.bounding_box()
        crest = SPEC.axis_height + SPEC.crest
        assert crest - PEGS.snap < box.min.Z and crest + PEGS.snap > box.max.Z
        assert len(shared.solids()) == 4, "two lips on each of two brackets"

    def test_the_pin_reaches_from_bracket_to_bracket(self, parts):
        """Through the barrel and out both sides: there is no way for it to work out."""
        box = parts["trunnion"].bounding_box()
        outside = SPEC.gap / 2 + SPEC.bracket
        assert -outside >= box.min.Y and outside <= box.max.Y

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
