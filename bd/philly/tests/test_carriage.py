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
from dataclasses import replace

import numpy as np
import pytest
from build123d import Axis, Pos, Vector
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

    def test_it_prints_lying_on_a_flat(self, pin):
        """Which is the easier print -- a real contact patch instead of a 3.5mm2
        circle -- and the stronger part, the layers now running along the pin
        rather than across the way it is loaded."""
        box = pin.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.length) < 1e-6
        assert abs(box.size.Y - PEGS.shank) < 1e-6
        assert abs(box.size.Z - PEGS.waist) < 1e-6

    def test_the_flats_are_wide_enough_to_lie_on(self):
        """Cut them shallower and the arcs undercut the bed by more than the
        overhang limit on the way down; the two conditions meet at shank/sqrt 2."""
        assert PEGS.waist <= PEGS.shank / math.sqrt(2)
        with pytest.raises(ValueError, match="lying down"):
            trunnion(replace(PEGS, waist=2.0))

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

    def test_the_way_in_is_narrower_than_the_pin_is_round(self, truck):
        """The whole bayonet in two numbers: the slot takes the pin across its
        flats and not across its round, so the pin passes at one angle only."""
        assert PEGS.waist < PEGS.slot < PEGS.shank < PEGS.bed
        y = SPEC.gap / 2 + SPEC.bracket / 2
        over = SPEC.axis_height + SPEC.lip_underside + 0.4
        for hand in (1, -1):
            assert truck.is_inside(Vector(hand * (PEGS.slot / 2 + 0.05), y, over)), "the lip"
            assert not truck.is_inside(Vector(hand * (PEGS.slot / 2 - 0.05), y, over)), "the way in"

    def test_the_lips_are_solid_bracket(self, truck):
        """Nothing here springs. The sprung lips this replaced were cut free by a
        slot apiece and took a set after an afternoon of play."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        for hand in (1, -1):
            for out in (0.2, 0.6, 1.0, 1.4):
                here = Vector(hand * (PEGS.slot / 2 + out), y, SPEC.axis_height + 1.0)
                assert truck.is_inside(here), f"metal {out}mm out from the slot"

    def test_the_bed_carries_its_own_roof(self, truck):
        """The lips' undersides lie at 45 degrees from the slot out to the bed's
        widest, so there is nothing to bridge."""
        assert SPEC.lip_clears_the_pin_by > 0.05, "or the pin drops in and jams"
        assert steepest_overhang(truck) <= LIMIT

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring swings between them; it is the widest thing there, and the
        gap is set by the barrel at the trunnions, so nothing makes room for it on
        purpose. Measuring the guns off the scan took this from 0.9mm to 0.3."""
        for spec in (SPEC, BROADSIDE):
            assert spec.gap / 2 - base_ring_radius(spec.gun) > 0.2

    def test_the_quoin_stands_on_the_bed(self, truck):
        top = SPEC.quoin_top
        assert truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top - 0.2)), "the wedge is there"
        assert not truck.is_inside(Vector(SPEC.quoin_to - 0.2, 0, top + 0.2)), "and stops there"
        assert top > SPEC.bed_top


class TestAssembled:
    @pytest.fixture(scope="class")
    def parts(self):
        return {part.label: part for part in assembly().children}

    @pytest.mark.parametrize(
        ("one", "other"),
        [("carriage", "cannon"), ("cannon", "trunnion"), ("carriage", "trunnion")],
    )
    def test_no_two_parts_share_any_volume(self, parts, one, other):
        """A fit that is 0.05mm too tight is invisible in the viewer."""
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_the_gun_lifts_out_only_with_its_muzzle_down(self):
        """The bayonet, asked as the physical question: raise the gun straight up
        out of its beds, a quarter of a millimetre at a time, and see whether the
        pin ever meets a bracket on the way. At the angle it rests at, it does."""
        for elevation, out in ((SPEC.elevation, False), (0.0, False), (PEGS.release, True)):
            parts = {p.label: p for p in assembly(SPEC, elevation=elevation).children}
            truck, pin = parts["carriage"], parts["trunnion"]
            worst = max(
                (Pos(0, 0, float(z)) * pin & truck).volume for z in np.arange(0.0, 3.6, 0.25)
            )
            assert (worst < 1e-9) is out, f"at {elevation:+.1f} degrees"

    def test_it_is_held_by_solid_metal_rather_than_by_a_spring(self):
        """How far the pin's corners stand under the lips where the gun rests."""
        turned = SPEC.elevation - PEGS.release
        assert PEGS.locked_by(turned) > 0.3
        assert PEGS.locked_by(0.0) < 0, "and lined up, it passes"

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
