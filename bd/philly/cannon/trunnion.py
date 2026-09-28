"""The trunnions: the pin the gun swings on, and the key that holds it in.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side resting in the carriage's trunnion beds under a cap square. Here they are
one pin, bored right through the piece and standing out far enough each side to
reach the outside of both brackets -- the way a wheelwright hangs a wheel, not
the way a founder cast a gun, but it is what makes the thing survive a child.

The pin is not round. Two flats are milled down its length, so that seen end on
it is `shank` across the round and `waist` across the flats, and the slot it
drops through in each bracket is a shade wider than the waist and a good deal
narrower than the shank. It therefore passes only when the flats line up with
the slot, which happens at one angle of the gun and no other; everywhere else
its corners are under the lips, held by solid bracket rather than by anything
springy. The hole through the barrel is the same shape, so turning the gun
turns the pin.

That is the third scheme. Two pegs pressed into blind sockets fell out of the
barrel while the gun was being offered up. Sprung lips either side of the slot
held it for an afternoon and then took a set: a lip 0.7mm thick bending across
the printed layers creeps a few microns a time, and after a few hundred clips
the 0.12mm it had to give with was gone. A bayonet has nothing to creep.

It prints lying on a flat, which is both the easier print -- a real contact
patch instead of a 3.5mm2 circle -- and the stronger part, since the layers now
run along the pin rather than across the way it is loaded. That works only
while the waist is no wider than `shank / sqrt 2`; wider, and the arcs undercut
the flat by more than `max_overhang` on the way down to the bed.

Every dimension is in printed millimetres, not calibres -- these are fits, and
a fit does not scale. `CannonSpec` bores its hole and `CarriageSpec` cuts its
slots from one of these.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Axis, Box, BuildPart, Cylinder, Mode, Part, Pos, chamfer
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    shank: float = 2.6  # diameter across the round
    waist: float = 1.7  # across the flats: what has to pass the bracket's slot
    # Right through the gun and both brackets. One length serves both carriages:
    # the 9-pounder's brackets are closer together, so on that gun the ends
    # stand a couple of tenths proud, which reads as the flat end of a trunnion.
    length: float = 11.7

    stand_off: float = 1.2  # barrel surface to a bracket's inner face
    running: float = 0.3  # diameter clearance in the bed, so the gun turns on it
    slot_fit: float = 0.15  # clearance in the bracket's slot, where it drops through
    key_fit: float = 0.1  # clearance in the barrel's keyed hole, so it can be pushed in

    # The gun's elevation, in degrees, at which the flats line up with the slots
    # and the gun lifts out. Negative: the muzzle goes down, which the carriage
    # allows and the quoin does not resist. Both the gun's hole and the
    # brackets' slots are cut from this one number, so they cannot disagree.
    release: float = -16.0

    entry: float = 0.3  # chamfer on both ends, so the pin finds each hole
    max_overhang: float = 45.0

    @property
    def bed(self) -> float:
        """Diameter of the carriage's bed, where the pin comes to rest."""
        return self.shank + self.running

    @property
    def slot(self) -> float:
        """Width of the way in: wider than the waist, narrower than the shank."""
        return self.waist + self.slot_fit

    @property
    def socket(self) -> float:
        """Diameter of the round part of the barrel's hole."""
        return self.shank + self.key_fit

    @property
    def keyway(self) -> float:
        """Across the flats of the barrel's hole: what keys the pin to the gun."""
        return self.waist + self.key_fit

    def presents(self, turned: float) -> float:
        """How wide the pin is across the slot, `turned` degrees from lined up.

        The support width of a round bar with two flats. Lined up it is the
        waist and it passes; turned, the corners where flat meets arc swing out
        past the slot's walls and it does not.
        """
        radius, half = self.shank / 2, self.waist / 2
        corner = math.sqrt(max(radius**2 - half**2, 0.0))
        angle = math.radians(abs(turned))
        return 2 * min(radius, corner * math.sin(angle) + half * math.cos(angle))

    def locked_by(self, turned: float) -> float:
        """How far the pin's corners stand under the lips, `turned` from lined up."""
        return self.presents(turned) - self.slot


def trunnion(spec: TrunnionSpec) -> Part:
    """The pin, lying on a flat with its length along x, chamfered both ends."""
    if spec.waist > spec.shank / math.sqrt(2):
        raise ValueError("the flats are too narrow for the pin to print lying down")

    with BuildPart() as pin:
        Cylinder(spec.shank / 2, spec.length, rotation=(0, 90, 0))
        Box(spec.length, spec.shank, spec.waist, mode=Mode.INTERSECT)
        chamfer(pin.faces().filter_by(Axis.X).edges(), spec.entry)

    assert pin.part is not None
    return pin.part.moved(Pos(0, 0, spec.waist / 2))


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    spec = TrunnionSpec()
    pin = trunnion(spec)
    box = pin.bounding_box().size
    print(
        f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm; print three. "
        f"Lined up it presents {spec.presents(0):.2f}mm to a {spec.slot:.2f}mm slot; "
        f"turned 20 degrees, {spec.presents(20):.2f}mm."
    )
    show_object(pin, name="trunnion")


if __name__ == "__main__":
    main()
