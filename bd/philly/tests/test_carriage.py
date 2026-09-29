"""The carriage, the trunnion bar, and the three of them together.

These are parts that have to fit each other, so most of what can go wrong is a
clearance: a hole drawn looser than the bar it grips, a hole that sags, a quoin
standing into the breech. Four schemes have now gone wrong on the print bed and
are tested against by name -- pegs that fell out of the barrel, cap squares too
small to hook onto anything, a bayonet the gun wobbled sideways out of, and a
round pin the gun tipped forward on -- so most of these ask a fifth the same two
questions: is the gun captive, and is it held at its angle?
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
from build123d import Box, Pos, Vector
from conftest import steepest_overhang

from cannon.assembly import assembly
from cannon.cannon import NINE_POUNDER, CannonSpec, base_ring_radius, cannon
from cannon.carriage import CarriageSpec, carriage
from cannon.trunnion import TrunnionSpec, diamond, trunnion

SPEC = CarriageSpec()
PEGS = SPEC.pegs
LIMIT = math.sin(math.radians(PEGS.max_overhang)) + 1e-6
BROADSIDE = CarriageSpec(gun=NINE_POUNDER, axis_height=14.64, elevation=4.0)


def _area(corners: list[tuple[float, float]]) -> float:
    pairs = zip(corners, corners[1:] + corners[:1], strict=True)
    return 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs))


class TestTrunnion:
    """One square bar, through the gun and pressed into both brackets."""

    @pytest.fixture(scope="class")
    def bar(self):
        return trunnion(PEGS)

    def test_it_is_one_valid_solid(self, bar):
        assert bar.is_valid
        assert len(bar.solids()) == 1

    def test_it_prints_lying_on_a_face(self, bar):
        """A real first layer, and the layers running along the bar rather than
        across the way it is loaded."""
        box = bar.bounding_box()
        assert abs(box.min.Z) < 1e-6
        assert abs(box.size.X - PEGS.length) < 1e-6
        assert abs(box.size.Y - PEGS.side) < 1e-6
        assert abs(box.size.Z - PEGS.side) < 1e-6

    def test_it_is_square_all_the_way_along(self, bar):
        """Square is what holds the gun's angle. A slice from the middle is the
        square less the four corners relieved off its long edges."""
        slab = bar & Box(0.1, 10.0, 10.0)
        assert slab.volume / 0.1 == pytest.approx(PEGS.side**2 - 2 * PEGS.relief**2, rel=1e-3)

    def test_it_is_long_enough_for_either_carriage(self):
        """Short of the outside of a bracket, that end of the press fit is simply
        missing; over-long it stands a little proud, which reads as the end of a
        trunnion."""
        for spec in (SPEC, BROADSIDE):
            assert PEGS.length >= spec.gap + 2 * spec.bracket

    def test_it_grips_the_barrel_along_its_whole_width(self):
        """Two pegs 1.2mm into blind sockets fell out while the gun was going in."""
        assert PEGS.length > 2 * (SPEC.gap / 2 - PEGS.stand_off)

    def test_nothing_overhangs(self, bar):
        """The relieved edges and the end chamfers under it lean 45 degrees."""
        assert steepest_overhang(bar) <= LIMIT


class TestDiamond:
    """The hole every part the bar goes through is cut with."""

    def test_stood_square_it_is_the_bar(self):
        corners = diamond(PEGS.side)
        assert _area(corners) == pytest.approx(PEGS.side**2)
        assert max(y for _, y in corners) == pytest.approx(PEGS.side / math.sqrt(2))

    @pytest.mark.parametrize("turned", [-6.0, -4.1, 0.0, 4.1, 6.0])
    def test_turned_no_roof_leans_past_the_limit(self, turned):
        """Turned to the gun's elevation, one roof face of a true square would lean
        49 degrees. That face is swung back up to 45."""
        right, apex, left, _ = diamond(PEGS.side, turned)
        for low in (right, left):
            lean = math.degrees(math.atan2(abs(apex[0] - low[0]), apex[1] - low[1]))
            assert lean <= PEGS.max_overhang + 1e-9

    @pytest.mark.parametrize("turned", [-4.1, 4.1])
    def test_turned_it_still_bears_on_the_bar(self, turned):
        """Swinging the face up only opens clearance: the other three corners are
        the bar's own, so the two faces under it -- where the gun's weight goes --
        are whole, and the sliver over the fourth is 0.17mm at its widest."""
        right, apex, left, bottom = diamond(PEGS.side, turned)
        radius = PEGS.side / math.sqrt(2)
        square = [
            (radius * math.cos(a), radius * math.sin(a))
            for a in (math.radians(turned + 90 * k) for k in range(4))
        ]
        for corner, own in zip(
            (right, left, bottom), (square[0], square[2], square[3]), strict=True
        ):
            assert corner == pytest.approx(own)
        # How far the apex stands off the face of the bar it was swung away from.
        low = right if turned > 0 else left
        face = (square[1][0] - low[0], square[1][1] - low[1])
        off = (apex[0] - low[0], apex[1] - low[1])
        sliver = abs(face[0] * off[1] - face[1] * off[0]) / math.hypot(*face)
        assert 0 < sliver < 0.2


class TestEitherCarriage:
    """Both carriages print, and both hold their guns where they are meant to."""

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
        """The diamonds' roofs, the tunnel's gable, the jaws' lead-ins and the
        trucks' cones all lean at 45 degrees, and no further."""
        assert steepest_overhang(truck) <= LIMIT

    def test_the_trunnions_are_at_the_height_asked_for(self, spec):
        parts = {part.label: part for part in assembly(spec).children}
        box = parts["trunnion"].bounding_box()
        assert abs(box.center().Z - spec.axis_height) < 1e-6

    def test_the_gun_cannot_tip(self, spec, truck):
        """The round pin's failure, asked directly. The printed gun is heavier at
        the muzzle than the model, and on a pin it fell forward off its quoin. Keyed
        on the bar, two degrees either way puts the bar into the brackets."""
        for tipped in (spec.elevation - 2.0, spec.elevation + 2.0):
            bar = {p.label: p for p in assembly(spec, elevation=tipped).children}["trunnion"]
            assert (bar & truck).volume > 1e-3, f"at {tipped:+.1f} degrees"

    def test_the_quoin_sits_under_the_breech(self, spec, truck):
        """Nothing rests on it now -- the bar holds the gun -- but it stands where a
        quoin would, a hair under the breech: half a degree more and it is in it."""
        resting = {p.label: p for p in assembly(spec).children}["cannon"]
        assert (resting & truck).volume < 1e-9
        raised = {p.label: p for p in assembly(spec, elevation=spec.elevation + 0.5).children}
        assert (raised["cannon"] & truck).volume > 1e-3


