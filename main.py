#!/usr/bin/env python3
"""Best Day Ever - generative picture for make.fun 'Make the AI judge happy'.

Pure Python 3 stdlib (no PIL in the sandbox). A chubby orange cat at its
surprise birthday party: party hat, laughing with its mouth wide open, eyes
squeezed shut, tears of joy, paws thrown up, balloons, confetti and a rainbow
behind it. 1024x1024, fully deterministic (fixed seeds -> identical bytes
every run). Writes /output/entry.png (override with ENTRY_OUT locally).
"""
import math, os, random, struct, zlib

W = H = 1024


def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def grad(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            p0, c0 = stops[i - 1]
            p1, c1 = stops[i]
            return mix(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.p = bytearray(w * h * 3)

    def blend(self, x, y, c, a):
        if a <= 0.0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = (y * self.w + x) * 3
        ia = 1.0 - a
        self.p[i] = int(self.p[i] * ia + c[0] * a)
        self.p[i + 1] = int(self.p[i + 1] * ia + c[1] * a)
        self.p[i + 2] = int(self.p[i + 2] * ia + c[2] * a)

    def vgrad(self, stops):
        for y in range(self.h):
            c = grad(stops, y / (self.h - 1))
            row = bytes((int(c[0]), int(c[1]), int(c[2]))) * self.w
            i = y * self.w * 3
            self.p[i:i + self.w * 3] = row


def draw(cv, bbox, sdf, paint, aa=1.0):
    x0 = max(0, int(bbox[0])); y0 = max(0, int(bbox[1]))
    x1 = min(cv.w, int(bbox[2]) + 1); y1 = min(cv.h, int(bbox[3]) + 1)
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = sdf(x + 0.5, y + 0.5)
            a = clamp(0.5 - d / aa, 0.0, 1.0)
            if a > 0.0:
                c = paint(x + 0.5, y + 0.5)
                cv.blend(x, y, c, a * c[3])


def solid(c, a=1.0):
    return lambda x, y: (c[0], c[1], c[2], a)


def sd_circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def sd_ellipse(cx, cy, rx, ry):
    m = min(rx, ry)
    return lambda x, y: (math.hypot((x - cx) / rx, (y - cy) / ry) - 1.0) * m


def sd_ring(cx, cy, r, hw):
    return lambda x, y: abs(math.hypot(x - cx, y - cy) - r) - hw


def sd_poly(pts):
    """Inigo Quilez polygon SDF (exact sign test)."""
    def f(px, py):
        d = (px - pts[0][0]) ** 2 + (py - pts[0][1]) ** 2
        s = 1.0
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]; xj, yj = pts[j]
            ex, ey = xj - xi, yj - yi
            wx, wy = px - xi, py - yi
            ee = ex * ex + ey * ey
            t = clamp((wx * ex + wy * ey) / ee, 0.0, 1.0) if ee > 0 else 0.0
            dx, dy = wx - ex * t, wy - ey * t
            dd = dx * dx + dy * dy
            if dd < d:
                d = dd
            c1 = py >= yi
            c2 = py < yj
            c3 = ex * wy > ey * wx
            if c1 == c2 == c3:
                s = -s
            j = i
        return s * math.sqrt(d)
    return f


def sd_capsule(x1, y1, x2, y2, r):
    def f(px, py):
        ex, ey = x2 - x1, y2 - y1
        wx, wy = px - x1, py - y1
        t = clamp((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        return math.hypot(wx - ex * t, wy - ey * t) - r
    return f


def sd_sparkle(cx, cy, r):
    def f(px, py):
        x, y = abs(px - cx), abs(py - cy)
        d1 = (x / (r * 0.16) + y / r) - 1.0
        d2 = (x / r + y / (r * 0.16)) - 1.0
        return min(d1, d2) * r * 0.16
    return f


def arc_pts(cx, cy, r, a0, a1, n=7):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1))))
            for i in range(n)]


def stroke(cv, pts, r, col, alpha=1.0, aa=1.6):
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        draw(cv, (min(x1, x2) - r - 3, min(y1, y2) - r - 3,
                  max(x1, x2) + r + 3, max(y1, y2) + r + 3),
             sd_capsule(x1, y1, x2, y2, r), solid(col, alpha), aa=aa)


