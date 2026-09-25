"""The carriage, the trunnion pegs, and the three of them together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a peg that binds in its socket instead of pivoting, a bracket the
gun fouls, a quoin that holds the breech up off its own trunnions. The
assembly tests measure the gaps rather than trusting that it looked right.
"""

from __future__ import annotations

import math

import pytest
from build123d import Axis, Vector
from conftest import steepest_overhang

from cannon.assembly import assembly
from cannon.cannon import CannonSpec, barrel_radius, base_ring_radius
from cannon.carriage import CarriageSpec, carriage
from cannon.trunnion import TrunnionSpec, trunnion

SPEC = CarriageSpec()
PEGS = SPEC.pegs


class TestTrunnion:
    """The peg: a round shank to turn in the gun, a diamond head to key the bracket."""

    @pytest.fixture(scope="class")
    def peg(self):
        return trunnion(PEGS)

    def test_it_is_one_valid_solid(self, peg):
        assert peg.is_valid
        assert len(peg.solids()) == 1

    def test_it_prints_shank_down(self, peg):
        box = peg.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.shank) < 1e-6, "the shank is the widest part"
        assert abs(box.size.Z - (PEGS.shank_length + PEGS.key_length)) < 1e-6

    def test_nothing_overhangs(self, peg):
        assert steepest_overhang(peg) <= math.sin(math.radians(PEGS.max_overhang)) + 1e-6


class TestCarriage:
    @pytest.fixture(scope="class")
    def truck(self):
        return carriage(SPEC)

    def test_it_is_one_valid_solid(self, truck):
        assert truck.is_valid
        assert len(truck.solids()) == 1

    def test_it_sits_flat_on_the_bed(self, truck):
        box = truck.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.Y - (SPEC.gap + 2 * SPEC.bracket)) < 1e-6

    def test_nothing_overhangs(self, truck):
        """The diamond holes and their countersinks are drawn to sit at the limit."""
        assert steepest_overhang(truck) <= math.sin(math.radians(PEGS.max_overhang)) + 1e-6

    def test_the_brackets_are_the_thickness_asked_for(self, truck):
        """The snap lives or dies on this number, so it is measured, not assumed."""
        z = SPEC.bed + SPEC.axis_height
        inside, outside = SPEC.gap / 2, SPEC.gap / 2 + SPEC.bracket
        x = 4.0  # clear of the trunnion hole
        assert not truck.is_inside(Vector(x, inside - 0.1, z))
        assert truck.is_inside(Vector(x, inside + SPEC.bracket / 2, z))
        assert not truck.is_inside(Vector(x, outside + 0.1, z))

    def test_the_trunnion_holes_go_right_through(self, truck):
        z = SPEC.bed + SPEC.axis_height
        for side in (1, -1):
            y = side * (SPEC.gap / 2 + SPEC.bracket / 2)
            assert not truck.is_inside(Vector(0, y, z)), "the hole is open"
            assert truck.is_inside(Vector(0, y, z + PEGS.hole)), "metal above it"

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring passes between them on the way in; it is the widest thing there."""
        assert SPEC.gap / 2 > base_ring_radius(SPEC.gun)

    def test_the_quoin_carries_the_breech(self, truck):
        top = SPEC.bed + SPEC.quoin_height
        assert truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top - 0.2)), "the wedge is there"
        assert not truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top + 0.2)), "and stops there"
        gap = SPEC.axis_height - SPEC.gun_radius(SPEC.quoin_to) - SPEC.quoin_height
        assert abs(gap - SPEC.clearance) < 1e-6, "the breech clears it by the stated play"


class TestAssembled:
    @pytest.fixture(scope="class")
    def parts(self):
        return {part.label: part for part in assembly().children}

    @pytest.mark.parametrize(
        ("one", "other"),
        [
            ("carriage", "cannon"),
            ("carriage", "trunnion+1"),
            ("cannon", "trunnion+1"),
            ("cannon", "trunnion-1"),
        ],
    )
    def test_no_two_parts_share_any_volume(self, parts, one, other):
        """A press fit that is 0.05mm too tight is invisible in the viewer."""
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_a_peg_reaches_from_its_bracket_into_the_barrel(self, parts):
        box = parts["trunnion+1"].bounding_box()
        barrel = barrel_radius(SPEC.gun, SPEC.gun.trunnions_at)
        assert abs(box.max.Y - (SPEC.gap / 2 + SPEC.bracket)) < 1e-6, "flush outside"
        assert barrel - PEGS.into_barrel + 1e-6 > box.min.Y, "and home in the socket"

    def test_the_gun_elevates_on_its_trunnions(self, parts):
        """The muzzle rises and the trunnion axis stays put: it swings, it does not slide."""
        level = parts["cannon"].faces().sort_by(Axis.X)[0].center()
        raised = {p.label: p for p in assembly(elevation=6.0).children}["cannon"]
        muzzle = raised.faces().sort_by(Axis.X)[0].center()
        assert muzzle.Z > level.Z + 1.0
        assert muzzle.X > level.X, "swung back, not lifted bodily"


def test_the_gun_can_be_built_without_sockets():
    """The barrel alone is still a model in its own right."""
    bare = CannonSpec(trunnions=None)
    assert TrunnionSpec().socket > TrunnionSpec().shank
    from cannon.cannon import cannon

    assert cannon(bare).is_valid
