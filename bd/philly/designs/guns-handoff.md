# The guns: what is built

Everything below is in `cannon/`, with tests in `tests/test_cannon.py` and
`tests/test_carriage.py`.

## What is built

Three printed parts per gun, all in the default `just build`:

| part | module | size at 1:55 |
|---|---|---|
| barrel | `cannon/cannon.py` | 7.0 x 7.0 x 48.4mm |
| carriage | `cannon/carriage.py` | 30.0 x 12.1 x 16.1mm |
| trunnion pin | `cannon/trunnion.py` | 2.6 x 2.6 x 10.5mm |

`cannon/assembly.py` puts them together for looking at -- a `RevoluteJoint` on
the trunnion axis, so `elevation` swings the gun -- and is not printed. The
tests assert that the only metal any two of them share is the four detents.

The barrel is a solid of revolution with its parts named as a gunfounder would
(swell of the muzzle, neck, astragal, reinforce rings, base ring, cascabel),
proportioned in calibres, so the bow 12-pounder and the broadside 9-pounders
are one `CannonSpec` at two calibres. It is bored only three calibres deep so
the trunnion pin bears on solid metal.

The pin goes right through the piece and reaches the outside of both brackets.
The top of each bracket is a **clip**: a round bed with a way in above it,
pinched by a **detent** the pin clicks past, and the two **lips** either side of
that way in are cut free of the bracket by a slot apiece. A lip is 0.7mm thick
on a 3.9mm arm and is strained 0.8% by the pin going by; its slot closes after
half a millimetre, which is four times the give the detent asks, so a lip cannot
be bent far enough to break. `CarriageSpec.lip_strain` is asserted under one
percent.

This is the third scheme. The brackets themselves were the spring first (6.5%
strain, hopeless), then separate pegs in blind sockets under sliding cap squares
-- which printed, and then fell apart in the hand: the pegs would not stay in
1.2mm of printed hole, and a 2.5mm cap square has no room for a groove and a
hook. HOW-IT-WORKS.md Part 12 records both.

Fits live in `TrunnionSpec`, in printed millimetres -- a clearance does not
scale -- and the barrel and the carriage both cut their geometry from that one
spec. The bed is 0.15mm per side over the pin; the detent stands 0.12mm into its
path on either lip.

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