def balloon(cv, cx, cy, rx, ry, col, dark):
    # string: gentle S-curve of capsules going down
    pts = [(cx + 10 * math.sin(t * 2.4), cy + ry + 8 + t * 118) for t in
           (0.0, 0.25, 0.5, 0.75, 1.0)]
    stroke(cv, pts, 3.2, (70, 60, 90), 0.8, aa=1.2)
    draw(cv, (cx - rx - 6, cy - ry - 6, cx + rx + 6, cy + ry + 6),
         sd_ellipse(cx, cy, rx + 4, ry + 4), solid(dark), aa=1.6)
    draw(cv, (cx - rx - 2, cy - ry - 2, cx + rx + 2, cy + ry + 2),
         sd_ellipse(cx, cy, rx, ry), solid(col), aa=1.6)
    knot = [(cx - 10, cy + ry + 2), (cx + 10, cy + ry + 2), (cx, cy + ry + 16)]
    draw(cv, (cx - 12, cy + ry, cx + 12, cy + ry + 18), sd_poly(knot),
         solid(dark), aa=1.4)
    draw(cv, (cx - rx * 0.55, cy - ry * 0.62, cx - rx * 0.05, cy - ry * 0.05),
         sd_ellipse(cx - rx * 0.32, cy - ry * 0.34, rx * 0.20, ry * 0.30),
         solid((255, 255, 255), 0.55), aa=8.0)


def confetti(cv, rng, n, front=False):
    cols = [(255, 77, 109), (255, 190, 40), (38, 201, 176), (120, 110, 255),
            (255, 120, 60), (240, 90, 200)]
    for _ in range(n):
        cx = rng.uniform(20, 1004)
        cy = rng.uniform(20, 1004)
        col = cols[rng.randrange(len(cols))]
        if rng.random() < 0.45:
            draw(cv, (cx - 9, cy - 9, cx + 9, cy + 9), sd_circle(cx, cy, 6.5),
                 solid(col, 0.92), aa=1.4)
        else:
            ang = rng.uniform(0, math.pi)
            ln, wd = rng.uniform(11, 17), 5.5
            dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
            px, py = -math.sin(ang) * wd, math.cos(ang) * wd
            pts = [(cx - dx - px, cy - dy - py), (cx + dx - px, cy + dy - py),
                   (cx + dx + px, cy + dy + py), (cx - dx + px, cy - dy + py)]
            draw(cv, (cx - 22, cy - 22, cx + 22, cy + 22), sd_poly(pts),
                 solid(col, 0.92), aa=1.4)


