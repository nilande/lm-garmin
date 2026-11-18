"""SPIKE – label diagnostic map: point types × characters, in a grid east of Syterstugan."""
from pyproj import Transformer

tr = Transformer.from_crs(3006, 4326, always_xy=True)
TYPES = [("sjo", "0x650d"), ("fjall", "0x6614"), ("ort", "0x0c00"), ("etikett", "0x2800")]
CHARS = [("a", "Anna"), ("á", "Ánná"), ("ŋ", "Aŋŋá"), ("č", "Čač"), ("Č", "Čuč"), ("đ", "Ađđa"), ("ŧ", "Aŧŧa")]
E0, N0, STEP = 520500, 7303500, 600  # grid origin (SWEREF 99 TM), 600 m spacing
nodes = []
nid = 1
for r, (tname, _) in enumerate(TYPES):
    for c, (ch, word) in enumerate(CHARS):
        lon, lat = tr.transform(E0 + c * STEP, N0 + (len(TYPES) - 1 - r) * STEP)
        label = f"{tname} {c + 1} {word}"
        nodes.append(f'<node id="{nid}" lat="{lat:.7f}" lon="{lon:.7f}" version="1">'
                     f'<tag k="diag" v="{tname}"/><tag k="name" v="{label}"/></node>')
        nid += 1
open("diag.osm", "w", encoding="utf-8").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n' + "\n".join(nodes) + "\n</osm>\n")
print(len(nodes), "points")
