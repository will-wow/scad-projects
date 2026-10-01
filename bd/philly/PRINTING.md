# Printing the hull

Notes for getting a printable — and floatable — model out of `just build`.

## Will it float?

Yes, comfortably, and at any infill you would plausibly choose. PLA is denser
than water (1.24 g/cm³), so a solid lump of it sinks; this hull floats because
it encloses far more air than it contains plastic.

At 300mm LOA with the current spec, the modelled solid is **176.3 cm³** inside
an external envelope of **408.4 cm³**. Everything follows from that ratio. (The
guns' slides have since added 0.9 cm³ to the hull, which moves the table below
by less than its rounding. The joinery -- knees, benches and keelson, less
the deck seams -- adds 6.1 cm³ more. It prints as nearly all wall, so call it
8 g and about half a millimetre of draft.)

Draft is measured up from the bottom of the print, and freeboard up from the
waterline to the lowest point of the rail, amidships, which stands 21.7mm
above the bottom.

|       Infill |    Mass |   Draft | Freeboard |
| -----------: | ------: | ------: | --------: |
|          10% |  21.9 g |  1.4 mm |   20.3 mm |
|          15% |  32.8 g |  2.1 mm |   19.6 mm |
|          25% |  54.6 g |  3.5 mm |   18.2 mm |
|          40% |  87.4 g |  5.5 mm |   16.2 mm |
| 100% (solid) | 218.6 g | 12.9 mm |    8.8 mm |

Two worth noting:

- **Even solid PLA floats**, with 8.8mm of freeboard at the lowest point of
  the rail.
- **Even a waterlogged print floats.** If every infill void fills with water
  (182.6 g at 15% infill) it settles to 10.9mm and stays there.

The fittings barely register: mast, sails, awning and its canvas together are
36.0 cm³, so at 15% infill they add 6.7 g and about a third of a millimetre of
draft. The guns weigh more than their size suggests, because parts that small
print as nearly all wall: three barrels, three carriages and their three trunnion
bars are 14.4 cm³, about 18 g, and another 1.2mm of draft.

So buoyancy is not the thing to design for. Water _getting inside the hull_ is.

## The parts

`just build` writes one file per part, because each wants a different
orientation and a different profile. The rig and the hull:

| File                             | Size                  | Orientation                | Notes                             |
| -------------------------------- | --------------------- | -------------------------- | --------------------------------- |
| `philadelphia-hull.3mf`          | 300 x 84.5 x 31.2mm   | as exported, bottom down   | the watertightness settings below |
| `philadelphia-mast.3mf`          | 200.8 x 93.0 x 5.0mm  | as exported, lying flat    | needs a 200mm bed axis            |
| `philadelphia-sails.3mf`         | 69 x 174.5 x 6.5mm    | as exported, flat          | two separate sails in one file    |
| `philadelphia-awning.3mf`        | 148.3 x 72.1 x 34.7mm | as exported, **roof down** | legs point up; do not flip it     |
| `philadelphia-awning-canvas.3mf` | 149.6 x 61.3 x 5.6mm  | as exported, flat          | print it with the sails' settings |

It also writes the gun parts -- `gun` and `carriage` for the 12-pounder,
`gun-9` and `carriage-9` for the 9-pounders, and one `trunnion` bar for each of
the three -- each in its own print orientation; the README's section on the guns
covers how they print and how many of each.

The carriages print standing on the bed as exported. Their clamps are arms a
millimetre wide with a hooked jaw at each end, and the jaws are what clip onto
the slide, so they need to come out true: turn on elephant's-foot compensation,
since a jaw squashed out at the first layer will bind on the slide. If a
carriage is too stiff to clip on, ease the jaws' lead-ins rather than the
slide, which is part of the hull.

A carriage is the one part here that is hard to keep on the bed. It stands on
two strips 30mm long with a 16mm part over them, and at 1.4mm wide they peeled
off three times running. They are 2.0 now, and the brackets also spread at 45
degrees where they meet the bed, into room going spare inboard of the trucks and
outboard of the clamps: 253mm2 of first layer instead of 191, each strip 3.2mm
wide instead of 2.0, and a feathered edge rather than a square one, which is
where peel starts.
It needs no trimming and reads as a plinth under a millimetre tall.

Note that elephant's-foot compensation eats into that spread, which is what it
is there for; without the spread the compensation comes off the strips
themselves.

If a carriage binds on its slide or will not clip on, the thing to print next is
not another hull: `just build --model cannon.proof:model=proof-12` writes a patch
of deck with the same rail sunk into it, two grams and a few minutes, and the
same carriage clips to it.

The brackets are cut right through with a diamond for the trunnion bar, and the
bar is a press fit in them, so what matters here is flow and hole shrinkage: a
printed hole comes out undersize, and that undersize is the grip. Drawn nominal
it took more force than a fit assembled by hand should, so the holes are now
drawn 0.04mm over the bar and the printer takes that back. If the bar still will
not go in, drop `press` in `cannon/trunnion.py` further -- do not put a file
through a bracket. If it goes in loose enough to walk back out, put `press` to
0.0. The bar itself prints lying on a face; print a spare. Once it
is in, the gun does not come off, or tip, until somebody pushes the bar back out
with a needle.

The mast is exported **lying down** rather than standing. Upright it would be a
200mm tower on a 5mm footprint, which is why the shaft is hexagonal and the
yards are square: everything rests on a flat rather than rolling on a curve. Do
not let the slicer stand it up.

