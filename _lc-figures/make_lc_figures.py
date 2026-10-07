"""Generate the GELOS Land Cover dataset figures: where the chips are, and how
many there are of each class.

Writes _lc-figures/chip-map.svg and _lc-figures/class-distribution.svg, which
{{< lc-figure map >}} and {{< lc-figure classes >}} inline into a slide. Both
are drawn from the same table, the chip centroids that gelos-lc-datagen
publishes for the GELOS app (one point per chip, with its land cover class),
read from the open gelos-fm bucket and kept in _lc-figures/cache/. Land is
Natural Earth 1:110m, cached there too. This script owns the geometry, the
text and the binning; lc-figures.css owns colour and type. Run with
`pixi run lc-figures` and commit the two SVGs; never edit them by hand.
"""

import gzip
import math
import urllib.request
from collections import defaultdict
from pathlib import Path

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles
from shapely.geometry import shape

BUCKET = "https://gelos-fm.s3.amazonaws.com"
CENTROIDS = "pmtiles/centroids.pmtiles"  # one point per chip: id, category
LAND = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
    "/master/geojson/ne_110m_land.geojson"
)

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
MAP_OUT = HERE / "chip-map.svg"
CLASSES_OUT = HERE / "class-distribution.svg"

# Map: chips are counted in cells CELL degrees on a side and each occupied
# cell is one dot, placed at the mean position of its chips, with an area
# that grows with the count (DOT_MIN for one chip, up to DOT_MAX)
CELL = 1.0
DOT_MIN, DOT_MAX = 3.0, 7.5
LAT_MIN = -60  # the map stops here: no chips further south, so no Antarctica
SIMPLIFY = 0.4  # degrees of tolerance when simplifying the coastline
MIN_LAND = 1.0  # square degrees; smaller islands are dropped
MAP_W = 1000
MAP_PAD = 8
CAPTION_H = 44

# Bar chart: one row per class, descending
BAR_W = 1000
LABEL_W = 240  # room for the class names, left of the baseline
VALUE_W = 130  # room for the counts, right of the longest bar
BAR_H, ROW_H = 40, 64
BAR_PAD_TOP = 58  # under the heading
BAR_PAD_BOTTOM = 16
BAR_RADIUS = 4


# ---- Data ------------------------------------------------------------------


def fetch(url, name):
    """A file downloaded once into the cache."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
    return path


def chips():
    """(lon, lat, category, colour) for every chip, from the app's centroid
    tiles.

    The colour is the class colour the GELOS app draws the chip in. The tiles
    are read at their deepest zoom, where tippecanoe keeps every point; tile
    buffers repeat points near tile edges, so they are deduplicated by chip id.
    """
    path = fetch(f"{BUCKET}/{CENTROIDS}", Path(CENTROIDS).name)
    seen = {}
    with open(path, "rb") as f:
        reader = Reader(MmapSource(f))
        maxzoom = reader.header()["max_zoom"]
        for (z, x, y), data in all_tiles(reader.get_bytes):
            if z != maxzoom:
                continue
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            n = 2**z
            for layer in mapbox_vector_tile.decode(data).values():
                extent = layer["extent"]
                for feat in layer["features"]:
                    assert feat["geometry"]["type"] == "Point"
                    px, py = feat["geometry"]["coordinates"]  # y up
                    lon = (x + px / extent) / n * 360 - 180
                    merc = (y + 1 - py / extent) / n
                    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * merc))))
                    props = feat["properties"]
                    seen[props["id"]] = (lon, lat, props["category"], props["color"])
    return [seen[k] for k in sorted(seen)]


def class_colours(points):
    """Class -> colour, checking the data gives each class a single colour."""
    colours = defaultdict(set)
    for _, _, category, colour in points:
        colours[category].add(colour.lower())
    for category, found in colours.items():
        assert len(found) == 1, f"{category} has several colours: {sorted(found)}"
    return {category: next(iter(found)) for category, found in colours.items()}


def land():
    """Land polygons as lists of (lon, lat) rings, simplified for a small map."""
    import json

    path = fetch(LAND, Path(LAND).name)
    rings = []
    for feature in json.loads(path.read_text())["features"]:
        geom = shape(feature["geometry"])
        if geom.bounds[3] < LAT_MIN or geom.area < MIN_LAND:
            continue
        geom = geom.simplify(SIMPLIFY, preserve_topology=True)
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            rings.append(list(poly.exterior.coords))
            rings.extend(list(ring.coords) for ring in poly.interiors)
    return rings


# ---- Map -------------------------------------------------------------------

# Equal Earth (Šavrič, Patterson & Jenny 2018), in radians
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796


def equal_earth(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(math.sqrt(3) / 2 * math.sin(phi))
    t2 = theta * theta
    t6 = t2 * t2 * t2
    x = 2 * math.sqrt(3) * lam * math.cos(theta)
    x /= 3 * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))
    y = theta * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


X_MAX = equal_earth(180, 0)[0]
Y_MAX = equal_earth(0, 90)[1]
Y_MIN = equal_earth(0, LAT_MIN)[1]
SCALE = (MAP_W - 2 * MAP_PAD) / (2 * X_MAX)
MAP_H = (Y_MAX - Y_MIN) * SCALE + 2 * MAP_PAD


def to_svg(lon, lat):
    x, y = equal_earth(lon, max(lat, LAT_MIN))
    return MAP_PAD + (x + X_MAX) * SCALE, MAP_PAD + (Y_MAX - y) * SCALE


def ring_path(ring):
    pts = [to_svg(lon, lat) for lon, lat in ring]
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


def binned(points):
    """(lon, lat, count) per occupied CELL-degree cell, at the chips' mean."""
    cells = defaultdict(list)
    for lon, lat, *_ in points:
        cells[(math.floor(lon / CELL), math.floor(lat / CELL))].append((lon, lat))
    out = []
    for pts in cells.values():
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        out.append((lon, lat, len(pts)))
    return sorted(out, key=lambda c: -c[2])  # big dots first, small ones on top


