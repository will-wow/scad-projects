# The guns: what is built, and one question left open

Branch `claude/philly-cannon-model-6a18f9`, on top of `wow/philly` at `1235d07`
(the mast and sails). Everything below is in `cannon/`, with tests in
`tests/test_cannon.py` and `tests/test_carriage.py`.

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

## Still to do

The slide and the runners it rides in. The carriage's underside is a plain flat
bed, ready for whatever clips it to the deck; the hook-and-chamfer rail the cap
squares use would work there too.

## The open question: nothing clears the bulwark

Measured against the current hull, above the deck:

| | mm |
|---|---|
| bow rail at the stem | 16.1 |
| bow rail at x=14 | 14.1 |
| bulwark amidships (broadside guns) | 10.1 - 10.6 |
| gun's axis on its carriage | 6.2 |
| top of the muzzle swell | 8.75 |

So the bow gun points at the inside of the bow, seven millimetres below the
top, and the broadside guns are under their rail too.

Raising the gun does not fix it at any sane height: the barrel has to cross the
rail line at the stem, where it is tallest, so the trunnion axis would need to
be 19.1mm above the deck at 0 degrees, or 15.6mm at 10 degrees -- and still
15.5mm at 25, because past about 10 degrees the binding point stops moving.
That is a carriage three times its present height.

Elevation cannot do it either, and is capped anyway: past 2 degrees the breech
fouls the carriage's own bed, and at 8 degrees it is on the deck. Ending the
bed short of the breech would buy 8 degrees, which is worth doing for looks but
does not change the clearance.

What could work, in rough order of how much it disturbs:

1. **Raise the bow gun on its slide.** The bow platform carrying the bow gun is
   in the record, and the slide is the part still to be designed, so the height
   belongs there rather than in the brackets -- which are shared with the two
   9-pounders and would look wrong amidships if they grew.
2. **Cut the bow bulwark down where the gun fires.** To clear a level gun the
   rail would have to come down about 12mm, which is most of the bow bulwark.
   Worth measuring the model's bow sheer against the scan first: 16mm above the
   deck is 0.9m at full size, which may be more than the boat had.
3. **Gunports amidships** for the 9-pounders, where the gap is only 1.4mm.

This is a hull-side decision -- deck heights and sheer -- which is why it is
written down here rather than solved in `cannon/`.
