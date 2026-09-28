"""The carriage, the trunnion pin, and the three of them together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a pin that binds instead of pivoting, a hole drawn looser than the pin
it grips, a quoin that holds the breech off its seat. Three schemes have now gone
wrong on the print bed and are tested against by name -- pegs that fell out of
the barrel, cap squares too small to hook onto anything, and a bayonet the gun
wobbled sideways out of -- so most of these are the same question asked of a
fourth: is the gun captive, and can it still turn?
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
    """One pin, bored through the gun and pressed into both brackets."""

    @pytest.fixture(scope="class")
    def pin(self):
        return trunnion(PEGS)

    def test_it_is_one_valid_solid(self, pin):
        assert pin.is_valid
        assert len(pin.solids()) == 1

    def test_it_prints_standing_on_its_head(self, pin):
        """The head is what makes that a print at all: 13.9mm2 of first layer where
        the shank on its own would stand on 5.3, and a face that seats against the
        outside of a bracket, so there is one depth to press it to."""
        box = pin.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.head) < 1e-6
        assert abs(box.size.Y - PEGS.head) < 1e-6
        assert abs(box.size.Z - PEGS.height) < 1e-6

    def test_it_is_round_all_the_way_along(self, pin):
        """No flats anywhere: the bayonet's flats are what let the gun work sideways
        out of its slots. A volume is the cheapest proof that none survive -- two
        cylinders, less the ring the entry chamfer takes off the top."""
        radius, lead = PEGS.shank / 2, PEGS.entry
        head = math.pi * (PEGS.head / 2) ** 2 * PEGS.head_thick
        shank = math.pi * radius**2 * PEGS.length
        chamfered = math.pi * (lead * radius**2 - (radius**3 - (radius - lead) ** 3) / 3)
        assert pin.volume == pytest.approx(head + shank - chamfered, rel=1e-3)

    def test_a_head_no_wider_than_the_hole_is_refused(self):
        """It is the head that stops the pin going in too far, so it has to bear on
        something. Turned down to the bore it would press straight through."""
        with pytest.raises(ValueError, match="press straight through"):
            trunnion(replace(PEGS, head=PEGS.bore))

    def test_it_is_long_enough_for_either_carriage(self):
        """With the head seated on the outside of one bracket the shank has to reach
        the outside of the other, or one half of the press fit is simply missing.
        Over-long it stands a little proud, which reads as the end of a trunnion."""
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

    def test_the_bracket_is_closed_over_the_pins_hole(self, truck):
        """The wobble, asked as a shape. The bayonet had the bracket open to the top
        so the pin could drop in, and a slot the pin can get into is a slot it can
        work along: the printed gun came off sideways in an afternoon. This is a
        hole, walled all the way to the top of the bracket."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        axis = SPEC.axis_height
        apex = axis + (PEGS.bore / 2) / math.sin(math.radians(PEGS.max_overhang))
        assert not truck.is_inside(Vector(0, y, axis)), "the hole itself"
        assert not truck.is_inside(Vector(0, y, apex - 0.2)), "and the teardrop over it"
        assert truck.is_inside(Vector(0, y, apex + 0.2)), "bracket over the apex"
        assert truck.is_inside(Vector(0, y, SPEC.rail_top - 0.1)), "and on up to the top"
        assert truck.is_inside(Vector(0, y, axis - PEGS.bore / 2 - 0.3)), "metal under it"

    def test_the_bracket_grips_and_the_barrel_turns(self):
        """The whole fit in three diameters: the hole the pin presses into is no
        wider than the pin, and the hole it turns in is `running` wider."""
        assert PEGS.bore <= PEGS.shank < PEGS.socket
        assert PEGS.shank - PEGS.bore == pytest.approx(PEGS.press)
        assert PEGS.socket - PEGS.shank == pytest.approx(PEGS.running)

    def test_the_hole_is_walled_all_round(self, truck):
        """Not a slot in any direction, which is the one thing the last scheme was."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        for hand in (1, -1):
            for out in (0.2, 0.6, 1.0):
                here = Vector(hand * (PEGS.bore / 2 + out), y, SPEC.axis_height)
                assert truck.is_inside(here), f"metal {out}mm out from the hole"

    def test_there_is_bracket_over_the_holes_apex(self, truck):
        """What `cheek` is set from. The hole carries its own roof as a teardrop, so
        its apex stands 1.84mm over the axis, and what is left above that is the one
        ligament the press fit could split: the old 2.4mm cheek left 0.56 of it."""
        assert SPEC.roof_over_the_pin > 1.0
        with pytest.raises(ValueError, match="over the pin"):
            carriage(replace(SPEC, cheek=2.4))
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
        """A fit that is 0.05mm too tight is invisible in the viewer.

        The press fit is drawn nominal, so the pin and the brackets share a surface
        and no volume: a 2.6mm hole comes off the printer a tenth or two under size
        already, and that is the whole of the grip. Draw interference here instead
        and this pair would have to expect it.
        """
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_the_gun_cannot_be_lifted_off_the_pin(self):
        """The failed print, asked as the physical question and answered the other
        way round. Shove the gun anywhere but along the pin's own axis, a quarter of
        a millimetre at a time, and it never clears the pin. The bayonet let it out
        at one elevation by design and at any elevation in practice."""
        parts = {p.label: p for p in assembly(SPEC).children}
        gun, pin = parts["cannon"], parts["trunnion"]
        for dx, dz in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            for step in np.arange(0.25, 3.6, 0.5):
                shoved = Pos(dx * float(step), 0, dz * float(step)) * gun
                assert (shoved & pin).volume > 1e-9, f"shoved {dx},{dz} by {step}"

    def test_the_barrel_turns_freely_on_the_pin(self):
        """A bearing, not a key. The gun swings through its whole range without ever
        touching the pin it hangs on -- where the bayonet's hole had a flat in it,
        so that turning the gun turned the pin."""
        for elevation in (-16.0, 0.0, SPEC.elevation):
            parts = {p.label: p for p in assembly(SPEC, elevation=elevation).children}
            shared = parts["cannon"] & parts["trunnion"]
            assert shared is None or shared.volume < 1e-9, f"at {elevation:+.1f} degrees"

    def test_the_pin_reaches_from_bracket_to_bracket(self, parts):
        """Through the barrel and into both brackets: a press fit at each end, and
        no way for the gun to reach either of them."""
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