def dot_radius(count, biggest):
    # Area grows with the count: radius with its square root
    t = math.sqrt(count / biggest)
    return DOT_MIN + (DOT_MAX - DOT_MIN) * t


def fmt(n):
    return f"{n:,}"


def map_svg(points):
    cells = binned(points)
    biggest = cells[0][2]
    total = len(points)
    height = MAP_H + CAPTION_H
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {MAP_W} {height:.0f}"'
        f' role="img" aria-label="World map of the {fmt(total)} GELOS Land Cover'
        ' chips: dots on every inhabited continent, densest in Africa, Europe,'
        ' South and East Asia and the Americas.">',
        f'<path class="land" d="{"".join(ring_path(r) for r in land())}"/>',
        '<g class="chips">',
    ]
    for lon, lat, count in cells:
        x, y = to_svg(lon, lat)
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot_radius(count, biggest):.1f}">'
            f"<title>{fmt(count)} chips</title></circle>"
        )
    out += [
        "</g>",
        f'<text class="caption" x="{MAP_PAD}" y="{height - 12:.0f}">'
        f'<tspan class="mono">{fmt(total)}</tspan> chips'
        f'<tspan class="note"> · dot area ∝ chips within {CELL:g}°</tspan></text>',
        "</svg>",
    ]
    return "\n".join(out), cells


def classes_svg(points):
    counts = defaultdict(int)
    for _, _, category, _ in points:
        counts[category] += 1
    colours = class_colours(points)
    rows = sorted(counts.items(), key=lambda kv: -kv[1])
    biggest = rows[0][1]
    x0 = LABEL_W
    span = BAR_W - LABEL_W - VALUE_W
    height = BAR_PAD_TOP + ROW_H * len(rows) + BAR_PAD_BOTTOM
    desc = ", ".join(f"{name} {fmt(n)}" for name, n in rows)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BAR_W} {height}"'
        f' role="img" aria-label="Bar chart of chips per land cover class: {desc}.">',
        f'<text class="heading" x="{x0}" y="30">Chips per land cover class</text>',
        f'<line class="baseline" x1="{x0}" y1="{BAR_PAD_TOP - 8}" x2="{x0}" y2="{height - BAR_PAD_BOTTOM}"/>',
    ]
    r = BAR_RADIUS
    for i, (name, n) in enumerate(rows):
        y = BAR_PAD_TOP + i * ROW_H
        w = span * n / biggest
        mid = y + BAR_H / 2
        # Square at the baseline, rounded at the data end
        d = (
            f"M{x0} {y}h{w - r:.1f}a{r} {r} 0 0 1 {r} {r}v{BAR_H - 2 * r}"
            f"a{r} {r} 0 0 1 -{r} {r}H{x0}Z"
        )
        out += [
            f'<g class="row"><title>{name}: {fmt(n)} chips</title>',
            f'<text class="name" x="{x0 - 18}" y="{mid:.0f}">{name}</text>',
            # The one colour set here rather than in the CSS: it is the class's
            # colour in the dataset, i.e. data, not styling
            f'<path class="bar" fill="{colours[name]}" d="{d}"/>',
            f'<text class="value mono" x="{x0 + w + 14:.1f}" y="{mid:.0f}">{fmt(n)}</text>',
            "</g>",
        ]
    out.append("</svg>")
    return "\n".join(out), [(name, n, colours[name]) for name, n in rows]


def main():
    points = chips()
    svg, cells = map_svg(points)
    MAP_OUT.write_text(svg + "\n")
    print(f"{len(points):,} chips in {len(cells):,} cells of {CELL:g}° (largest {cells[0][2]:,})")
    print(f"wrote {MAP_OUT.relative_to(HERE.parent)} ({MAP_OUT.stat().st_size / 1024:.0f} KB)")

    svg, rows = classes_svg(points)
    CLASSES_OUT.write_text(svg + "\n")
    for name, n, colour in rows:
        print(f"  {name:<12} {n:>7,}  {colour}")
    print(f"wrote {CLASSES_OUT.relative_to(HERE.parent)} ({CLASSES_OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
