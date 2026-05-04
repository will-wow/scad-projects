include <BOSL2/std.scad>;
include <frames.scad>

// Smooth a half-frame's control points into a curve, mirrored into a full cross-section.
// half_pts: [[x,y],...] keel→deck, x may be negative (aft frames); abs is taken.
function _abs_x(pts) = [for (p = pts) [abs(p[0]), p[1]]];

function full_frame(half_pts, relsize = 0.2) =
  let (
    s = smooth_path(_abs_x(half_pts), relsize=relsize, closed=false),
    port = [for (p = reverse(s)) [-p[0], p[1]]]
  ) concat(s, port);

// Place a 2D frame as flat 3D points at height z.
function frame_3d(pts, z) = [for (p = pts) [p[0], p[1], z]];

// Place a 2D frame raked at rake_deg around the X axis.
// The keel (y≈0) stays at z; the deck top shifts by -y*sin(rake_deg).
function raked_frame_3d(pts, z, rake_deg) =
  [for (p = pts) [p[0], p[1]*cos(rake_deg), z - p[1]*sin(rake_deg)]];


keel_l = 80;
keel_h = 16;
breadth = 27;

e = 2.71828;

RAKE      = 5;   // transom rake in degrees
BOW_STEPS = 5;   // synthetic frames tapering to stem post
BOW_LEN   = 60;  // mm from bow frame to stem post

module ship_hull() {
  all_halves = concat(aft_frames, fore_frames);
  n = len(all_halves);
  smooth = [for (h = all_halves) full_frame(h)];

  hull_frames = [
    for (i = [0:n-1])
    let (z = i * 20)
    i == 0
      ? raked_frame_3d(smooth[i], z, RAKE)
      : frame_3d(smooth[i], z)
  ];

  bow_half   = smooth_path(_abs_x(all_halves[n-1]), relsize=0.2, closed=false);
  bow_z0     = (n-1) * 20;
  bow_keel_x = bow_half[0][0];  // half-keel-width; stem post converges here

  bow_frames = [
    for (i = [1:BOW_STEPS])
    let (
      t    = i / BOW_STEPS,
      z    = bow_z0 + i * BOW_LEN / BOW_STEPS,
      half = [for (p = bow_half) [p[0] * (1-t) + bow_keel_x * t, p[1]]],
      port = [for (p = reverse(half)) [-p[0], p[1]]]
    )
    frame_3d(concat(half, port), z)
  ];

  skin(concat(hull_frames, bow_frames), slices=10, method="direct");
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
