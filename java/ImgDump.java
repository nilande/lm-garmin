// Decode Garmin .img maps built by mkgmap back to GeoJSON features, one per line, using
// mkgmap's own reader classes (ADR-0006). Runs as a single-file program on the mkgmap jar:
//
//   java -cp mkgmap.jar ImgDump.java map.img [more.img ...]
//
// Works on single tiles and on gmapsupp-style files with several tiles. mkgmap's MapReader
// only reads the first tile of a file, so Tile below does the same for a named tile.
// Output properties: tile, kind (point|line|polygon), type (hex), label, level, and
// road=true for lines in NET.
import java.io.Closeable;
import java.io.FileNotFoundException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Map;

import uk.me.parabola.imgfmt.app.Coord;
import uk.me.parabola.imgfmt.app.Label;
import uk.me.parabola.imgfmt.app.lbl.LBLFileReader;
import uk.me.parabola.imgfmt.app.net.NETFileReader;
import uk.me.parabola.imgfmt.app.trergn.Point;
import uk.me.parabola.imgfmt.app.trergn.Polygon;
import uk.me.parabola.imgfmt.app.trergn.Polyline;
import uk.me.parabola.imgfmt.app.trergn.RGNFileReader;
import uk.me.parabola.imgfmt.app.trergn.Subdivision;
import uk.me.parabola.imgfmt.app.trergn.TREFileReader;
import uk.me.parabola.imgfmt.app.trergn.Zoom;
import uk.me.parabola.imgfmt.fs.DirectoryEntry;
import uk.me.parabola.imgfmt.fs.FileSystem;
import uk.me.parabola.imgfmt.sys.ImgFS;

public class ImgDump {
    private static final StringBuilder OUT = new StringBuilder(1 << 16);
    private static Map<Integer, String> labels = Map.of();

    private static String esc(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder(s.length());
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.toString();
    }

    private static String text(Label l) {
        if (l == null) return "";
        String t = l.getText();
        if ((t == null || t.isEmpty()) && l.getOffset() > 0) t = labels.get(l.getOffset());
        return esc(t);
    }

    private static Label pointLabel(Point p) {
        Label l = p.getLabel();
        if ((l == null || l.getText() == null || l.getText().isEmpty()) && p.getPOIRecord() != null)
            l = p.getPOIRecord().getNameLabel();
        return l;
    }

    private static void coords(List<Coord> pts) {
        OUT.append('[');
        for (int i = 0; i < pts.size(); i++) {
            Coord c = pts.get(i);
            if (i > 0) OUT.append(',');
            OUT.append(String.format("[%.6f,%.6f]", c.getLonDegrees(), c.getLatDegrees()));
        }
        OUT.append(']');
    }

    private static void head(String tile, String kind, int type, String label, int level) {
        head(tile, kind, type, label, level, false);
    }

    private static void head(String tile, String kind, int type, String label, int level,
                             boolean road) {
        OUT.append("{\"type\":\"Feature\",\"properties\":{\"tile\":\"").append(tile)
           .append("\",\"kind\":\"").append(kind)
           .append("\",\"type\":\"0x").append(Integer.toHexString(type))
           .append("\",\"label\":\"").append(label)
           .append("\",\"level\":").append(level);
        if (road) OUT.append(",\"road\":true");  // in NET: searchable / routable (#72, #28)
        OUT.append("},\"geometry\":");
    }

    private static void flush() {
        System.out.print(OUT);
        OUT.setLength(0);
    }

    /** The subfiles of one tile (NAME.TRE/RGN/LBL[/NET]), wired like mkgmap's MapReader. */
    private static final class Tile implements Closeable {
        private final Deque<Closeable> toClose = new ArrayDeque<>();
        final TREFileReader tre;
        final RGNFileReader rgn;
        final LBLFileReader lbl;
        /** Raw NET subfile: road labels by road record (NET1), see roadLabel. */
        byte[] net;

