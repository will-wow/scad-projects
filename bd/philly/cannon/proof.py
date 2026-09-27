"""A proof piece: a patch of deck with a slide on it, to try a carriage against.

Proof, in the gunnery sense -- the round fired to prove a new gun before it is
issued. This is the same idea for the print: the slide and the planking it is
sunk into, cut down to something that comes off the bed in a few minutes, so a
carriage's clamps can be tried on the real rail without committing to a hull.

The rail is the same for both guns. Their carriages are the same length, run the
same distance, and clip to the same `Slide`, so `proof` builds an identical rail
for either; only the deck around it differs, being as wide as that gun's trucks
stand. The 12-pounder's is the wider, and takes either carriage.

What it is for is the fit that no measurement settles: whether the clamps go on
with a thumb, whether the carriage runs chock to chock without binding, and
whether it stays on when the piece is turned over and shaken.

    just watch cannon/proof.py
    just build --model cannon.proof:model=proof-12 --model cannon.proof:nine=proof-9
"""

from __future__ import annotations

from dataclasses import dataclass, field

from build123d import Align, Box, BuildPart, Location, Locations, Part, add
from ocp_vscode import show_object

from cannon.cannon import NINE_POUNDER
from cannon.carriage import CarriageSpec
from cannon.slide import slide


@dataclass(frozen=True)
class ProofSpec:
    carriage: CarriageSpec = field(default_factory=CarriageSpec)

    deck: float = 2.0  # the hull's planking, so the rail is sunk as deeply as it will be
    margin: float = 2.0  # deck outside the trucks, and beyond each chock


def proof(spec: ProofSpec) -> Part:
    """The pad and its rail, standing on the bed the way the hull's deck does."""
    truck = spec.carriage
    rig = truck.slide
    fore = truck.fore - rig.chock - spec.margin
    aft = truck.aft + rig.travel + rig.chock + spec.margin

    # Laid exactly as `guns.Mount.slide` lays it, from the carriage's fore end to
    # its aft end plus a full recoil, with z = 0 the deck's face. Built before
    # the builder opens: inside it, the bare Polygon of the rail's section is
    # taken as a sketch operation on the part and refused.
    rail = slide(rig, truck.fore, truck.aft + rig.travel)

    with BuildPart() as piece:
        with Locations(((fore + aft) / 2, 0, 0)):
            Box(
                aft - fore,
                2 * (truck.half_width + spec.margin),
                spec.deck,
                align=(Align.CENTER, Align.CENTER, Align.MAX),
            )
        add(rail)

    assert piece.part is not None
    return piece.part.moved(Location((0, 0, spec.deck)))


def model() -> Part:
    return proof(ProofSpec())


def nine() -> Part:
    """The 9-pounders' pad. The rail on it is the bow gun's rail exactly."""
    return proof(ProofSpec(carriage=CarriageSpec(gun=NINE_POUNDER, axis_height=14.64)))


def main() -> None:
    spec = ProofSpec()
    pad = proof(spec)
    box = pad.bounding_box().size
    rig = spec.carriage.slide
    print(
        f"proof piece {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm; "
        f"the carriage runs {rig.travel:.0f}mm between its chocks, "
        f"each clamp spreading {rig.snap:.2f}mm to clip on"
    )
    show_object(pad, name="proof")


if __name__ == "__main__":
    main()
