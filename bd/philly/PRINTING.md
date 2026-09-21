# Printing the hull

Notes for getting a printable — and floatable — model out of `just build`.

## Will it float?

Yes, comfortably, and at any infill you would plausibly choose. PLA is denser
than water (1.24 g/cm³), so a solid lump of it sinks; this hull floats because
it encloses far more air than it contains plastic.

At 300mm LOA with the current spec, the modelled solid is **196.6 cm³** inside
an external envelope of **408.3 cm³**. Everything follows from that ratio.

| Infill | Mass | Draft | Freeboard |
| -----: | ---: | ----: | --------: |
| 10% | 24.4 g | 3.1 mm | 28.1 mm |
| 15% | 36.6 g | 3.9 mm | 27.3 mm |
| 25% | 61.0 g | 5.4 mm | 25.8 mm |
| 40% | 97.5 g | 7.6 mm | 23.6 mm |
| 100% (solid) | 243.8 g | 15.8 mm | 15.4 mm |

Two worth noting:

- **Even solid PLA floats**, with half the hull's depth still above water.
- **Even a waterlogged print floats.** If every infill void fills with water
  (203.7 g at 15% infill) it settles to 13.6mm and stays there.

So buoyancy is not the thing to design for. Water *getting inside the hull* is.

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
