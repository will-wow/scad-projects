# Fitting the guns to the hull

The plan for the next piece of work. The guns themselves are built -- barrel,
carriage, trunnion pegs and cap squares, in `cannon/` (see
[`guns-handoff.md`](guns-handoff.md)) -- but nothing yet puts them in the boat.
This covers where each one goes, how high it has to sit, and how it clips into
the hull.

Stations are fractions of the length from the bow, as `main.py` places things.
Heights are above the keel unless they say otherwise. Full-size millimetres
come first, then printed millimetres at 300mm (1mm printed is 54.6mm full
size).

## What the scan says

All of this is printed by [`measure_scan.py`](measure_scan.py) (see the end of
this doc).

**The 12-pounder** sits on the centreline, firing over the stem between the
knightheads.

| | full size | printed |
|---|---|---|
| muzzle past the stem | 38 | 0.7 |
| elevation | 4.1 deg | |
| trunnions aft of the stem | 1355 (0.083) | 24.8 |
| forecastle deck under the trunnions | 862 | 15.8 |
| axis above that deck, at the trunnions | 767 | **14.1** |
| axis at the stem | 1727, level with the knightheads' tops | |

The deck sections under the gun show a second level about 100 above the
forecastle (1.8mm printed). The carriage stands on that seat, not on the deck
itself.

**The 9-pounders** are staggered, one each side: port at 0.483, starboard at
0.606. They fire outboard over the rail, which has no ports.

| starboard gun at 0.606 | full size | printed |
|---|---|---|
| elevation | 4.0 deg | |
| middle platform under it | 612 | 11.2 |
| axis above the platform, where it crosses the rail | 853 | **15.6** |
| barrel's underside over the rail | 87 | 1.6 |
| muzzle swell radius | 128 | 2.3 |

The swell of 128 is 2.4 calibres of a 107mm bore -- a 9-pounder. The port gun
is scanned run in, with too little clean barrel to fit, so it is taken to match
the starboard one.

**The decks** are already in `main.HULL` from the same measurements:

| | stretch | height |
|---|---|---|
| forecastle | 0 -- 0.31 | 0.48 of the depth |
| middle platform | 0.39 -- 0.655 | 0.34 |
| quarterdeck | 0.71 -- 1.0 | 0.30 |

## Clearance against the model

This is the model's own rail, from the lines plan, above the model's own decks.
The barrel's underside has to clear the rail where it crosses it.

| gun | rail above its deck | axis needed | scan's axis | margin |
|---|---|---|---|---|
| 9-pdr, port (0.483), level | 12.44 | 14.79 | 15.6 | 0.8 |
| 9-pdr, starboard (0.606), level | 12.54 | 14.89 | 15.6 | 0.7 |
| 12-pdr (at trunnions), level | | 14.46 | 14.1 | -0.4 |
| 12-pdr (at trunnions), 4.1 deg | | 12.68 | 14.1 | 1.4 |

The bow gun's rail is the sheer at the stem, 27.6mm, against a forecastle at
15.7mm.

**So no gunports are needed.** At the scan's real heights the broadside guns
clear their rails level. The bow gun clears at its real elevation, which it
has to be built with anyway. The real boat had no ports, and this is why.

**The carriage is what has to change.** As built, it puts the trunnion axis
6.2mm above whatever it stands on. The targets are:

- **14.1mm** for the bow gun, measured from the forecastle. The 1.8mm seat is
  part of that, so the carriage itself gives 12.3.
- **About 15mm** at the trunnions for the 9-pounders. The scan gives 15.6
  where the barrel crosses the rail. The trunnions are inboard of that point
  and so lower by the elevation, and the solver below settles the exact
  number.

## Decisions already made

- **A drawer channel with a detent.** Each carriage slides in a channel cut
  into its deck. It clips in, runs out to the rail, and slides back without
  sliding off.
- **The channels are printed into the hull.** They are cut after `build`, as
  the mast step and the awning sockets are. They are not separate parts glued
  in.
- **The 9-pounders are staggered**, one per side, at the scan's stations.
- **No gunports.** See above.

## The interface

**Carriage side: a foot under the bed.**

- The foot is a strip along the carriage's length, wider at the bottom than
  at the top, with 45 degree flanks. That is `max_overhang`, the same angle
  as the rail hooks the cap squares ride.
- It prints bed-down, and it narrows as it rises, so nothing overhangs.
- It is added to `carriage()` below the bed, which raises the gun by the
  foot's height. That is part of the height target, not extra to it.

**Hull side: the channel.**

- The channel is the foot's profile, offset by the fit and extruded along the
  slide. `cap_square.py` cuts its groove from the rail's profile the same way:
  one `offset(amount=fit, kind=Kind.INTERSECTION)` on the swept profile, never
  a groove patched together from rectangles.
- Its roof is the 45 degree flank, so the hull still prints bottom-down with
  no support.
- The slide runs fore and aft for the bow gun and athwartships for the
  9-pounders.