The yards used to be round and thinner than the mast, which looked better and
did not print -- each one hung 1.25mm clear of the bed along its whole length
with nothing underneath. Square and mast-width, they lie on it. The only thing left
off the bed is the short necked section at each tip where a sail clips on, and
that is a 4.6mm bridge with a square shoulder holding each end. It used to be
2.5mm, and grew with the eyes that clip onto it; `clip_inset` moved inboard to
keep the outboard shoulder, which on the topsail's head yard is the tight one.

The sails and the awning's canvas are 0.6mm thick -- three layers at 0.2mm --
with a 1.2mm bolt rope round the edges and 1.6mm patches at the corners.
They want the _opposite_ of the hull's profile: no extra walls, no solid infill,
and no brim that would weld the corner loops to the bed. They should stay
slightly flexible, since clipping one on means springing each eye over its
neck.

**The corner eyes are the part that broke.** They are 4mm wide now rather than
1.9, and their mouths open to 2.457mm against a 2.507mm neck, so each lip
springs 0.025mm going on rather than the 0.126 it used to. That is the whole
change that matters: a lip bends across the printed layers, where PLA gives up
around one to two percent of strain, and 0.126mm on a two-millimetre arm came
to some five percent. The width is for the layer bonded at the root and for
being pulled off askew, not for the strain, which does not depend on it.

Because the snap is now only those last few hundredths, **hole and outer-wall
compensation matter**: if a printed eye comes out so tight it has to be forced,
or so loose it drops off the yard, that is the slot's width, and `mouth` in
`rig.py` is the number to move.

If you have PETG, print the sails and canvas in it. They get pulled off and
clipped back on far more than anything else on the boat, and PETG takes
repeated bending much better than PLA, which whitens at the fold and then
snaps.

The awning frame is exported **roof down**, which is the whole reason its roof
is a flat plane rather than following the sheer. That way the roof is the first
layer -- one connected grid, well stuck to the bed -- and the ten legs rise
off it as plain columns with nothing to bridge. Flipped the other way up, the
legs print first as thin towers and the entire roof has to span between them.

The legs are the thing to watch: 3.4mm square and up to 30mm tall, ten of them
standing free. Slow the outer walls down, and if the tops ring or lean, print
them with a bit more cooling rather than adding supports.

Each one now carries **knees** where it meets the bars -- a 6mm triangle into
the crossbar and into each rail -- because a dropped boat snapped a leg off at
that corner. They cost 1.4 cm³ and print as part of the leg: laid roof-down
every layer of a knee is smaller than the one beneath it, so the 45 degree
hypotenuse carries itself. The knees on the two necked crossbars are cut short,
since the canvas's eye comes down into that square.

The bar across the forward well **bridges about 34.4mm on each side of the
tube**. That is long, but the tube standing on the bottom halves what would
otherwise be a single 78mm span. If the underside sags badly enough to bother
you, it is inside the hull and out of sight; the fix would be a small gusset
where the bar meets the tube.

## Slicer settings that actually matter

These are about watertightness, not flotation.

- **Wall loops: 3, not 2.** The single most important setting. The hull is 2mm
  thick; at 0.45mm line width two loops per side cover 1.8mm and leave a 0.2mm
  strip of _sparse infill_ running through the middle of the shell. Three loops
  cover 2.7mm, so the whole wall is perimeter extrusions with no infill path
  through it.
- **Bottom layers: 5–6.** The flat bottom is the largest below-waterline
  surface and the likeliest place for a gap.
- **Layer height 0.16–0.2mm.** More layers, but each bond is better.
- **Nozzle temperature near the top of the filament's range**, and external
  perimeters slowed to ~25–30mm/s. Watertightness on FDM is layer adhesion.
- **Z-seam: Aligned, painted onto the stem.** Random scatters small defects
  over the whole hull; aligned puts them in one vertical line you can control
  and touch up.

The stem's foot stands on the bed and its front leaves it at about 50 degrees,
so the bow needs no supports.

Do not use vase mode — it would discard the decks, the bulwarks and the wall.

## Ballast and the waterline

The opposite problem to sinking: at 15% infill she draws 2.1mm on a 31.2mm
hull and rides like a leaf.

| Target draft | Total mass needed |
| -----------: | ----------------: |
|         8 mm |           130.3 g |
|        11 mm |           183.6 g |

If the real boat drew about two feet, that is roughly 11mm at 1:55 — worth
checking against a source, but the order of magnitude is right.

The tidy way to get there is a **modifier mesh over the lower hull** with high
infill, leaving the topsides light. That buys the mass _and_ puts it low, so
she is stable rather than tender. Lead shot set in epoxy in the open wells does
the same job and is easier to tune by feel.

## One thing about the layout

The open wells hollow to the bottom, so their floors sit 2mm above the hull's
bottom — **at or below the external waterline** at any usual infill. That is normal for a boat,
but it means a hull leak floods the boat directly rather than merely wetting
the infill. Worth a sink test before painting.

Their floors are planked like the decks, which takes 0.029 cm³ in all. The
grooves are 0.2mm deep and cut on the _inside_ only, leaving 1.8mm of floor and
not touching the skin the water sees; with 5–6 bottom layers and three wall
loops there is still no infill path through it. The seams start 6mm out from the
centreline, clear of the keelson and of the mast's tube.

## Recomputing these numbers

They come from the model, so they move when the spec does. The envelope is
`build(replace(spec, wall=0.0))` — the outer loft with no cavity — and
displacement at a draft is the volume of its intersection with a box that deep
from the bottom up; bisect on the draft until that matches the mass. Mass is
the part volume times infill fraction times 1.24 g/cm³.
