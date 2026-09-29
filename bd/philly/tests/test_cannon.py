"""The gun.

It prints standing on its muzzle, so most of what can go wrong is about that:
an underside the printer can't bridge, or a bore that doesn't open onto the bed.
"""

from __future__ import annotations

import math

import pytest
from build123d import Vector
from conftest import steepest_overhang

from cannon.cannon import CannonSpec, Ring, cannon, trunnion_height
from cannon.trunnion import diamond

SPEC = CannonSpec()


@pytest.fixture(scope="module")
def gun():
    return cannon(SPEC)


def test_it_is_one_valid_solid(gun):
    assert gun.is_valid
    assert len(gun.solids()) == 1


def test_it_is_the_right_size(gun):
    box = gun.bounding_box()
    # The muzzle face is on the bed, and the cascabel adds to the nominal length.
    assert abs(box.min.Z) < 1e-6
    barrel = SPEC.length * SPEC.scale
    assert barrel < box.size.Z < barrel + 3 * SPEC.calibre * SPEC.scale
    # Widest at the base ring: the breech plus the ring standing proud of it.
    widest = (SPEC.breech + 2 * SPEC.base_ring) * SPEC.calibre * SPEC.scale
    assert abs(box.size.X - widest) < 0.02 * widest


def test_the_bore_opens_onto_the_muzzle_face_and_stops_short_of_the_trunnions(gun):
    """The trunnion bar goes right through the piece, so it must find solid metal
    there: the bore is a muzzle detail only."""
    bore = SPEC.calibre * SPEC.scale
    wall = (SPEC.neck - 1) / 2 * bore
    assert not gun.is_inside(Vector(0, 0, 0.01)), "the bore should be open at the muzzle"
    assert gun.is_inside(Vector(bore / 2 + wall / 2, 0, 0.01)), "metal round the bore"
    top = SPEC.bore_length * bore
    assert not gun.is_inside(Vector(0, 0, top - bore)), "the bore runs its stated length"
    assert gun.is_inside(Vector(0, 0, top + 0.1)), "and is closed above that"
    below = trunnion_height(SPEC) + min(up for _, up in _hole()) - 0.2
    assert gun.is_inside(Vector(0, 0, below)), "solid between the bore and the bar's hole"


def _hole() -> list[tuple[float, float]]:
    bar = SPEC.trunnions
    assert bar is not None
    return diamond(bar.socket, 0.0, SPEC.max_overhang)


def test_the_hole_the_bar_goes_through_is_closed_all_round(gun):
    """Half of what makes the gun captive: its hole is a hole, not a slot, so the
    only way off the bar is along the bar. The bayonet had its slot in the
    carriage, and the printed gun worked sideways out of it."""
    height = trunnion_height(SPEC)
    across = max(along for along, _ in _hole())
    apex = max(up for _, up in _hole())
    assert not gun.is_inside(Vector(0, 0, height)), "the hole itself"
    for hand in (1, -1):
        assert gun.is_inside(Vector(hand * (across + 0.3), 0, height)), "metal beside it"
    assert gun.is_inside(Vector(0, 0, height - apex - 0.3)), "metal under it"
    assert gun.is_inside(Vector(0, 0, height + apex + 0.3)), "metal over it"


def test_the_bars_hole_stops_short_of_the_first_reinforce_ring():
    """The hole stands on a corner, so its apex points up the barrel toward the
    ring above; a notch in that ring's chamfer is what running into it would look
    like."""
    lean = math.sin(math.radians(SPEC.max_overhang))
    apex = trunnion_height(SPEC) + max(up for _, up in _hole())
    ring = min((r for r in SPEC.rings if r.at > SPEC.trunnions_at), key=lambda r: r.at)
    cal = SPEC.calibre * SPEC.scale
    foot = ring.at * SPEC.length * SPEC.scale - ring.proud * cal / lean
    assert foot - apex > 0.1, f"only {foot - apex:.2f}mm from the hole's apex to the ring"


@pytest.mark.parametrize("overhang", [45.0, 35.0])
def test_nothing_overhangs_more_than_allowed(overhang):
    """The rings, the button and the roof of the trunnion hole, all as printed."""
    gun = cannon(CannonSpec(max_overhang=overhang))
    assert steepest_overhang(gun) <= math.sin(math.radians(overhang)) + 1e-6


def test_the_rings_stand_proud_where_they_are_put():
    spec = CannonSpec(rings=(Ring(at=0.5, proud=0.5),))
    gun = cannon(spec)
    z = 0.5 * spec.length * spec.scale
    barrel = (spec.neck + spec.breech) / 4 * spec.calibre * spec.scale
    assert gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z))
    assert not gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z * 0.9))
