include <BOSL2/std.scad>;
include <frames.scad>
use <../vendor/plot-function/plot_function.scad>
use <../vendor/ogive_and_ogee.scad>

// Smooth a half-frame's control points into a curve, mirrored into a full cross-section.
// half_pts: [[x,y],...] keel→deck, x may be negative (aft frames); abs is taken.
function _abs_x(pts) = [for (p = pts) [abs(p[0]), p[1]]];

function full_frame(half_pts, relsize = 0.2) =
  let (
    s = smooth_path(_abs_x(half_pts), relsize=relsize, closed=false),
    port = [for (p = reverse(s)) [-p[0], p[1]]]
  ) concat(s, port);

//$fs = .1;
//union() {
//  translate([0, 30, 2.5]) sphere(1); //bow
//  translate([0, 10, -1]) cube([20, 1, 8], true); //1st bulkhead
//  translate([0, 10, -5]) cube([1, 1, 8], true); //1st keel
//  translate([0, -8, -1]) cube([20, 1, 8], true); //2nd bulkhead
//  translate([0, -8, -5]) cube([1, 1, 8], true); //2nd keel
//  translate([0, -30, 1]) cube([16, 1, 4], true); //stern
//}
//cylinder(40, 1, 1); //Mast

keel_l = 80;
keel_h = 16;
breadth = 27;

e = 2.71828;

module ship_hull() {
  // Aft frames run midship→stern in the body plan; reverse so skin goes stern→bow.
  all_halves = concat(aft_frames, fore_frames);
  frames = [for (h = all_halves) full_frame(h)];

  skin(
    frames,
    slices=10,
    z=[for (i = [0:len(frames) - 1]) i * 20],
    method="reindex"
  );
}

ship_hull();

//rotate([0, 0, -90])
//  ogive(width=breadth, height=keel_h, steps=16);
//
//translate([0, 0, 10])
//  rotate([0, 0, 180])
//    ogee(width=keel_h/5*4, height=breadth, steps=16);
//
//translate([0, 0, 20])
//  rotate([0, 0, 180])
//    ogee(width=keel_h/5*3, height=breadth, steps=16);
