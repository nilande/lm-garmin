// SPIKE – not production code.
// Decode a single mkgmap tile .img back to GeoJSON features (one per line),
// using mkgmap's own reader classes.
// Usage: java -cp mkgmap.jar ImgDump.java tile.img [level]
import java.util.List;

import uk.me.parabola.imgfmt.app.Coord;
import uk.me.parabola.imgfmt.app.Label;
import uk.me.parabola.imgfmt.app.map.MapReader;
import uk.me.parabola.imgfmt.app.trergn.Point;
import uk.me.parabola.imgfmt.app.trergn.Polygon;
import uk.me.parabola.imgfmt.app.trergn.Polyline;
import uk.me.parabola.imgfmt.app.trergn.Zoom;

public class ImgDump {
    static String esc(String s) {
        return s == null ? "" : s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    static java.util.Map<Integer, String> LABELS = java.util.Map.of();

    static String label(Label l) {
        if (l == null) return "";
        String t = l.getText();
        if ((t == null || t.isEmpty()) && l.getOffset() > 0) t = LABELS.get(l.getOffset());
        return esc(t);
    }

    static Label pointLabel(Point p) {
        Label l = p.getLabel();
        if ((l == null || l.getText() == null || l.getText().isEmpty()) && p.getPOIRecord() != null)
            l = p.getPOIRecord().getNameLabel();
        return l;
    }

    static String coords(List<Coord> pts) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < pts.size(); i++) {
            Coord c = pts.get(i);
            if (i > 0) sb.append(',');
            sb.append(String.format("[%.6f,%.6f]", c.getLonDegrees(), c.getLatDegrees()));
        }
        return sb.append(']').toString();
    }

    static void emit(String kind, int type, String lbl, int level, String geom) {
        System.out.printf("{\"type\":\"Feature\",\"properties\":{\"kind\":\"%s\",\"type\":\"0x%x\",\"label\":\"%s\",\"level\":%d},\"geometry\":%s}%n",
                kind, type, lbl, level, geom);
    }

    public static void main(String[] args) throws Exception {
        try (MapReader mr = new MapReader(args[0])) {
            LABELS = mr.getLabels();
            Zoom[] levels = mr.getLevels();
            int only = args.length > 1 ? Integer.parseInt(args[1]) : -1;
            for (Zoom z : levels) {
                if (z == null) continue;
                int lv = z.getLevel();
                if (only >= 0 && lv != only) continue;
                for (Point p : mr.pointsForLevel(lv, MapReader.WITH_EXT_TYPE_DATA)) {
                    Coord c = p.getLocation();
                    emit("point", p.getType(), label(pointLabel(p)), lv,
                            String.format("{\"type\":\"Point\",\"coordinates\":[%.6f,%.6f]}", c.getLonDegrees(), c.getLatDegrees()));
                }
                for (Polyline l : mr.linesForLevel(lv)) {
                    emit("line", l.getType(), label(l.getLabel()), lv,
                            "{\"type\":\"LineString\",\"coordinates\":" + coords(l.getPoints()) + "}");
                }
                for (Polygon s : mr.shapesForLevel(lv, MapReader.WITH_EXT_TYPE_DATA)) {
                    List<Coord> pts = s.getPoints();
                    if (!pts.isEmpty() && !pts.get(0).equals(pts.get(pts.size() - 1))) pts.add(pts.get(0));
                    emit("polygon", s.getType(), label(s.getLabel()), lv,
                            "{\"type\":\"Polygon\",\"coordinates\":[" + coords(pts) + "]}");
                }
            }
        }
    }
}
