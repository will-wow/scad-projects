"""The trunnions: the pegs the gun swings on.

On the real gun the trunnions are cast as part of the barrel, two stubs either
side that rest in the carriage's trunnion holes under a cap square. Here they
are printed separately and do two jobs at once: the round shank is a running
fit in a socket bored into the barrel, so the gun elevates on it, and the
diamond head is a key in the carriage's bracket, so the gun cannot fall out.

Every dimension is in printed millimetres, not calibres -- these are fits, and
a fit does not scale. `CannonSpec` and `CarriageSpec` both take a TrunnionSpec
and cut their own holes from it.

    just watch cannon/trunnion.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    BuildPart,
    BuildSketch,
    Cylinder,
    Part,
    Plane,
    Rectangle,
    chamfer,
    extrude,
)
from ocp_vscode import show_object


@dataclass(frozen=True)
class TrunnionSpec:
    shank: float = 2.6  # the trunnion proper, which turns in the barrel
    shank_length: float = 2.4  # all of it: socket, then the gap to the bracket
    into_barrel: float = 1.2  # how much of that the socket takes
    running: float = 0.15  # diameter clearance in the barrel's socket

    key: float = 1.6  # the head, across the diamond's corners
    key_length: float = 0.9  # a bracket's thickness, so the head finishes flush
    keyed: float = 0.1  # clearance in the bracket's hole

    # Chamfer on the head's leading edges and the hole's inner mouth. The head
    # starts entering before the bracket has spread the full key_length, which
    # is what keeps the snap inside what PLA will take.
    lead_in: float = 0.5

    max_overhang: float = 45.0

    @property
    def socket(self) -> float:
        """Diameter of the barrel's socket."""
        return self.shank + self.running

    @property
    def socket_depth(self) -> float:
        return self.into_barrel + 0.2

    @property
    def hole(self) -> float:
        """The bracket's diamond hole, across the corners."""
        return self.key + self.keyed

    @property
    def spread(self) -> float:
        """How far a bracket must bow out to let the head past."""
        return self.key_length - self.lead_in


def trunnion(spec: TrunnionSpec) -> Part:
    """One peg, shank down on the bed and head up: no overhang anywhere."""
    with BuildPart() as peg:
        Cylinder(spec.shank / 2, spec.shank_length, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with BuildSketch(Plane.XY.offset(spec.shank_length)):
            Rectangle(spec.key / math.sqrt(2), spec.key / math.sqrt(2), rotation=45)
        extrude(amount=spec.key_length)
        chamfer(peg.edges().group_by(Axis.Z)[-1], spec.lead_in / 2)

    assert peg.part is not None
    return peg.part


def model() -> Part:
    return trunnion(TrunnionSpec())


def main() -> None:
    peg = model()
    box = peg.bounding_box().size
    print(f"trunnion {box.X:.2f} x {box.Y:.2f} x {box.Z:.2f} mm")
    show_object(peg, name="trunnion")


if __name__ == "__main__":
    main()
