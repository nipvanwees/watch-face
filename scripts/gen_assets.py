"""Generate the watch face PNGs (hands, ticks, center cap, metric icons).

Standard library only. Run from the project root:
    python3 scripts/gen_assets.py
Sizes must stay in sync with watchface/index.layout.js.
"""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "trex3pro.r" / "images"


def write_png(path, w, h, pixels):
    """pixels: list of rows, each a list of (r, g, b, a) tuples."""
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def coverage(d, radius):
    """Anti-aliased coverage of a pixel at distance d from a shape of given radius."""
    return max(0.0, min(1.0, radius - d + 0.5))


def render(w, h, layers):
    """layers: list of (color, fn(x, y) -> alpha), painted bottom to top."""
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            cx, cy = x + 0.5, y + 0.5
            r = g = b = a = 0.0
            for (lr, lg, lb), fn in layers:
                la = fn(cx, cy)
                if la <= 0:
                    continue
                # "over" compositing in premultiplied space
                r, g, b = lr * la + r * (1 - la), lg * la + g * (1 - la), lb * la + b * (1 - la)
                a = la + a * (1 - la)
            if a > 0:
                row.append((round(r / a), round(g / a), round(b / a), round(a * 255)))
            else:
                row.append((0, 0, 0, 0))
        rows.append(row)
    return rows


def capsule(ax, ay, bx, by, radius):
    return lambda x, y: coverage(seg_dist(x, y, ax, ay, bx, by), radius)


def circle(cx, cy, radius):
    return lambda x, y: coverage(math.hypot(x - cx, y - cy), radius)


def save(name, w, h, layers):
    write_png(OUT / name, w, h, render(w, h, layers))
    print(f"wrote {name} ({w}x{h})")


INDEX = (179, 168, 143)
DOT = (138, 129, 112)
RED = (214, 58, 42)
HAND_BODY = (61, 58, 51)
LUME = (233, 220, 188)
BLACK = (0, 0, 0)

C = 240  # dial center in the 480px design


def union(*shapes):
    """Combine (bbox, fn) shapes into one fn, only evaluating shapes whose bbox contains the pixel."""
    def fn(x, y):
        best = 0.0
        for (x0, y0, x1, y1), f in shapes:
            if x0 <= x <= x1 and y0 <= y <= y1:
                best = max(best, f(x, y))
        return best
    return fn


def radial(turns, r):
    a = turns * 2 * math.pi
    return math.sin(a), -math.cos(a), C + math.sin(a) * r, C - math.cos(a) * r


def bbox(points, pad):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def ellipse_outline(cx, cy, rx, ry, stroke):
    """Approximate anti-aliased outline of an axis-aligned ellipse."""
    def fn(x, y):
        nx, ny = (x - cx) / rx, (y - cy) / ry
        d = abs(math.hypot(nx, ny) - 1) * min(rx, ry)
        return coverage(d, stroke / 2)
    return fn


def polyline(points, radius):
    return union(*[(bbox([a, b], radius + 2), capsule(*a, *b, radius)) for a, b in zip(points, points[1:])])


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Dial: short hour ticks at the very edge (12 o'clock in red) and minute dots.
    # 3 o'clock is left empty for the time, 9 o'clock for the heart rate / water group.
    indices, dots = [], []
    for hour in range(1, 12):
        if hour in (3, 9):
            continue
        sx, sy, _, _ = radial(hour / 12, 0)
        a = (C + sx * 202, C + sy * 202)
        b = (C + sx * 228, C + sy * 228)
        indices.append((bbox([a, b], 3), capsule(*a, *b, 1.7)))
    for minute in range(60):
        if minute % 5 == 0:
            continue
        _, _, x, y = radial(minute / 60, 232)
        dots.append((bbox([(x, y)], 3), circle(x, y, 1.3)))
    save("dial.png", 480, 480, [
        (DOT, union(*dots)),
        (INDEX, union(*indices)),
        (RED, capsule(C, C - 228, C, C - 202, 2)),
    ])

    # Hands: dark body with a cream inlay strip on the outer part, pivot at the bottom center
    save("hand_hour.png", 12, 139, [
        (HAND_BODY, capsule(6, 134, 6, 4.5, 4.5)),
        (LUME, capsule(6, 134 - 40, 6, 134 - 122, 1.7)),
    ])
    save("hand_minute.png", 10, 234, [
        (HAND_BODY, capsule(5, 230, 5, 4, 4)),
        (LUME, capsule(5, 230 - 50, 5, 230 - 214, 1.6)),
    ])
    # Second hand: thin red with a short tail, pivot at (3, 230)
    save("hand_second.png", 6, 262, [(RED, capsule(3, 260, 3, 1, 1))])

    # Center cap
    save("center.png", 18, 18, [(RED, circle(9, 9, 7)), (BLACK, circle(9, 9, 2.6))])

    # Metric icons: thin outlines on a 40x44 tile, drawn at 2x around its center.
    # Tappable metrics (water, stretch) are red, display-only ones (heart rate, steps) warm grey.
    W, H, S = 40, 44, 2.0
    CX, CY = W / 2, H / 2
    STROKE = 2.2

    def in_heart(x, y, scale):
        hx, hy = (x - CX) / scale, (CY + 1.3 * S - y) / scale
        return (hx * hx + hy * hy - 1) ** 3 - hx * hx * hy ** 3 <= 0

    def heart_outline(x, y):
        inside = 0
        for sy in range(4):
            for sx in range(4):
                px_, py_ = x - 0.5 + (sx + 0.5) / 4, y - 0.5 + (sy + 0.5) / 4
                inside += in_heart(px_, py_, 8.5 * S) and not in_heart(px_, py_ + 0.4, 8.5 * S - 2.5)
        return inside / 16

    save("icon_heart.png", W, H, [(INDEX, heart_outline)])

    def at(*points):
        return [(CX + x * S, CY + y * S) for x, y in points]

    tile = (0, 0, W, H)

    # Stretch: figure in a side bend, one arm over the head
    save("icon_stretch.png", W, H, [(RED, union(
        (tile, ellipse_outline(CX + 4 * S, CY - 8.5 * S, 2.4 * S, 2.4 * S, STROKE)),
        (tile, polyline(at((-3, 10), (0, 1), (1, -2.5), (3, -5.5)), STROKE / 2)),
        (tile, polyline(at((1.5, -3.5), (-3, -8), (-8, -9.5)), STROKE / 2)),
        (tile, polyline(at((0, 1), (5, 9)), STROKE / 2)),
    ))])

    # Water: tapered glass with a water line
    save("icon_water.png", W, H, [(RED, union(
        (tile, polyline(at((-5.5, -9), (-4, 9), (4, 9), (5.5, -9)), STROKE / 2)),
        (tile, polyline(at((-3, 1.5), (3, 1.5)), STROKE / 2)),
    ))])

    # Steps: two footprints
    save("icon_steps.png", W, H, [(INDEX, union(*[
        (tile, ellipse_outline(CX + dx * S, CY + dy * S, rx * S, ry * S, STROKE))
        for dx, dy, rx, ry in [(-3.5, -1, 2.8, 5), (-3.5, 7.5, 2, 1.8), (3.5, -6, 2.8, 5), (3.5, 2.5, 2, 1.8)]
    ]))])


if __name__ == "__main__":
    main()
