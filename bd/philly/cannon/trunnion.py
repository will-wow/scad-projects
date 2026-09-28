"""The trunnion: the pin the gun swings on, pressed into the carriage.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side resting in the carriage's trunnion beds under a cap square. Here they are
one pin, bored right through the piece and pressed into both brackets -- the way
a wheelwright hangs a wheel, not the way a founder cast a gun, but it is what
makes the thing survive a child.

The pin is round and plain. It presses into a hole in each bracket and the
barrel turns on it, so the only fit that has to be a fit is the bracket's, and
the gun's angle has nothing to do with anything. The gun is then captive: there
is no way out of a hole the pin passes through, and taking it apart means
pushing the pin back out with a needle.

That is the fourth scheme, and the three before it all failed the same way, by
leaving the gun a way out. Two pegs pressed 1.2mm into blind sockets fell out of
the barrel while the gun was being offered up. Sprung lips either side of a slot
held it for an afternoon and then took a set. And a bayonet -- a pin with two
flats, passing a narrow slot at one elevation and under solid bracket at every
other -- printed, and let the gun wobble sideways out of its slots: a slot the
pin can get into is a slot it can work along. A hole cannot be worked along.

It prints standing on a small head, which is 13.9mm2 of first layer instead of
the 5.3mm2 the shank alone would stand on, and which seats against the outside
of a bracket, so there is one depth to press it to and no judgement in it.

Every dimension is in printed millimetres, not calibres -- these are fits, and a
fit does not scale. `CannonSpec` bores its hole and `CarriageSpec` bores the
brackets' from one of these.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Align, Axis, BuildPart, Cylinder, Locations, Part, chamfer
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    shank: float = 2.6  # diameter of the pin
    # Right through the gun and both brackets. One length serves both carriages:
    # it is the 12-pounder's gap plus its two brackets to within a few
    # hundredths, so there the far end comes flush, and on the 9-pounder it
    # stands 0.57 proud, which reads as the flat end of a trunnion.
    length: float = 11.7

    # The head: what the pin stands on to print, and what it seats against.
    head: float = 4.2
    head_thick: float = 0.6

    stand_off: float = 1.2  # barrel surface to a bracket's inner face
    running: float = 0.3  # diameter clearance in the barrel, so the gun turns on it
    # How much narrower than the pin a bracket's hole is drawn. Nothing: a 2.6mm
    # hole comes off the printer a tenth or two under size already and that is
    # the whole of the grip, where drawn interference would only hoop-stress a
    # 1.4mm bracket. If a print will not take the pin, make this negative rather
    # than reaming the bracket.
    press: float = 0.0

    entry: float = 0.3  # chamfer on the free end, so the pin finds its holes
    max_overhang: float = 45.0

    @property
    def bore(self) -> float:
        """Diameter of a bracket's hole: the press fit that holds the gun on."""
        return self.shank - self.press

    @property
    def socket(self) -> float:
        """Diameter of the barrel's hole: a running fit, since the gun turns on the pin."""
        return self.shank + self.running

    @property
    def height(self) -> float:
        """Head and shank together: the whole part, as it stands on the bed."""
        return self.head_thick + self.length


def trunnion(spec: TrunnionSpec) -> Part:
    """The pin, standing on its head with its length up z, chamfered at the top.

    Nothing overhangs: the shank steps inward off the head, so the only downward
    face in the part is the head's own underside, lying on the bed.
    """
    if spec.head <= spec.bore:
        raise ValueError("the head is no wider than the hole; it would press straight through")

    from_the_bed = (Align.CENTER, Align.CENTER, Align.MIN)
    with BuildPart() as pin:
        Cylinder(spec.head / 2, spec.head_thick, align=from_the_bed)
        with Locations((0, 0, spec.head_thick)):
            Cylinder(spec.shank / 2, spec.length, align=from_the_bed)
        chamfer(pin.faces().sort_by(Axis.Z)[-1].edges(), spec.entry)

    assert pin.part is not None
    return pin.part


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    spec = TrunnionSpec()
    pin = trunnion(spec)
    box = pin.bounding_box().size
    print(
        f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm; print three and a spare. "
        f"It presses into {spec.bore:.2f}mm in each bracket, and the barrel turns "
        f"on it in {spec.socket:.2f}mm."
    )
    show_object(pin, name="trunnion")


if __name__ == "__main__":
    main()
