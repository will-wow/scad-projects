# The guns: what is built

Everything below is in `cannon/`, with tests in `tests/test_cannon.py` and
`tests/test_carriage.py`.

## What is built

Four printed parts per gun, all in the default `just build`:

| part | module | size at 1:55 |
|---|---|---|
| barrel | `cannon/cannon.py` | 7.0 x 7.0 x 48.4mm |
| carriage | `cannon/carriage.py` | 30.0 x 11.5 x 7.9mm |
| trunnion peg (x2) | `cannon/trunnion.py` | 3.4 x 3.4 x 3.8mm |
| cap square (x2) | `cannon/cap_square.py` | 6.1 x 2.5 x 1.6mm |

`cannon/assembly.py` puts them together for looking at -- a `RevoluteJoint` on
the trunnion axis, so `elevation` swings the gun -- and is not printed. The
tests assert no two parts in it share any volume.

The barrel is a solid of revolution with its parts named as a gunfounder would
(swell of the muzzle, neck, astragal, reinforce rings, base ring, cascabel),
proportioned in calibres, so the bow 12-pounder and the broadside 9-pounders
are one `CannonSpec` at two calibres. It is bored only three calibres deep so
the trunnion sockets bear on solid metal.

The gun drops into open beds notched into each bracket's rail; a cap square
slides aft over each trunnion and clicks past a detent. Nothing is a spring: an
earlier version flexed the brackets, which at this scale worked out at 6.5%
strain against the 2% PLA takes. The rail is hooked outboard and chamfered
inboard, so lifting a strap drives it further under the hook.

Fits live in `TrunnionSpec`, in printed millimetres -- a clearance does not
scale -- and the barrel, carriage and cap square all cut their geometry from
that one spec. The running fit is 0.15mm per side.

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
