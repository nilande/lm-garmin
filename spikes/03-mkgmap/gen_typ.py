"""SPIKE – generate TYP text files for mkgmap (colours roughly from the LM legend)."""
import os


def poly(t, name, col, pattern=None):
    if pattern:
        rows = "\n".join(f'"{r}"' for r in pattern)
        return (f'[_polygon]\nType={t}\nString1=0x04,{name}\nXpm="32 32 2 1"\n'
                f'"a c {col[0]}"\n"b c {col[1]}"\n{rows}\n[end]\n')
    return f'[_polygon]\nType={t}\nString1=0x04,{name}\nXpm="0 0 1 0"\n"a c {col}"\n[end]\n'


def line(t, name, col, w, border=None, dash=None):
    if dash:
        pat = "".join("a" if (i % (dash[0] + dash[1])) < dash[0] else "b" for i in range(32))
        rows = "\n".join(f'"{pat}"' for _ in range(w))
        return (f'[_line]\nType={t}\nString1=0x04,{name}\nUseOrientation=Y\nXpm="32 {w} 2 1"\n'
                f'"a c {col}"\n"b c none"\n{rows}\n[end]\n')
    if border:
        return (f'[_line]\nType={t}\nString1=0x04,{name}\nLineWidth={w}\nBorderWidth=1\n'
                f'Xpm="0 0 2 0"\n"a c {col}"\n"b c {border}"\n[end]\n')
    return f'[_line]\nType={t}\nString1=0x04,{name}\nLineWidth={w}\nXpm="0 0 1 0"\n"a c {col}"\n[end]\n'


def point(t, name, col, size=7):
    rows = "\n".join(f'"{"a" * size}"' for _ in range(size))
    return f'[_point]\nType={t}\nString1=0x04,{name}\nXpm="{size} {size} 1 1"\n"a c {col}"\n{rows}\n[end]\n'


marsh = [("a" * 32 if r % 4 == 0 else "b" * 32) for r in range(32)]
order = [("0x28", 1), ("0x3c", 4), ("0x48", 4), ("0x3f", 4), ("0x4d", 3),
         ("0x01", 2), ("0x02", 2), ("0x03", 2), ("0x0c", 2), ("0x10f03", 1), ("0x4e", 2), ("0x4f", 2),
         ("0x52", 1), ("0x50", 1), ("0x10f01", 1), ("0x10f02", 1),
         ("0x51", 3), ("0x10f04", 3), ("0x10f05", 3), ("0x10f06", 3), ("0x10f07", 3), ("0x13", 5)]
base = [
    "[_id]\nFID=5730\nProductCode=1\nCodePage=1252\n[end]\n",
    "[_drawOrder]\n" + "\n".join(f"Type={t},{o}" for t, o in order) + "\n[end]\n",
    poly("0x28", "Hav", "#A6D6F5"), poly("0x3c", "Sjö", "#A6D6F5"), poly("0x48", "Vattendragsyta", "#A6D6F5"),
    poly("0x3f", "Anlagt vatten", "#A6D6F5"), poly("0x4d", "Glaciär", "#E6F4FB"),
    poly("0x01", "Sluten bebyggelse", "#D58B5B"), poly("0x02", "Hög bebyggelse", "#E0B08C"),
    poly("0x03", "Låg bebyggelse", "#EECB9F"), poly("0x0c", "Industri", "#E5E5E5"),
    poly("0x10f03", "Öppen mark", "#FDFBE4"), poly("0x4e", "Åker", "#FBF29B"), poly("0x4f", "Fruktodling", "#FBF29B"),
    poly("0x52", "Kalfjäll", "#FFFFFF"), poly("0x50", "Barr- och blandskog", "#CFE8B6"),
    poly("0x10f01", "Lövskog", "#E3F2CF"), poly("0x10f02", "Fjällbjörkskog", "#E8F5DC"),
    poly("0x51", "Sankmark, fast", ("#E88A2E", "none"), marsh),
    poly("0x10f04", "Sankmark, våt", ("#2AA0E0", "none"), marsh),
    poly("0x10f05", "Berg i dagen", "#B4B4B4"), poly("0x10f06", "Tät vegetation", "#C7E39E"),
    poly("0x10f07", "Blockig mark", "#D0D0D0"), poly("0x13", "Byggnad", "#505050"),
    line("0x20", "Höjdkurva", "#C9865A", 1), line("0x22", "Stödkurva", "#C9865A", 2),
    line("0x21", "Gropkurva", "#C9865A", 1),
    line("0x01", "Motorväg", "#C0392B", 5, "#7A1F15"), line("0x02", "Motortrafikled", "#C0392B", 4, "#7A1F15"),
    line("0x03", "Landsväg", "#E07850", 4, "#8A3A20"), line("0x04", "Landsväg liten", "#E89070", 3, "#8A3A20"),
    line("0x05", "Småväg", "#808080", 2), line("0x06", "Gata", "#808080", 2), line("0x07", "Småväg enkel", "#A0A0A0", 1),
    line("0x0a", "Traktorväg", "#606060", 2, dash=(4, 3)), line("0x11", "Cykelväg", "#8A6A3A", 1),
    line("0x16", "Stig", "#333333", 2, dash=(2, 2)), line("0x18", "Vattendrag", "#3A8FD0", 1),
    line("0x29", "Kraftledning", "#202020", 1), line("0x1c", "Gräns", "#C8A0E0", 3),
    point("0x6402", "Byggnad", "#000000", 3), point("0x6616", "Höjdpunkt", "#000000", 3),
    point("0x650d", "Sjö, namn", "#3A8FD0", 5),
]
over = [
    "[_id]\nFID=5731\nProductCode=1\nCodePage=1252\n[end]\n",
    line("0x10e10", "Vinterled, skoter tillåten", "#FF7A00", 4, "#7A3A00"),
    line("0x10e11", "Vinterled, påbjuden", "#E00000", 5, "#600000"),
    line("0x10e12", "Vinterled, skoter ej tillåten", "#7A7A7A", 3, dash=(3, 3)),
    line("0x10e13", "Vinterled, ingen information", "#FFB060", 3, dash=(6, 3)),
    point("0x11610", "Påbjuden färdväg skoter", "#E00000", 9),
]
os.makedirs("typ", exist_ok=True)
open("typ/lm.txt", "w", encoding="cp1252").write("\n".join(base))
open("typ/skoter.txt", "w", encoding="cp1252").write("\n".join(over))
