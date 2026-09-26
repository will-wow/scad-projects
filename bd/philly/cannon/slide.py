"""The slide: the rail on the deck that a carriage runs out and recoils along.

Gunboats and galleys often worked a gun on a slide rather than on free trucks,
and it suits a toy: the gun runs out, recoils, and stays aboard. The slide is a
low timber rail printed as part of the deck, with a **chock** across each end.
Its **head** is wider than its **neck**, so it has a lip down each side.

The carriage clips on from above. Under its bed, in a tunnel, it carries two
**clamps**: springy arms that run fore and aft, fixed at their middles, with a
hooked **jaw** at each end that snaps under the slide's lip. Once clipped on the
carriage cannot lift off whichever way up the boat is, and the chocks stop it
at both ends of its run: run out at one, recoiled at the other.

Every dimension is in printed millimetres. Like the trunnion pegs, these are
fits, and a fit does not scale; both the hull and the carriage cut their parts
from one `Slide`.

The clamps bend sideways, in the plane of the print bed, so the strain runs
along the extruded lines rather than across the layers, which is where PLA is
weak.

    just watch cannon/slide.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Box, Part, Plane, Polygon, Pos, extrude
from ocp_vscode import show_object


@dataclass(frozen=True)
class Slide:
    neck: float = 2.0  # width of the rail below its lip
    neck_height: float = 1.2  # where the lip starts, above the deck
    lip: float = 0.6  # how far the head overhangs the neck each side, at 45 degrees
    side: float = 0.4  # the head's upright face, above the lip
    lead: float = 0.4  # chamfer on the head's top edges, that the jaws ride down
    fit: float = 0.15  # running clearance, per side
    sink: float = 0.5  # how far the rail is set into the deck, so it merges into it

    clamp: float = 1.0  # a clamp's thickness: the dimension it bends through
    jaw: float = 3.0  # length of the hooked end of each clamp
    root: float = 3.0  # length of the block fixing a clamp's middle to its bracket
    chock: float = 2.0  # length of the stop across each end
    travel: float = 8.0  # how far the carriage recoils, chock to chock

    max_overhang: float = 45.0

    @property
    def head(self) -> float:
        return self.neck + 2 * self.lip

    @property
    def height(self) -> float:
        """The rail's top, above the deck."""
        return self.neck_height + self.lip + self.side + self.lead

    @property
    def reach(self) -> float:
        """A clamp's outer face from the centreline: half the width they take."""
        return self.head / 2 + self.fit + self.clamp

    @property
    def snap(self) -> float:
        """How far each jaw is pushed out on its way over the head."""
        return self.lip - self.fit

    def strain(self, arm: float) -> float:
        """Peak bending strain in a clamp `arm` long, pushed out by `snap` at its end."""
        return 1.5 * self.clamp * self.snap / arm**2

    def profile(self) -> tuple[tuple[float, float], ...]:
        """The rail's section, as (y, z) from its sunk foot, anticlockwise.

        The lip's underside is the head's only overhang, at 45 degrees, so the
        rail prints with the hull.
        """
        n, h = self.neck / 2, self.head / 2
        under = self.neck_height + self.lip
        half = (
            (n, -self.sink),
            (n, self.neck_height),
            (h, under),
            (h, under + self.side),
            (h - self.lead, self.height),
        )
        return (*half, *((-y, z) for y, z in reversed(half)))

    def jaw_profile(self, side: int) -> tuple[tuple[float, float], ...]:
        """A jaw's section, (y, z), on the `side` of the rail; its bottom is the deck.

        The rail's profile grown by `fit`: the jaw's inner face is the neck
        offset by it, and its top is the lip's underside offset square to itself
        by it, which drops that 45-degree line by fit * (sqrt 2 - 1) where it
        meets the neck. Below, a lead-in at 45 degrees, so pressing the carriage
        down onto the head spreads the clamps rather than jamming.

        Anticlockwise on either side, so it extrudes toward +x either way.
        """
        inner = self.neck / 2 + self.fit
        outer = self.head / 2 + self.fit
        meets = self.neck_height - self.fit * (math.sqrt(2) - 1)
        corners = (
            (outer, meets + self.lip),
            (inner, meets),
            (inner, self.lip),
            (outer, 0.0),
        )
        return tuple((side * y, z) for y, z in (corners if side > 0 else reversed(corners)))


def slide(spec: Slide, start: float, end: float) -> Part:
    """The rail along x, its neck from `start` to `end`, with a chock outside each end.

    z = 0 is the deck. The chocks are as wide as the clamps reach, so the whole
    end of each clamp comes up against one, not just its jaw, and as tall as the
    rail, which keeps them under the carriage's tunnel.
    """
    rail = extrude(Plane.YZ.offset(start) * Polygon(*spec.profile(), align=None), end - start)
    rise = spec.height + spec.sink
    for at in (start - spec.chock / 2, end + spec.chock / 2):
        rail += Pos(at, 0, rise / 2 - spec.sink) * Box(spec.chock, 2 * spec.reach, rise)
    return rail


def model() -> Part:
    return slide(Slide(), 0.0, 38.0)


def main() -> None:
    spec = Slide()
    rail = model()
    box = rail.bounding_box().size
    print(
        f"slide {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm; a clamp snaps "
        f"{spec.snap:.2f}mm over its head"
    )
    show_object(rail, name="slide")


if __name__ == "__main__":
    main()