def main():
    cv = Canvas(W, H)
    rng = random.Random(2026)

    # --- sky: bright blue melting into warm cream ---
    cv.vgrad([(0.0, (96, 176, 250)), (0.45, (150, 212, 252)),
              (0.75, (208, 240, 252)), (1.0, (255, 243, 205))])

    # --- rainbow arcs behind the cat ---
    rb = [(255, 84, 84), (255, 152, 48), (255, 216, 64),
          (96, 205, 96), (66, 150, 255), (150, 100, 230)]
    for i, col in enumerate(rb):
        r = 452 - i * 31
        draw(cv, (30, -60, 994, 560), sd_ring(512, 500, r, 14.5),
             solid(col, 0.88), aa=1.8)

    # soft clouds
    def cloud(cx, cy, s, a):
        for dx, dy, r in ((-56, 10, 34), (-18, -8, 46), (30, -10, 50),
                          (72, 8, 36), (6, 14, 42)):
            draw(cv, (cx + (dx - r - 14) * s, cy + (dy - r - 14) * s,
                      cx + (dx + r + 14) * s, cy + (dy + r + 14) * s),
                 sd_circle(cx + dx * s, cy + dy * s, r * s),
                 solid((255, 255, 255), a), aa=14.0)
    cloud(142, 122, 1.0, 0.9)
    cloud(890, 138, 0.85, 0.9)
    cloud(924, 838, 0.7, 0.55)
    cloud(96, 856, 0.62, 0.55)

    # background confetti
    confetti(cv, rng, 55)

    # balloons
    balloon(cv, 138, 330, 74, 90, (255, 84, 96), (196, 44, 62))
    balloon(cv, 898, 292, 68, 84, (38, 198, 218), (16, 138, 158))

    # clouds where the rainbow lands
    cloud(128, 560, 0.8, 0.85)
    cloud(900, 566, 0.75, 0.85)

    OUT = (148, 84, 38)
    FUR = (250, 166, 74)
    FUR_D = (230, 128, 40)
    CREAM = (255, 228, 182)
    PINK = (255, 120, 155)

    # --- body (mostly hidden behind the huge head) ---
    draw(cv, (512 - 212, 690, 512 + 212, 1010), sd_ellipse(512, 856, 204, 152),
         solid(OUT), aa=1.6)
    draw(cv, (512 - 204, 696, 512 + 204, 1004), sd_ellipse(512, 856, 196, 144),
         solid(FUR), aa=1.6)
    draw(cv, (512 - 120, 770, 512 + 120, 1000), sd_ellipse(512, 892, 112, 104),
         solid(CREAM), aa=2.0)
    # feet
    for fx in (382, 642):
        draw(cv, (fx - 72, 916, fx + 72, 998), sd_ellipse(fx, 958, 66, 40),
             solid(OUT), aa=1.6)
        draw(cv, (fx - 66, 920, fx + 66, 994), sd_ellipse(fx, 958, 60, 34),
             solid(FUR), aa=1.6)
        draw(cv, (fx - 17, 940, fx + 17, 972), sd_ellipse(fx, 956, 13, 11),
             solid(PINK, 0.9), aa=1.6)

    # --- arms raised in celebration, drawn before the head so the
    # shoulders tuck behind it and only forearms + paws peek out ---
    for sgn in (-1, 1):
        sx, sy = 512 + sgn * 150, 690           # shoulder (hidden by head)
        px, py = 512 + sgn * 316, 452           # paw centre
        draw(cv, (min(sx, px) - 50, min(sy, py) - 66, max(sx, px) + 50,
                  max(sy, py) + 10),
             sd_capsule(sx, sy, px, py, 39), solid(OUT), aa=1.6)
        draw(cv, (min(sx, px) - 44, min(sy, py) - 60, max(sx, px) + 44,
                  max(sy, py) + 6),
             sd_capsule(sx, sy, px, py, 32), solid(FUR), aa=1.6)
        draw(cv, (px - 50, py - 64, px + 50, py + 64),
             sd_ellipse(px, py, 44, 58), solid(OUT), aa=1.6)
        draw(cv, (px - 44, py - 58, px + 44, py + 58),
             sd_ellipse(px, py, 38, 52), solid(FUR), aa=1.6)
        for txo in (-15, 0, 15):  # toe beans on the raised paws
            draw(cv, (px + txo - 9, py - 48, px + txo + 9, py - 28),
                 sd_ellipse(px + txo, py - 38, 7, 9), solid(PINK, 0.95), aa=1.4)
        draw(cv, (px - 16, py + 2, px + 16, py + 36),
             sd_ellipse(px, py + 19, 13, 14), solid(PINK, 0.95), aa=1.4)

    # --- ears (behind head, above the rainbow) ---
    ear_l = [(330, 330), (286, 168), (452, 240)]
    ear_r = [(694, 330), (738, 168), (572, 240)]
    for ear in (ear_l, ear_r):
        big = [(512 + (x - 512) * 1.08, 330 + (y - 330) * 1.12) for (x, y) in ear]
        draw(cv, (min(p[0] for p in big) - 4, min(p[1] for p in big) - 4,
                  max(p[0] for p in big) + 4, max(p[1] for p in big) + 4),
             sd_poly(big), solid(OUT), aa=1.8)
        draw(cv, (min(p[0] for p in ear) - 4, min(p[1] for p in ear) - 4,
                  max(p[0] for p in ear) + 4, max(p[1] for p in ear) + 4),
             sd_poly(ear), solid(FUR), aa=1.8)
        cx = sum(p[0] for p in ear) / 3
        cy = sum(p[1] for p in ear) / 3
        small = [(cx + (x - cx) * 0.52, cy + (y - cy) * 0.52) for (x, y) in ear]
        draw(cv, (min(p[0] for p in small) - 4, min(p[1] for p in small) - 4,
                  max(p[0] for p in small) + 4, max(p[1] for p in small) + 4),
             sd_poly(small), solid(PINK), aa=2.0)

    # --- the huge laughing head ---
    draw(cv, (512 - 262, 238, 512 + 262, 766), sd_circle(512, 502, 256),
         solid(OUT), aa=1.6)
    draw(cv, (512 - 254, 246, 512 + 254, 758), sd_circle(512, 502, 248),
         solid(FUR), aa=1.6)
    # muzzle patch
    draw(cv, (512 - 168, 520, 512 + 168, 756), sd_ellipse(512, 640, 160, 110),
         solid(CREAM), aa=2.4)
    # (no forehead stripes: the party hat covers that area)

    # --- laughing eyes: squeezed-shut happy arcs ---
    for ex in (398, 626):
        pts = arc_pts(ex, 486, 52, 195, 345, 9)
        stroke(cv, pts, 14, (92, 52, 26), 1.0, aa=1.8)

    # tears of joy flying off the outer eye corners
    for (tx, ty, s) in [(318, 452, 1.0), (282, 492, 0.7), (706, 452, 1.0),
                        (742, 492, 0.7)]:
        drop = [(tx, ty - 26 * s), (tx + 15 * s, ty + 8 * s),
                (tx + 8 * s, ty + 22 * s), (tx - 8 * s, ty + 22 * s),
                (tx - 15 * s, ty + 8 * s)]
        draw(cv, (tx - 18 * s, ty - 28 * s, tx + 18 * s, ty + 25 * s),
             sd_poly(drop), solid((96, 190, 250), 0.92), aa=1.6)
        draw(cv, (tx - 10 * s, ty - 4 * s, tx + 2 * s, ty + 10 * s),
             sd_circle(tx - 4 * s, ty + 3 * s, 4.5 * s),
             solid((255, 255, 255), 0.8), aa=1.4)

    # nose (sits clearly on the muzzle, above the mouth)
    nose = [(512 - 19, 538), (512 + 19, 538), (512, 561)]
    draw(cv, (512 - 22, 535, 512 + 22, 564), sd_poly(nose),
         solid((240, 96, 128)), aa=1.6)

    # --- the big open laughing mouth ---
    draw(cv, (512 - 118, 570, 512 + 118, 736), sd_ellipse(512, 648, 112, 84),
         solid((122, 32, 40)), aa=1.8)
    # tongue
    draw(cv, (512 - 62, 656, 512 + 62, 730), sd_ellipse(512, 696, 56, 30),
         solid((255, 130, 150)), aa=1.8)
    # upper teeth strip
    draw(cv, (512 - 96, 566, 512 + 96, 616), sd_ellipse(512, 592, 92, 22),
         solid((255, 252, 246)), aa=1.8)

    # blush
    for bx in (330, 694):
        draw(cv, (bx - 56, 566, bx + 56, 622), sd_ellipse(bx, 594, 48, 25),
             solid((255, 110, 145), 0.55), aa=15.0)

    # whiskers (short, joyful)
    for sgn in (-1, 1):
        for dy, tilt in ((-4, -8), (12, 4)):
            x0 = 512 + sgn * 130
            x1 = 512 + sgn * 208
            draw(cv, (min(x0, x1) - 4, 576 + dy - 10, max(x0, x1) + 4,
                      576 + dy + tilt + 10),
                 sd_capsule(x0, 582 + dy, x1, 582 + dy + tilt, 2.6),
                 solid((255, 252, 246), 0.8), aa=1.2)

    # --- party hat, bigger, tilted right, on top of the head ---
    hat = [(412, 272), (656, 240), (592, 30)]
    cxh = sum(p[0] for p in hat) / 3
    cyh = sum(p[1] for p in hat) / 3
    big = [(cxh + (x - cxh) * 1.09, cyh + (y - cyh) * 1.09) for (x, y) in hat]
    draw(cv, (min(p[0] for p in big) - 4, min(p[1] for p in big) - 4,
              max(p[0] for p in big) + 4, max(p[1] for p in big) + 4),
         sd_poly(big), solid(OUT), aa=1.8)
    draw(cv, (min(p[0] for p in hat) - 4, min(p[1] for p in hat) - 4,
              max(p[0] for p in hat) + 4, max(p[1] for p in hat) + 4),
         sd_poly(hat), solid((255, 84, 120)), aa=1.8)
    # hat stripes: two diagonal bands clipped by the cone
    (ax, ay), (bx, by), (tx, ty) = hat
    for t, col in ((0.36, (255, 205, 60)), (0.66, (64, 200, 220))):
        band = [(ax + (tx - ax) * t - 78, ay + (ty - ay) * t + 30),
                (bx + (tx - bx) * t + 30, by + (ty - by) * t + 30),
                (bx + (tx - bx) * t + 40, by + (ty - by) * t - 16),
                (ax + (tx - ax) * t - 68, ay + (ty - ay) * t - 16)]
        both = lambda x, y, h=sd_poly(hat), b=sd_poly(band): max(h(x, y), b(x, y))
        draw(cv, (min(p[0] for p in band) - 3, min(p[1] for p in band) - 3,
                  max(p[0] for p in band) + 3, max(p[1] for p in band) + 3),
             both, solid(col), aa=1.6)
    # thin brim hugging the head + pompom
    draw(cv, (412 - 30, 240 - 22, 656 + 30, 272 + 22),
         sd_ellipse(534, 258, 140, 17), solid((255, 205, 60)), aa=1.8)
    draw(cv, (592 - 38, 30 - 40, 592 + 38, 30 + 34), sd_circle(592, 26, 34),
         solid(OUT), aa=1.6)
    draw(cv, (592 - 31, 30 - 33, 592 + 31, 30 + 27), sd_circle(592, 26, 27),
         solid((255, 240, 120)), aa=1.6)

    # front confetti + sparkles
    confetti(cv, rng, 16, front=True)
    for cx, cy, r in [(206, 660, 24), (830, 700, 20), (150, 90, 18),
                      (884, 84, 22), (512, 130, 16)]:
        draw(cv, (cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3),
             sd_sparkle(cx, cy, r), solid((255, 226, 92), 0.95), aa=1.6)

    # --- PNG encode (deterministic) ---
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += cv.p[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    out = os.environ.get("ENTRY_OUT", "/output/entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        f.write(png)
    print(f"wrote {out}: {len(png)} bytes")


if __name__ == "__main__":
    main()
