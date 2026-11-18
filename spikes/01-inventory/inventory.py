"""SPIKE – not production code.

Inventory every GeoPackage in a directory: tables, columns, row counts,
object-type distribution and value distributions for low-cardinality
text columns. Writes JSON to stdout.

Usage: python3 inventory.py <gpkg-dir> > inventory.json
"""
import json
import os
import sqlite3
import sys
import time

SKIP_COLS = {"objektidentitet", "skapad", "geom", "fid"}
MAX_DISTINCT = 40


def inspect(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cur = con.cursor()
    out = {}
    contents = cur.execute(
        "SELECT table_name, data_type, min_x, min_y, max_x, max_y, srs_id "
        "FROM gpkg_contents"
    ).fetchall()
    geomcols = dict(
        cur.execute(
            "SELECT table_name, geometry_type_name FROM gpkg_geometry_columns"
        ).fetchall()
    )
    for tname, dtype, x0, y0, x1, y1, srs in contents:
        t0 = time.time()
        cols = [r[1:3] for r in cur.execute(f'PRAGMA table_info("{tname}")')]
        n = cur.execute(f'SELECT count(*) FROM "{tname}"').fetchone()[0]
        info = {
            "data_type": dtype,
            "geometry": geomcols.get(tname),
            "srs": srs,
            "bbox": [x0, y0, x1, y1],
            "count": n,
            "columns": {c: t for c, t in cols},
            "values": {},
        }
        for c, t in cols:
            if c in SKIP_COLS:
                continue
            nd = cur.execute(
                f'SELECT count(*) FROM (SELECT DISTINCT "{c}" FROM "{tname}" LIMIT {MAX_DISTINCT + 1})'
            ).fetchone()[0]
            if nd <= MAX_DISTINCT:
                rows = cur.execute(
                    f'SELECT "{c}", count(*) FROM "{tname}" GROUP BY 1 ORDER BY 2 DESC'
                ).fetchall()
                info["values"][c] = rows
            else:
                nn = cur.execute(
                    f'SELECT count(*) FROM "{tname}" WHERE "{c}" IS NOT NULL AND "{c}" != \'\''
                ).fetchone()[0]
                info["values"][c] = {"distinct": f">{MAX_DISTINCT}", "non_null": nn}
        if "objekttypnr" in info["columns"]:
            info["objekttyper"] = cur.execute(
                f'SELECT objekttypnr, objekttyp, count(*) FROM "{tname}" GROUP BY 1,2 ORDER BY 1'
            ).fetchall()
        info["seconds"] = round(time.time() - t0, 1)
        out[tname] = info
        print(f"{os.path.basename(path)}:{tname} {n} rows {info['seconds']}s", file=sys.stderr)
    con.close()
    return out


def main():
    d = sys.argv[1]
    res = {}
    for f in sorted(os.listdir(d)):
        if f.endswith(".gpkg") and not f.startswith("._"):
            res[f] = inspect(os.path.join(d, f))
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
