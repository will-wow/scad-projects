"""The trunnion: a square bar the gun is fixed on, pressed into the carriage.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side resting in the carriage's trunnion beds under a cap square. Here they are
one bar, bored right through the piece and pressed into both brackets -- the way
a wheelwright hangs a wheel, not the way a founder cast a gun, but it is what
makes the thing survive a child.

The bar is square and every hole it goes through is a diamond, the square stood
on a corner, so the gun does not turn on it. That fixes two things at once. A
round pin let the gun pivot, and the printed gun is not breech-heavy the way the
model is: at sparse infill the thin chase prints as nearly solid wall and the fat
breech as mostly air, so it tipped muzzle-down off its quoin. And the round holes
sagged, so the pin went in tight. A diamond is four flat faces at 45 degrees,
which is the one shape a horizontal hole can have with nothing to sag.

The gun is fixed at its carriage's `elevation`, not level: level, the barrel
would stand 0.7mm into the rail it has to fire over. So the bracket's diamond is
turned by that much from the gun's, and `diamond` swings whichever roof face that
leaves too flat back up to 45 degrees. The sliver of clearance that opens over
that one face is on the side the gun's weight never bears on.

This is the fifth scheme. Two pegs pressed 1.2mm into blind sockets fell out of
the barrel while the gun was being offered up. Sprung lips either side of a slot
held it for an afternoon and then took a set. A bayonet -- a pin with two flats,
passing a slot at one elevation -- let the gun wobble sideways out of the slot.
And a round pin pressed into two holes held the gun on and let it fall forward.

The bar prints lying on a face: a real first layer, and the layers running along
it. Its long edges are relieved, since the diamonds' corners print a little
filled and a sharp corner would jam in them before the faces met.

Every dimension is in printed millimetres, not calibres -- these are fits, and a
fit does not scale. `CannonSpec` cuts its hole and `CarriageSpec` the brackets'
from one of these.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Align, Axis, Box, BuildPart, Part, chamfer
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    side: float = 2.4  # across the bar's flats
    # Right through the gun and both brackets. One length serves both carriages:
    # it is the 12-pounder's gap plus its two brackets to within a few
    # hundredths, so there both ends come flush, and on the 9-pounder they stand
    # 0.29 proud, which reads as the flat end of a trunnion.
    length: float = 12.9

    stand_off: float = 1.2  # barrel surface to a bracket's inner face
    # How much smaller than the bar a bracket's hole is drawn. Nothing: a printed
    # hole comes out a tenth or two under size already, and that is the grip. If
    # a print will not take the bar, make this negative.
    press: float = 0.0
    # How much larger than the bar the barrel's hole is drawn. A little, since it
    # is the longest of the three fits and the bar has to slide through it; the
    # printer takes most of it back. Every 0.05 of it that survives is about 1.2
    # degrees the muzzle can droop, and the barrel clears its rail by only a
    # third of a millimetre per degree.
    key_fit: float = 0.05

    relief: float = 0.25  # chamfer on the long edges, clear of the diamonds' corners
    entry: float = 0.3  # chamfer on both ends, so the bar finds each hole
    max_overhang: float = 45.0

    @property
    def bore(self) -> float:
        """Across the flats of a bracket's hole: the press fit that holds the gun on."""
        return self.side - self.press

    @property
    def socket(self) -> float:
        """Across the flats of the barrel's hole: the fit that holds the gun's angle."""
        return self.side + self.key_fit


def _meet(
    p: tuple[float, float], d: tuple[float, float], q: tuple[float, float], e: tuple[float, float]
) -> tuple[float, float]:
    """Where the line through `p` along `d` crosses the line through `q` along `e`."""
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    return (p[0] + t * d[0], p[1] + t * d[1])


def diamond(
    across: float, turned: float = 0.0, overhang: float = 45.0
) -> list[tuple[float, float]]:
    """A square hole `across` its flats, stood on a corner about the origin.

    Returns its corners anticlockwise from the right-hand one, in a plane whose
    second axis is up as printed. `turned` degrees anticlockwise, one of its two
    roof faces leans further than `overhang` from vertical and would sag, so that
    face is swung up to `overhang` about its lower end and meets the other higher
    up. The bar still bears on the three faces left; over the fourth there is a
    sliver of clearance, nothing at the side corner and widest at the top.
    """
    radius = across / math.sqrt(2)
    right, top, left, bottom = (
        (radius * math.cos(a), radius * math.sin(a))
        for a in (math.radians(turned + 90 * k) for k in range(4))
    )
    lean = math.radians(overhang)
    rising = (
        (-math.sin(lean), math.cos(lean))
        if 45 + turned > overhang
        else (top[0] - right[0], top[1] - right[1])
    )
    falling = (
        (math.sin(lean), math.cos(lean))
        if 45 - turned > overhang
        else (top[0] - left[0], top[1] - left[1])
    )
    return [right, _meet(right, rising, left, falling), left, bottom]


def trunnion(spec: TrunnionSpec) -> Part:
    """The bar, lying on a face with its length along x, relieved and chamfered."""
    with BuildPart() as bar:
        Box(spec.length, spec.side, spec.side, align=(Align.CENTER, Align.CENTER, Align.MIN))
        chamfer(bar.edges().filter_by(Axis.X), spec.relief)
        chamfer(bar.faces().filter_by(Axis.X).edges(), spec.entry)

    assert bar.part is not None
    return bar.part


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    spec = TrunnionSpec()
    bar = trunnion(spec)
    box = bar.bounding_box().size
    print(
        f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm; print three and a spare. "
        f"It presses into {spec.bore:.2f}mm in each bracket and slides through "
        f"{spec.socket:.2f}mm in the barrel."
    )
    show_object(bar, name="trunnion")


if __name__ == "__main__":
    main()