class TestCarriage:
    @pytest.fixture(scope="class")
    def truck(self):
        return carriage(SPEC)

    def test_the_bracket_is_closed_over_the_bars_hole(self, truck):
        """The bayonet had the bracket open to the top so its pin could drop in, and a
        slot the pin can get into is a slot it can work along. This is a hole, walled
        all the way to the top of the bracket."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        axis = SPEC.axis_height
        apex = axis + max(up for _, up in SPEC.hole)
        low = axis + min(up for _, up in SPEC.hole)
        assert not truck.is_inside(Vector(0, y, axis)), "the hole itself"
        assert not truck.is_inside(Vector(0, y, apex - 0.2)), "and up into its apex"
        assert truck.is_inside(Vector(0, y, apex + 0.2)), "bracket over the apex"
        assert truck.is_inside(Vector(0, y, SPEC.rail_top - 0.1)), "and on up to the top"
        assert truck.is_inside(Vector(0, y, low - 0.3)), "metal under it"

    def test_the_bracket_grips_and_the_barrel_holds_the_angle(self):
        """The whole fit in three sizes across the flats: the brackets' holes no
        bigger than the bar, and the barrel's only `key_fit` bigger."""
        assert PEGS.bore <= PEGS.side < PEGS.socket
        assert PEGS.side - PEGS.bore == pytest.approx(PEGS.press)
        assert PEGS.socket - PEGS.side == pytest.approx(PEGS.key_fit)

    def test_the_hole_is_walled_all_round(self, truck):
        """Not a slot in any direction."""
        y = SPEC.gap / 2 + SPEC.bracket / 2
        across = max(abs(along) for along, _ in SPEC.hole)
        for hand in (1, -1):
            for out in (0.2, 0.6, 1.0):
                here = Vector(hand * (across + out), y, SPEC.axis_height)
                assert truck.is_inside(here), f"metal {out}mm out from the hole"

    def test_there_is_bracket_over_the_holes_apex(self):
        """What `cheek` is set from. The diamond's apex stands 1.82mm over the axis,
        and what is left above it is the one ligament the press fit could split."""
        assert SPEC.roof_over_the_bar > 1.0
        with pytest.raises(ValueError, match="over the bar"):
            carriage(replace(SPEC, cheek=2.4))

    def test_the_brackets_clear_the_widest_part_of_the_gun(self):
        """The base ring passes between them; it is the widest thing there, and the
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

        The press fit is drawn nominal, so the bar and the brackets share faces and
        no volume: a printed hole comes out a tenth or two under size already, and
        that is the whole of the grip. It also says the brackets' diamonds are
        turned the right way -- turned the wrong way, they would be eight degrees
        out from the bar.
        """
        shared = parts[one] & parts[other]
        assert shared is None or shared.volume < 1e-9

    def test_the_gun_cannot_be_lifted_off_the_bar(self):
        """Shove the gun anywhere but along the bar's own axis, a quarter of a
        millimetre at a time, and it never clears the bar. The bayonet let it out at
        one elevation by design and at any elevation in practice."""
        parts = {p.label: p for p in assembly(SPEC).children}
        gun, bar = parts["cannon"], parts["trunnion"]
        for dx, dz in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            for step in np.arange(0.25, 3.6, 0.5):
                shoved = Pos(dx * float(step), 0, dz * float(step)) * gun
                assert (shoved & bar).volume > 1e-9, f"shoved {dx},{dz} by {step}"

    def test_the_bar_reaches_from_bracket_to_bracket(self, parts):
        """Through the barrel and into both brackets: a press fit at each end, and
        no way for the gun to reach either of them."""
        box = parts["trunnion"].bounding_box()
        outside = SPEC.gap / 2 + SPEC.bracket
        assert -outside >= box.min.Y and outside <= box.max.Y


def test_the_gun_can_be_built_without_sockets():
    """The barrel alone is still a model in its own right."""
    assert cannon(CannonSpec(trunnions=None)).is_valid
    assert TrunnionSpec().socket >= TrunnionSpec().side
