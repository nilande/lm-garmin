// SPIKE (#72, #28) – inspect how a routable third-party Garmin map is built, to compare with ours.
//
//   java -cp mkgmap.jar NavInspect.java map.img            # subfiles, header facts, Täby tile
//   java -cp mkgmap.jar NavInspect.java map.img TILENAME   # address and road data of one tile
//
// Reads only; uses mkgmap's reader classes like java/ImgDump.java.
import java.util.Map;
import java.util.TreeMap;
import java.util.List;
import java.util.ArrayList;

import uk.me.parabola.imgfmt.app.Area;
import uk.me.parabola.imgfmt.app.Label;
import uk.me.parabola.imgfmt.app.lbl.City;
import uk.me.parabola.imgfmt.app.lbl.Country;
import uk.me.parabola.imgfmt.app.lbl.LBLFileReader;
import uk.me.parabola.imgfmt.app.lbl.Region;
import uk.me.parabola.imgfmt.app.lbl.Zip;
import uk.me.parabola.imgfmt.app.net.NETFileReader;
import uk.me.parabola.imgfmt.app.net.RoadDef;
import uk.me.parabola.imgfmt.app.trergn.TREFileReader;
import uk.me.parabola.imgfmt.app.trergn.Zoom;
import uk.me.parabola.imgfmt.fs.DirectoryEntry;
import uk.me.parabola.imgfmt.fs.FileSystem;
import uk.me.parabola.imgfmt.fs.ImgChannel;
import uk.me.parabola.imgfmt.sys.ImgFS;

public class NavInspect {
    static String lab(Label l) {
        return l == null ? "" : String.valueOf(l.getText());
    }

    public static void main(String[] args) throws Exception {
        FileSystem fs = ImgFS.openFs(args[0]);
        if (args.length == 1) overview(fs);
        else tile(fs, args[1]);
        fs.close();
    }

    static void overview(FileSystem fs) throws Exception {
        Map<String, long[]> byExt = new TreeMap<>();
        List<String> other = new ArrayList<>();
        List<String> tiles = new ArrayList<>();
        for (DirectoryEntry e : fs.list()) {
            long[] a = byExt.computeIfAbsent(e.getExt(), k -> new long[2]);
            a[0]++;
            a[1] += e.getSize();
            if (e.getExt().equals("TRE")) tiles.add(e.getName());
            if (!List.of("TRE", "RGN", "LBL", "NET", "NOD", "DEM").contains(e.getExt()))
                other.add(e.getFullName() + " " + e.getSize());
        }
        System.out.println("== subfiles by type (count, MB)");
        byExt.forEach((k, v) -> System.out.printf("%-4s %6d %9.1f%n", k, v[0], v[1] / 1e6));
        System.out.println("== other subfiles");
        other.forEach(System.out::println);
        // Täby centre
        double lat = 59.444, lon = 18.069;
        String first = tiles.get(0);
        try (ImgChannel c = fs.open(first + ".TRE", "r")) {
            TREFileReader tre = new TREFileReader(c);
            System.out.println("== first tile " + first);
            for (String s : tre.getMapInfo(65001)) System.out.println("info: " + s);
            for (Zoom z : tre.getMapLevels()) if (z != null) System.out.println("level " + z.getLevel() + " res " + z.getResolution());
        }
        for (String t : tiles) {
            try (ImgChannel c = fs.open(t + ".TRE", "r")) {
                Area a = new TREFileReader(c).getBounds();
                if (a.contains(new uk.me.parabola.imgfmt.app.Coord(lat, lon)))
                    System.out.println("Täby tile: " + t + " " + a);
            }
        }
    }

    static void tile(FileSystem fs, String t) throws Exception {
        try (ImgChannel lc = fs.open(t + ".LBL", "r")) {
            LBLFileReader lbl = new LBLFileReader(lc);
            System.out.println("codepage " + lbl.getCodePage() + " sort " + lbl.getSortOrderId() + " encoding " + lbl.getEncodingType());
            for (Country c : lbl.getCountries()) if (c != null) System.out.println("country " + c.getIndex() + " " + lab(c.getLabel()));
            for (Region r : lbl.getRegions()) if (r != null) System.out.println("region " + r.getIndex() + " " + lab(r.getLabel()) + " / " + lab(r.getCountry().getLabel()));
            List<City> cities = lbl.getCities();
            System.out.println("cities " + cities.size());
            for (City c : cities.subList(0, Math.min(25, cities.size()))) if (c != null)
                System.out.println("  city " + c.getIndex() + " " + c.getName() + " region#" + c.getRegionNumber() + " country#" + c.getCountryNumber() + " point " + c.getPointIndex());
            List<Zip> zips = lbl.getZips();
            System.out.print("zips " + zips.size() + ":");
            for (Zip z : zips.subList(0, Math.min(15, zips.size()))) if (z != null) System.out.print(" " + lab(z.getLabel()));
            System.out.println();
            try (ImgChannel nc = fs.open(t + ".NET", "r")) {
                NETFileReader net = new NETFileReader(nc);
                net.setLabels(lbl);
                net.setCities(cities);
                net.setZips(zips);
                List<RoadDef> roads = net.getRoads();
                int withCity = 0, withZip = 0, withNum = 0, multiLabel = 0;
                Map<Integer, Integer> cls = new TreeMap<>(), spd = new TreeMap<>();
                for (RoadDef r : roads) {
                    if (!r.getCities().isEmpty()) withCity++;
                    if (!r.getZips().isEmpty()) withZip++;
                    if (r.hasHouseNumbers()) withNum++;
                    if (r.getLabels() != null && r.getLabels().length > 1 && r.getLabels()[1] != null) multiLabel++;
                    cls.merge(r.getRoadClass(), 1, Integer::sum);
                    spd.merge(r.getRoadSpeed(), 1, Integer::sum);
                }
                System.out.printf("roads %d, with city %d, with zip %d, with house numbers %d, >1 label %d%n",
                        roads.size(), withCity, withZip, withNum, multiLabel);
                System.out.println("road class " + cls + "  speed " + spd);
                int shown = 0;
                for (RoadDef r : roads) {
                    if (r.getCities().isEmpty() || shown++ > 25) continue;
                    StringBuilder b = new StringBuilder("  road ");
                    for (Label l : r.getLabels()) if (l != null) b.append('[').append(lab(l)).append(']');
                    b.append(" class ").append(r.getRoadClass()).append(" speed ").append(r.getRoadSpeed());
                    for (City c : r.getCities()) b.append(" city=").append(c.getName());
                    for (Zip z : r.getZips()) b.append(" zip=").append(lab(z.getLabel()));
                    if (r.hasHouseNumbers()) b.append(" numbers");
                    System.out.println(b);
                }
            } catch (java.io.FileNotFoundException e) {
                System.out.println("no NET");
            }
        }
        for (String ext : List.of("TRE", "RGN", "LBL", "NET", "NOD", "DEM")) {
            for (DirectoryEntry e : fs.list())
                if (e.getName().equals(t) && e.getExt().equals(ext)) System.out.printf("%s %d bytes%n", ext, e.getSize());
        }
    }
}
