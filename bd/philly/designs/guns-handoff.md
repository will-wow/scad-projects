# The guns: what is built

Everything below is in `cannon/`, with tests in `tests/test_cannon.py` and
`tests/test_carriage.py`.

## What is built

Three printed parts per gun, all in the default `just build`:

| part | module | size at 1:55 |
|---|---|---|
| barrel | `cannon/cannon.py` | 8.3 x 8.3 x 52.6mm |
| carriage | `cannon/carriage.py` | 30.0 x 13.3 x 15.9mm |
| trunnion pin | `cannon/trunnion.py` | 2.6 x 2.6 x 11.7mm |

`cannon/assembly.py` puts them together for looking at -- a `RevoluteJoint` on
the trunnion axis, so `elevation` swings the gun -- and is not printed. The
tests assert that no two of them share any metal, and that the gun lifts out of
its carriage at one angle and no other.

The barrel is a solid of revolution with its parts named as a gunfounder would
(swell of the muzzle, neck, astragal, reinforce rings, base ring, cascabel),
proportioned in calibres, so the bow 12-pounder and the broadside 9-pounders
are one `CannonSpec` at two calibres. It is bored only three calibres deep so
the trunnion pin bears on solid metal.

Every one of those proportions is measured off the Smithsonian's scan rather
than assumed. The first printed gun felt thin in the hand, and it was: the
piece runs 2.27 calibres at the neck to 3.70 at the breech, where the model had
2.1 to 2.8, and is 22.6 calibres long where the model had 20.8. Measured
end-on and independently, the starboard 9-pounder comes to 2.23 and 3.37 over
21.7 calibres, so the two pieces agree. `designs/measure_scan.py` prints the
numbers for both.

The pin goes right through the piece and reaches the outside of both brackets,
and it is not round: two flats down its length make it 2.6mm across the round
and 1.7mm across the flats, against a 1.85mm slot in each bracket. So it drops
into its beds at one angle of the gun -- muzzle down 16 degrees -- and at every
other angle its corners are under the lips, held by solid bracket. The barrel's
hole carries the same flat, so turning the gun turns the pin. Where the gun
rests on its quoin it is locked by 0.42mm.

This is the third scheme, and the two before it both failed in the hand rather
than on paper. Pegs in blind sockets under sliding cap squares fell apart during
assembly. Sprung lips either side of the slot held the gun for an afternoon of
play and then took a set: the strain was inside what PLA yields at, but nothing
in that number says what a thousand cycles of creep will do to 0.12mm of travel.
A bayonet has no travel to lose. HOW-IT-WORKS.md Part 12 records both.

Fits live in `TrunnionSpec`, in printed millimetres -- a clearance does not
scale -- and the barrel and the carriage both cut their geometry from that one
spec, `release` included, so the gun's hole and the brackets' slots cannot
disagree about the angle. The bed is 0.15mm per side over the pin.

Two things learned the hard way, both recorded in the code: a `BuildSketch`
opened inside a helper function silently goes nowhere, because build123d only
nests builders opened in the same Python frame; and fine cuts must be made
after the final `scale()`, or the slivers they leave shrink below what OCCT
will mesh and the 3MF comes out non-manifold.

## Fitted to the hull

Done: the guns stand in the boat on slides printed into the decks, at the
scan's heights, and fire over the rail. See `guns.py`, `cannon/slide.py`, and
HOW-IT-WORKS.md Part 12. The plan they came from is
[`guns-integration-plan.md`](guns-integration-plan.md); where the build departs
from it is noted at its top.
