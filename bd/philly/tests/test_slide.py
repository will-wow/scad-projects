"""The slide and the clamps that hold a carriage on it.

This is the one spring in the gun, so the questions are the spring's: does it
clear the slide when it should, is it caught under the lip when it should be,
and does clipping it on bend it further than PLA will take?
"""

from __future__ import annotations

import math

import pytest
from build123d import Plane, Pos, Vector, section
from conftest import steepest_overhang

from cannon.cannon import NINE_POUNDER
from cannon.carriage import CarriageSpec, carriage
from cannon.proof import ProofSpec, proof
from cannon.slide import Slide, slide

SPEC = CarriageSpec()
RIG = SPEC.slide
LIMIT = math.sin(math.radians(RIG.max_overhang)) + 1e-6

# PLA yields at a little over 2%; keep the clamps to half of that, since a toy
# gets clipped on and off far more often than a snap fit usually is.
STRAIN = 0.01


@pytest.fixture(scope="module")
def truck():
    return carriage(SPEC)


@pytest.fixture(scope="module")
def rail():
    """The slide under the carriage as it stands run out: from its front to its tail."""
    return slide(RIG, SPEC.fore, SPEC.aft + RIG.travel)


def test_the_slide_is_one_valid_solid(rail):
    assert rail.is_valid
    assert len(rail.solids()) == 1


def test_the_slide_prints_with_the_hull():
    """Laid on a bare bed it overhangs only under its lip, at 45 degrees; in the
    hull it stands on the deck, so its sunk foot is nothing to print."""
    assert steepest_overhang(slide(Slide(sink=0.0), 0.0, 20.0)) <= LIMIT


def test_the_carriage_runs_on_the_slide_without_touching_it(truck, rail):
    assert (truck & rail).volume < 1e-9


def test_the_jaws_are_caught_under_the_lip(truck, rail):
    """What keeps the carriage aboard upside down: straight above each jaw is
    the slide's head, so the carriage cannot lift off without spreading the
    clamps."""
    y = RIG.neck / 2 + RIG.fit + 0.1
    for x in (SPEC.fore + RIG.jaw / 2, SPEC.aft - RIG.jaw / 2):
        jaw = Vector(x, y, RIG.lip + 0.1)
        assert truck.is_inside(jaw), "the jaw is there"
        assert rail.is_inside(jaw + Vector(0, 0, RIG.neck_height)), "and the head is over it"


def test_the_carriage_lifts_by_no_more_than_the_fit(truck, rail):
    """The lip's underside is offset square to itself by the fit, which at 45
    degrees is fit * sqrt 2 of room upward; raised that far it is free, and any
    higher it is in the lip."""
    play = RIG.fit * math.sqrt(2)
    assert (Pos(0, 0, 0.9 * play) * truck & rail).volume < 1e-9
    assert (Pos(0, 0, play + 0.05) * truck & rail).volume > 1e-4


def test_the_clamps_can_spread_over_the_head():
    """Each jaw has to clear the head's widest point, and there must be room
    between a clamp and its bracket for it to go."""
    assert RIG.snap > 0
    assert SPEC.gap / 2 - RIG.reach > RIG.snap


def test_clipping_on_strains_the_clamps_within_what_pla_takes():
    assert RIG.strain(SPEC.arm) < STRAIN


def test_the_chocks_stop_the_carriage_at_both_ends(truck, rail):
    """Just touching at either end of its run, and a tenth further would be into a chock."""
    assert (truck & rail).volume < 1e-9
    assert (Pos(-0.1, 0, 0) * truck & rail).volume > 1e-4, "run out"
    recoiled = Pos(RIG.travel, 0, 0) * truck
    assert (recoiled & rail).volume < 1e-9
    assert (Pos(RIG.travel + 0.1, 0, 0) * truck & rail).volume > 1e-4, "recoiled"


class TestProofPiece:
    """The test print: a patch of deck with a rail on it, to try a carriage against.

    It is only worth printing if it behaves like the hull, so what is checked is
    that the rail on it is the hull's rail exactly and that there is deck under
    the carriage wherever the carriage can get to.
    """

    @pytest.fixture(scope="class")
    def pad(self):
        return proof(ProofSpec())

    def test_it_is_one_valid_solid(self, pad):
        assert pad.is_valid
        assert len(pad.solids()) == 1

    def test_it_prints_deck_down(self, pad):
        assert abs(pad.bounding_box().min.Z) < 1e-6
        assert steepest_overhang(pad) <= LIMIT

    def test_the_rail_on_it_is_the_one_the_hull_gets(self, pad, rail):
        """Otherwise the print proves nothing about the boat."""
        on_deck = Pos(0, 0, ProofSpec().deck) * rail
        assert (on_deck - pad).volume < 1e-6

    def test_both_guns_get_the_same_rail(self):
        """The carriages are the same length and run the same distance, so only the
        deck around the rail differs -- the 12-pounder's trucks stand wider."""
        nine = CarriageSpec(gun=NINE_POUNDER, axis_height=14.64)
        assert (SPEC.fore, SPEC.aft, SPEC.slide) == (nine.fore, nine.aft, nine.slide)
        assert proof(ProofSpec(carriage=nine)).bounding_box().size.Y < (
            proof(ProofSpec()).bounding_box().size.Y
        )

    def test_there_is_deck_under_the_carriage_all_along_its_run(self, pad):
        """The check `guns.fit_guns` makes against the hull, made against the pad:
        deck under each corner of the carriage, and open air over it."""
        deck = ProofSpec().deck
        for recoil in (0.0, RIG.travel):
            for x in (SPEC.fore, SPEC.aft):
                for y in (-SPEC.half_width, SPEC.half_width):
                    under = Vector(x + recoil, y, deck - 0.3)
                    assert pad.is_inside(under), f"deck under ({x + recoil:.1f}, {y:.1f})"
                    over = Vector(x + recoil, y, deck + RIG.height + 0.5)
                    assert not pad.is_inside(over), "and nothing over it"


class TestTabs:
    """The way out if a bed will not hold a carriage: it stands on two strips
    30mm long and 1.4mm wide, under 16mm of part."""

    def test_they_are_off_unless_asked_for(self, truck):
        """Nothing in the boat is built with them -- they would foul the hull."""
        assert SPEC.tabs == 0.0
        tabbed = carriage(CarriageSpec(tabs=5.0))
        assert tabbed.bounding_box().max.Y > truck.bounding_box().max.Y
        assert len(tabbed.solids()) == 1, "each pad is merged into a bracket, not loose"

    def test_they_spread_the_first_layer(self):
        """155mm2 becomes 220, and the extra is at the corners, where peel starts."""
        plain = section(carriage(SPEC), Plane.XY.offset(0.05))
        tabbed = section(carriage(CarriageSpec(tabs=5.0)), Plane.XY.offset(0.05))
        assert sum(f.area for f in tabbed.faces()) > 1.35 * sum(f.area for f in plain.faces())
