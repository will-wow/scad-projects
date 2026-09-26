"""The trunnions: the pegs the gun swings on.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side resting in the carriage's trunnion beds under a cap square. Here they are
printed separately and do two jobs: the shank presses into a socket bored in
the barrel, the rimbase -- the collar a real trunnion has where it meets the
piece -- bears against the bracket and keeps the peg from working out, and the
journal beyond it turns in the carriage's bed under the cap square.

Every dimension is in printed millimetres, not calibres -- these are fits, and
a fit does not scale. `CannonSpec` and `CarriageSpec` both take a TrunnionSpec
and cut their own holes from it.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    BuildPart,
    Cone,
    Cylinder,
    Locations,
    Part,
    chamfer,
)
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    shank: float = 2.6  # diameter, in the barrel and in the bed alike
    into_barrel: float = 1.2  # how deep the barrel's socket takes it
    press: float = 0.0  # diameter fit there; a printed hole's undersize is the grip

    rimbase: float = 3.4  # the collar between barrel and bracket
    stand_off: float = 1.2  # its length: barrel surface to the bracket's inner face
    journal: float = 1.4  # the part in the bed; a bracket's thickness, so it finishes flush
    running: float = 0.3  # diameter clearance in the bed, so the gun turns on it

    entry: float = 0.3  # chamfer on the end that goes into the barrel
    max_overhang: float = 45.0

    @property
    def socket(self) -> float:
        """Diameter of the barrel's socket."""
        return self.shank + self.press

    @property
    def socket_depth(self) -> float:
        return self.into_barrel + 0.2

    @property
    def bed(self) -> float:
        """Diameter of the carriage's trunnion bed."""
        return self.shank + self.running


def trunnion(spec: TrunnionSpec) -> Part:
    """One peg, shank down on the bed.

    The rimbase is wider than the bed it sits beside, so once the gun is in the
    carriage the peg cannot work its way out: the collar will not pass through.
    Its underside is chamfered at the overhang limit, which is the only place
    on the peg where the diameter steps outward.
    """
    rise = (spec.rimbase - spec.shank) / 2
    with BuildPart() as peg:
        Cylinder(spec.shank / 2, spec.into_barrel, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((0, 0, spec.into_barrel)):
            Cone(
                spec.shank / 2,
                spec.rimbase / 2,
                rise,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        with Locations((0, 0, spec.into_barrel + rise)):
            Cylinder(
                spec.rimbase / 2,
                spec.stand_off - rise,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        with Locations((0, 0, spec.into_barrel + spec.stand_off)):
            Cylinder(spec.shank / 2, spec.journal, align=(Align.CENTER, Align.CENTER, Align.MIN))
        chamfer(peg.edges().group_by(Axis.Z)[0], spec.entry)

    assert peg.part is not None
    return peg.part


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    spec = TrunnionSpec()
    peg = trunnion(spec)
    box = peg.bounding_box().size
    print(f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm")
    show_object(peg, name="trunnion")


if __name__ == "__main__":
    main()