- The channel is closed at the rail end. That end is where the carriage stops
  when it is run out.
- It is open at the inboard end, which is where the carriage goes in.

**The detent: an asymmetric ridge across the channel floor, near the open
end.**

- It has a gentle ramp on the entry side, so the carriage pushes in over it.
- It has a steep face on the other side, so recoil (a finger pulling the gun
  back) stops against it rather than running the carriage out of the channel.
- Taking the carriage out means lifting its tail over the steep face on
  purpose.
- The channel carries `lift` of headroom over its whole length, as
  `CapSquareSpec` does, so the foot rides over the ridge.

**The fits come from the gun's own specs**, not new numbers:

- the running fit per side from `CapSquareSpec.fit` (0.15);
- the lift from `CapSquareSpec.lift` (0.5);
- the detent's height from `CarriageSpec.detent` (0.25), the bump the cap
  squares already click over.

**How deep the channel can go.** A deck is solid down to the hull's outside,
so the channel's floor must leave `awning.FLOOR` (2mm) above it, as the awning
sockets do.

- The middle platform stands 9.6mm above the outside, so a channel 2-3mm deep
  leaves plenty.
- The forecastle stands 14.2mm above the outside.

## Code for the next session

1. **`cannon/carriage.py`**:
   - Add an axis-height target to `CarriageSpec`, and derive the bed's
     thickness and the foot from it rather than stacking fixed numbers.
     `STEPS` are fixed millimetres today; keep their shape and lift them.
   - Add the foot.
   - End the bed short of the breech. Past about 2 degrees the breech fouls
     the bed, and at 8 it reaches the deck. The guns need 4, and the bow gun
     depends on it to clear the stem.
2. **`cannon/cannon.py`**: add `NINE_POUNDER`, a `replace()` of the 12-pounder
   spec with `calibre=107`.
   - Its length is unmeasured. Scale the 12-pounder's by calibre to start
     (about 2230).
   - Better still, extend `measure_scan.py` to trace the starboard barrel back
     to its breech.
3. **A new `guns.py`**, in the pattern of `rig.py` and `awning.py`:
   - A `Gun` placement: station, side, gun spec and carriage spec. It should
     know which deck it stands on from `main.HULL.decks`, rather than being
     told.
   - A run-out solver. From the hull lines at the gun's station, it finds
     where the carriage stops so the muzzle just clears the rail. It checks
     that the barrel's underside clears the rail at the gun's elevation, and
     refuses a placement that does not.
   - `fit_guns(hull, spec, lines, guns)`, which cuts the channels and ridges
     after `build`, like `fit_mast` and `fit_awning`. It checks the floor
     under each channel.
4. **Wiring:**
   - `main.model()` calls `fit_guns`.
   - `assembly.parts()` places each gun on its carriage, run out, at its
     elevation. `cannon/assembly.py` already has the gun on a `RevoluteJoint`
     on the carriage.
   - `export.PARTS` gains the 9-pounder barrel. The 12-pounder's `gun` part
     stays as it is.
5. **Move the awning leg at 0.58.**
   - Its boss spans 170.5-177.5mm. The starboard 9-pounder's carriage, 11.5mm
     wide along the length, spans about 176-188.
   - Try 0.55: boss 161.5-168.5, clear of both guns (the port one spans about
     139-151).
   - The crossbars are pitched from the span's start, not from the legs, so
     the topsail pairs do not move.

## Tests

- Each gun, placed in the assembly, fires over its rail: nothing of the hull
  is inside the barrel at its run-out position and elevation.
- The carriages meet the scan's axis heights (14.1 above the forecastle for
  the bow gun; the solved height for the 9-pounders), within a tenth of a
  millimetre.
- The foot slides in its channel: every side has the fit's clearance. The
  foot cannot lift out: a probe above the foot's widest point is hull.
- The detent is asymmetric: the entry ramp is gentler than `max_overhang`, and
  the stop face is steeper.
- Neither the foot nor the channel's roof overhangs past `max_overhang`, by
  `conftest.steepest_overhang` on the parts.
- The fitted hull is still one valid solid, no wider than the bare one, and
  every channel leaves `FLOOR` above the outside.
- The assembly clash check covers the guns: nothing shares volume with the
  mast, the awning or the sails.

## Measuring the scan again

The two GLBs are not in the repository (the Smithsonian's terms are not an
open licence). [`scan/README.md`](scan/README.md) says which files go where.
Then:

```sh
uv run --no-project --with dracopy --with numpy designs/measure_scan.py
```

It prints four things:

- which end is the bow;
- the deck surface along the centreline, grouped into platforms and wells;
- the 12-pounder's muzzle, elevation and axis height at its trunnions;
- each 9-pounder's elevation, axis height where it crosses the rail, and
  muzzle radius.

It fits circles through slices of each barrel and keeps only the slices that
fit cleanly, so a carriage or a rope in the slice does not skew the answer.
Every number in this document came from its output.