        Tile(FileSystem fs, String name) throws Exception {
            tre = keep(new TREFileReader(keep(fs.open(name + ".TRE", "r"))));
            rgn = keep(new RGNFileReader(keep(fs.open(name + ".RGN", "r"))));
            lbl = keep(new LBLFileReader(keep(fs.open(name + ".LBL", "r"))));
            try {
                NETFileReader net = keep(new NETFileReader(keep(fs.open(name + ".NET", "r"))));
                net.setLabels(lbl);
                net.setCities(lbl.getCities());
                net.setZips(lbl.getZips());
                rgn.setNetFile(net);
                this.net = readAll(fs, name + ".NET");
            } catch (FileNotFoundException e) {
                // no NET: map built without routing/address data
            }
            rgn.setLblFile(lbl);
        }

        private static byte[] readAll(FileSystem fs, String file) throws Exception {
            try (var ch = fs.open(file, "r")) {
                var out = new java.io.ByteArrayOutputStream();
                var buf = java.nio.ByteBuffer.allocate(1 << 16);
                int n;
                while ((n = ch.read(buf)) > 0) {
                    out.write(buf.array(), 0, n);
                    buf.clear();
                }
                return out.toByteArray();
            }
        }

        /**
         * The first label of a road's NET1 record. mkgmap's reader maps only the roads listed
         * in the sorted-roads index (one per name), so the other roads of a merged street came
         * out unlabelled (#28).
         */
        Label roadLabel(int net1Offset) {
            if (net == null) return null;
            int start = (net[0x15] & 0xff) | (net[0x16] & 0xff) << 8 | (net[0x17] & 0xff) << 16
                    | (net[0x18] & 0xff) << 24;
            int pos = start + net1Offset;
            if (pos < 0 || pos + 3 > net.length) return null;
            int v = (net[pos] & 0xff) | (net[pos + 1] & 0xff) << 8 | (net[pos + 2] & 0xff) << 16;
            return lbl.fetchLabel(v & 0x7fffff);
        }

        private <T extends Closeable> T keep(T c) {
            toClose.push(c);
            return c;
        }

        @Override
        public void close() {
            while (!toClose.isEmpty()) {
                try {
                    toClose.pop().close();
                } catch (Exception ignored) {
                    // best effort
                }
            }
        }
    }

    private static void dumpTile(FileSystem fs, String tile) throws Exception {
        try (Tile t = new Tile(fs, tile)) {
            labels = t.lbl.getLabels();
            for (Zoom z : t.tre.getMapLevels()) {
                if (z == null) continue;
                int lv = z.getLevel();
                for (Subdivision sd : t.tre.subdivForLevel(lv)) {
                    for (Point p : t.rgn.pointsForSubdiv(sd, true)) {
                        Coord c = p.getLocation();
                        head(tile, "point", p.getType(), text(pointLabel(p)), lv);
                        OUT.append(String.format("{\"type\":\"Point\",\"coordinates\":[%.6f,%.6f]}}%n",
                                c.getLonDegrees(), c.getLatDegrees()));
                    }
                    for (Polyline l : t.rgn.linesForSubdiv(sd)) {
                        Label label = l.getLabel();
                        if (l.isRoad() && text(label).isEmpty()) label = t.roadLabel(l.getOffsetNet1());
                        head(tile, "line", l.getType(), text(label), lv, l.isRoad());
                        OUT.append("{\"type\":\"LineString\",\"coordinates\":");
                        coords(l.getPoints());
                        OUT.append("}}\n");
                    }
                    for (Polygon s : t.rgn.shapesForSubdiv(sd, true)) {
                        List<Coord> pts = new ArrayList<>(s.getPoints());
                        if (!pts.isEmpty() && !pts.get(0).equals(pts.get(pts.size() - 1))) pts.add(pts.get(0));
                        head(tile, "polygon", s.getType(), text(s.getLabel()), lv);
                        OUT.append("{\"type\":\"Polygon\",\"coordinates\":[");
                        coords(pts);
                        OUT.append("]}}\n");
                    }
                    if (OUT.length() > (1 << 20)) flush();
                }
                flush();
            }
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            System.err.println("usage: java -cp mkgmap.jar ImgDump.java map.img [more.img ...]");
            System.exit(2);
        }
        for (String path : args) {
            FileSystem fs = ImgFS.openFs(path);
            try {
                List<String> tiles = new ArrayList<>();
                for (DirectoryEntry e : fs.list())
                    if ("TRE".equals(e.getExt())) tiles.add(e.getName());
                for (String name : tiles) dumpTile(fs, name);
            } finally {
                fs.close();
            }
        }
        flush();
    }
}
