# Interpreting the raster comparison

The renderer reads the compiled Garmin features at one level and uses the
style mapping that generated their TYP. It projects the geometries to
SWEREF 99 TM and draws them at the same grid as the reference. In the difference
image, red marks a difference in land class. Grey marks pixels outside the
reference or too far from the reference palette to classify.

IoU is the intersection of the predicted and reference class masks divided by
their union, among classifiable reference pixels. A null score means the class
was absent on both sides. The report includes the pixel counts so a score based
on a few pixels can be distinguished from a large feature. The palette is fixed
independently of the style, with a nearest-colour threshold of 18 RGB units.
Lines and points appear in the preview but the comparison scores land polygons.

Karta 1:50 000 is drawn from Topografi 10. The Garmin map uses Topografi 50
at its most detailed levels. Differences in selected features, boundaries and
shape detail can therefore be expected even with equivalent colours. The
reference also contains labels, strokes and anti-aliasing. Wetland scores are
especially sensitive to the position and spacing of hatch lines and to similar
colours in contours. Treat those scores as ink overlap rather than agreement
on wetland area. Use the preview and the Garmin for separate visual checks.

CI compares the mountain and urban fixture rasters and uploads JSON metrics
with the existing integration report. The PNGs and map files are local outputs.
