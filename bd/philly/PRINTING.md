# Printing the hull

Notes for getting a printable — and floatable — model out of `just build`.

## Will it float?

Yes, comfortably, and at any infill you would plausibly choose. PLA is denser
than water (1.24 g/cm³), so a solid lump of it sinks; this hull floats because
it encloses far more air than it contains plastic.

At 300mm LOA with the current spec, the modelled solid is **164.2 cm³** inside
an external envelope of **408.3 cm³**. Everything follows from that ratio.

| Infill | Mass | Draft | Freeboard |
| -----: | ---: | ----: | --------: |
| 10% | 20.4 g | 2.9 mm | 29.9 mm |
| 15% | 30.5 g | 3.5 mm | 29.2 mm |
| 25% | 50.9 g | 4.8 mm | 28.0 mm |
| 40% | 81.5 g | 6.7 mm | 26.1 mm |
| 100% (solid) | 203.6 g | 13.6 mm | 19.1 mm |

Two worth noting:

- **Even solid PLA floats**, with well over half the hull's depth above water.
- **Even a waterlogged print floats.** If every infill void fills with water
  (170.1 g at 15% infill) it settles to 11.8mm and stays there.

The rig barely registers: mast and sails together are 14.3 cm³, so at 15%
infill they add 2.7 g and about two tenths of a millimetre of draft.

So buoyancy is not the thing to design for. Water *getting inside the hull* is.

## The three parts

`just build` writes one file per part, because each wants a different
orientation and a different profile:

| File | Size | Orientation | Notes |
| --- | --- | --- | --- |
| `philadelphia-hull.3mf` | 300 x 84.5 x 31.2mm | as exported, bottom down | the watertightness settings below |
| `philadelphia-mast.3mf` | 200.8 x 72.3 x 5.0mm | as exported, lying flat | needs a 200mm bed axis |
| `philadelphia-sails.3mf` | 69 x 121 x 6.6mm | as exported, flat | two separate sails in one file |

The mast is exported **lying down** rather than standing. Upright it would be a
200mm tower on a 5mm footprint, which is why the shaft is hexagonal and the
yards are square: everything rests on a flat rather than rolling on a curve. Do
not let the slicer stand it up.

The yards used to be round and thinner than the mast, which looked better and
did not print -- each one hung 1.25mm clear of the bed along its whole 72mm with
nothing underneath. Square and mast-width, they lie on it. The only thing left
off the bed is the short necked section at each tip where a sail clips on, and
that is a 2.5mm bridge with a square shoulder holding each end.

The sails are 0.6mm thick -- three layers at 0.2mm. They want the *opposite* of
the hull's profile: no extra walls, no solid infill, and no brim that would weld
the corner loops to the bed. They should stay slightly flexible, since clipping
one onto a yard means springing it over the mouth.

The bar across the forward well **bridges about 31.6mm on each side of the
tube**. That is long, but the tube standing on the bottom halves what would
otherwise be a single 73mm span. If the underside sags badly enough to bother
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

The opposite problem to sinking: at 15% infill she draws 3.9mm on a 31.2mm
hull and rides like a leaf.

| Target draft | Total mass needed |
| -----------: | ----------------: |
| 8 mm | 103.9 g |
| 11 mm | 156.2 g |

If the real boat drew about two feet, that is roughly 11mm at 1:55 — worth
checking against a source, but the order of magnitude is right.

The tidy way to get there is a **modifier mesh over the lower hull** with high
infill, leaving the topsides light. That buys the mass *and* puts it low, so
she is stable rather than tender. Lead shot set in epoxy in the open wells does
the same job and is easier to tune by feel.

## One thing about the layout

The open spans hollow to the bottom, so their floors sit about 2mm above the
hull's bottom — **below the external waterline**. That is normal for a boat,
but it means a hull leak floods the boat directly rather than merely wetting
the infill. Worth a sink test before painting.

## Recomputing these numbers

They come from the model, so they move when the spec does. Displacement is the
integral of submerged section area along the length, using the same
`sheer_half_width` / `chine_half_width` / heights that [`hull.py`](hull.py)
lofts, plus the swell from [`Bulge`](hull.py#L55); mass is the part volume
times infill fraction times 1.24 g/cm³. The envelope figure is
`build(replace(spec, wall=0.0)).volume` — the outer loft with no cavity.
