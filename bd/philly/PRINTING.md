# Printing the hull

Notes for getting a printable — and floatable — model out of `just build`.

## Will it float?

Yes, comfortably, and at any infill you would plausibly choose. PLA is denser
than water (1.24 g/cm³), so a solid lump of it sinks; this hull floats because
it encloses far more air than it contains plastic.

At 300mm LOA with the current spec, the modelled solid is **176.3 cm³** inside
an external envelope of **408.4 cm³**. Everything follows from that ratio.

Draft is measured up from the bottom of the print, and freeboard up from the
waterline to the lowest point of the rail, amidships, which stands 21.7mm
above the bottom.

| Infill | Mass | Draft | Freeboard |
| -----: | ---: | ----: | --------: |
| 10% | 21.9 g | 1.4 mm | 20.3 mm |
| 15% | 32.8 g | 2.1 mm | 19.6 mm |
| 25% | 54.6 g | 3.5 mm | 18.2 mm |
| 40% | 87.4 g | 5.5 mm | 16.2 mm |
| 100% (solid) | 218.6 g | 12.9 mm | 8.8 mm |

Two worth noting:

- **Even solid PLA floats**, with 8.8mm of freeboard at the lowest point of
  the rail.
- **Even a waterlogged print floats.** If every infill void fills with water
  (182.6 g at 15% infill) it settles to 10.9mm and stays there.

The fittings barely register: mast, sails, awning and its canvas together are
29.7 cm³, so at 15% infill they add 5.5 g and about a third of a millimetre of
draft.

So buoyancy is not the thing to design for. Water *getting inside the hull* is.

## The parts

`just build` writes one file per part, because each wants a different
orientation and a different profile. The rig and the hull:

| File | Size | Orientation | Notes |
| --- | --- | --- | --- |
| `philadelphia-hull.3mf` | 300 x 84.5 x 31.2mm | as exported, bottom down | the watertightness settings below |
| `philadelphia-mast.3mf` | 200.8 x 93.0 x 5.0mm | as exported, lying flat | needs a 200mm bed axis |
| `philadelphia-sails.3mf` | 69 x 178 x 6.6mm | as exported, flat | two separate sails in one file |
| `philadelphia-awning.3mf` | 123.4 x 72.1 x 32.2mm | as exported, **roof down** | legs point up; do not flip it |
| `philadelphia-awning-canvas.3mf` | 124.7 x 61.3 x 4.7mm | as exported, flat | print it with the sails' settings |

It also writes the four gun parts -- `gun`, `carriage`, `trunnion` and
`cap-square` -- each in its own print orientation; the README's section on the
guns covers how they print.

The mast is exported **lying down** rather than standing. Upright it would be a
200mm tower on a 5mm footprint, which is why the shaft is hexagonal and the
yards are square: everything rests on a flat rather than rolling on a curve. Do
not let the slicer stand it up.

The yards used to be round and thinner than the mast, which looked better and
did not print -- each one hung 1.25mm clear of the bed along its whole length
with nothing underneath. Square and mast-width, they lie on it. The only thing left
off the bed is the short necked section at each tip where a sail clips on, and
that is a 2.5mm bridge with a square shoulder holding each end.

The sails and the awning's canvas are 0.6mm thick -- three layers at 0.2mm.
They want the *opposite* of the hull's profile: no extra walls, no solid infill,
and no brim that would weld the corner loops to the bed. They should stay
slightly flexible, since clipping one on means springing each eye over its
neck.

The awning frame is exported **roof down**, which is the whole reason its roof
is a flat plane rather than following the sheer. That way the roof is the first
layer -- one connected grid, well stuck to the bed -- and the eight legs rise
off it as plain columns with nothing to bridge. Flipped the other way up, the
legs print first as thin towers and the entire roof has to span between them.

The legs are the thing to watch: 3.4mm square and up to 28mm tall, eight of them
standing free. Slow the outer walls down, and if the tops ring or lean, print
them with a bit more cooling rather than adding supports.

The bar across the forward well **bridges about 34.4mm on each side of the
tube**. That is long, but the tube standing on the bottom halves what would
otherwise be a single 78mm span. If the underside sags badly enough to bother
you, it is inside the hull and out of sight; the fix would be a small gusset
where the bar meets the tube.

## Slicer settings that actually matter

These are about watertightness, not flotation.

- **Wall loops: 3, not 2.** The single most important setting. The hull is 2mm
  thick; at 0.45mm line width two loops per side cover 1.8mm and leave a 0.2mm
  strip of *sparse infill* running through the middle of the shell. Three loops
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

Do not use vase mode — it would discard the decks, the bulwarks and the wall.

## Ballast and the waterline

The opposite problem to sinking: at 15% infill she draws 2.1mm on a 31.2mm
hull and rides like a leaf.

| Target draft | Total mass needed |
| -----------: | ----------------: |
| 8 mm | 130.3 g |
| 11 mm | 183.6 g |

If the real boat drew about two feet, that is roughly 11mm at 1:55 — worth
checking against a source, but the order of magnitude is right.

The tidy way to get there is a **modifier mesh over the lower hull** with high
infill, leaving the topsides light. That buys the mass *and* puts it low, so
she is stable rather than tender. Lead shot set in epoxy in the open wells does
the same job and is easier to tune by feel.

## One thing about the layout

The open wells hollow to the bottom, so their floors sit 2mm above the hull's
bottom — **at or below the external waterline** at any usual infill. That is normal for a boat,
but it means a hull leak floods the boat directly rather than merely wetting
the infill. Worth a sink test before painting.

## Recomputing these numbers

They come from the model, so they move when the spec does. The envelope is
`build(replace(spec, wall=0.0))` — the outer loft with no cavity — and
displacement at a draft is the volume of its intersection with a box that deep
from the bottom up; bisect on the draft until that matches the mass. Mass is
the part volume times infill fraction times 1.24 g/cm³.
