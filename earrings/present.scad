include <Round-Anything/polyround.scad>

$fa = 1;
$fs = 0.4;

boxWidth = 15;
boxW = boxWidth / 2;
boxRadius = 0.4;
boxHeight = 4;

top = sqrt(boxW * boxW + boxW * boxW);

module box() {
  union() {
    boxPoints = [
      [-boxW, -boxW, boxRadius],
      [boxW, -boxW, boxRadius],
      [boxW, boxW, boxRadius],
      [-boxW, boxW, boxRadius],
    ];
    polyRoundExtrude(boxPoints, boxHeight, boxRadius, boxRadius, fn=10);

    wrappingWidth = 3;
    wrappingLength = boxWidth + 0.4;
    wrappingHeight = boxHeight + 0.4;

    verticalWrappingPoints = [
      [-wrappingWidth / 2, -wrappingLength / 2, boxRadius],
      [wrappingWidth / 2, -wrappingLength / 2, boxRadius],
      [wrappingWidth / 2, wrappingLength / 2, boxRadius],
      [-wrappingWidth / 2, wrappingLength / 2, boxRadius],
    ];
    polyRoundExtrude(verticalWrappingPoints, wrappingHeight, boxRadius, boxRadius, fn=10);

    hWrappingPoints = [
      [-wrappingLength / 2, -wrappingWidth / 2, boxRadius],
      [wrappingLength / 2, -wrappingWidth / 2, boxRadius],
      [wrappingLength / 2, wrappingWidth / 2, boxRadius],
      [-wrappingLength / 2, wrappingWidth / 2, boxRadius],
    ];
    polyRoundExtrude(hWrappingPoints, wrappingHeight, boxRadius, boxRadius, fn=10);

    ribbonW = 6;
    ribbonH = 3;
    ribbonInnerH = 0.8;
    ribbonInnerW = 1.4;
    ribbonKnotH = 1.6;

    ribbonPts = [
      // Left side
      [-ribbonInnerW, ribbonKnotH, boxRadius],
      [-ribbonInnerW, ribbonInnerH, boxRadius],
      [-ribbonW, ribbonH, boxRadius],
      [-ribbonW, -ribbonH, boxRadius],
      [-ribbonInnerW, -ribbonInnerH, boxRadius],
      [-ribbonInnerW, -ribbonKnotH, boxRadius],
      // Right side
      [ribbonInnerW, -ribbonKnotH, boxRadius],
      [ribbonInnerW, -ribbonInnerH, boxRadius],
      [ribbonW, -ribbonH, boxRadius],
      [ribbonW, ribbonH, boxRadius],
      [ribbonInnerW, ribbonInnerH, boxRadius],
      [ribbonInnerW, ribbonKnotH, boxRadius],
    ];

    rotate([0, 0, 45])
      polyRoundExtrude(ribbonPts, wrappingHeight + 0.4, boxRadius, boxRadius, fn=10);

    hangerW = 2;
    hangerH = 3;

    hangerPoints = [
      [-hangerW, -hangerH, 0],
      [-hangerW, hangerH, hangerW],
      [hangerW, hangerH, hangerW],
      [hangerW, -hangerH, 0],
    ];
    rotate([0, 0, 45])
      translate([0, top - 1, 0])
        polyRoundExtrude(hangerPoints, boxHeight, boxRadius, boxRadius, fn=50);
  }
}

holeWidth = 2;

difference() {
  box();

  rotate([0, 0, 45])
    translate([0, top, 0])
      translate([0, 0, -boxHeight / 2])
        cylinder(h=boxHeight * 2, d=1.5);
}
