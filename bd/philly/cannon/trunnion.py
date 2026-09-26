"""The trunnions: the axle the gun swings on.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side resting in the carriage's trunnion beds under a cap square. Here they are
one pin, bored right through the piece and standing out far enough each side to
reach the outside of both brackets -- the way a wheelwright hangs a wheel, not
the way a founder cast a gun, but it is what makes the thing survive a child.

Two separate pegs pressed into blind sockets was the first try, and they fell
out of the barrel while the gun was being clipped in: 1.2mm of printed hole is
not a press fit. Through the piece there is nothing to fall out of. The barrel
grips the pin along five millimetres, and either end of the pin is trapped in a
bracket, so no part of the assembly can leave without another giving way first.

The pin prints standing on end. Every dimension is in printed millimetres, not
calibres -- these are fits, and a fit does not scale. `CannonSpec` bores its
hole and `CarriageSpec` cuts its clips from one of these.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Align, BuildPart, Cylinder, GeomType, Part, chamfer
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    shank: float = 2.6  # diameter, in the barrel and in the clips alike
    # Right through the gun and both brackets. One length serves both carriages:
    # the 9-pounder's brackets are closer together, so on that gun the ends
    # stand a couple of tenths proud, which reads as the flat end of a trunnion.
    length: float = 11.7
    press: float = 0.0  # diameter fit in the barrel; a printed hole's undersize is the grip
    running: float = 0.3  # diameter clearance in the carriage's clips, so the gun turns

    stand_off: float = 1.2  # barrel surface to a bracket's inner face
    snap: float = 0.24  # how much narrower than the pin the clip's detent is
    entry: float = 0.3  # chamfer on both ends
    max_overhang: float = 45.0

    @property
    def socket(self) -> float:
        """Diameter of the hole through the barrel."""
        return self.shank + self.press

    @property
    def bed(self) -> float:
        """Diameter of the carriage's clip, where the pin comes to rest."""
        return self.shank + self.running

    @property
    def gate(self) -> float:
        """Clear width at the detent: what the pin has to spread to clip in."""
        return self.shank - self.snap


def trunnion(spec: TrunnionSpec) -> Part:
    """The pin, standing on end, chamfered both ends so it finds either hole."""
    with BuildPart() as pin:
        Cylinder(spec.shank / 2, spec.length, align=(Align.CENTER, Align.CENTER, Align.MIN))
        chamfer(pin.edges().filter_by(GeomType.CIRCLE), spec.entry)

    assert pin.part is not None
    return pin.part


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    spec = TrunnionSpec()
    pin = trunnion(spec)
    box = pin.bounding_box().size
    print(f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm; print three")
    show_object(pin, name="trunnion")


if __name__ == "__main__":
    main()
