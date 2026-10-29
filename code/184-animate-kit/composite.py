# 2D overlay (title, tags, chips, rulebook, captions) composited over the Blender frames.
# usage: composite.py <in_dir> <out_dir> [frame ...]   (frames named f_0001.png or still_0001.png)
import sys, os, glob, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = os.environ.get("ANIMATE_FONT", "Figtree.ttf")
FPS = 25
INK = (4, 20, 26); SUB = (19, 52, 64); MUTED = (98, 120, 128); TEAL = (0, 151, 153)
ORANGE = (230, 82, 30); AMBER = (180, 83, 9); RED = (205, 40, 32); PURPLE = (91, 63, 209)


def font(sz, w="SemiBold"):
    f = ImageFont.truetype(FONT, sz)
    try:
        f.set_variation_by_name(w)
    except Exception:
        pass
    return f


def cl(x): return 0.0 if x < 0 else 1.0 if x > 1 else x
def ease(x): x = cl(x); return 1 - (1 - x) ** 3
def seg(t, a, b): return cl((t - a) / (b - a))
def window(t, a, b, fi=0.35, fo=0.35): return min(ease(seg(t, a, a + fi)), 1 - ease(seg(t, b - fo, b)))


def layer(size): return Image.new("RGBA", size, (0, 0, 0, 0))


def apply_alpha(im, a, dy=0):
    if a <= 0:
        return None
    if a < 1:
        r, g, b, al = im.split(); al = al.point(lambda v: int(v * a)); im = Image.merge("RGBA", (r, g, b, al))
    if dy:
        out = layer(im.size); out.paste(im, (0, int(dy)), im); im = out
    return im


def shadowed(base, im, blur=10, off=4, op=0.12):
    a = im.split()[3].point(lambda v: int(v * op))
    sh = Image.new("RGBA", im.size, (4, 20, 26, 0)); sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(sh, (0, off)); base.alpha_composite(im)


class Overlay:
    def __init__(self, W, H):
        self.W, self.H = W, H; self.s = W / 1280.0
        self.cache = {}

    def S(self, v): return int(round(v * self.s))

    def title(self):
        if "title" in self.cache:
            return self.cache["title"]
        W, S = self.W, self.S; im = layer((W, self.H)); d = ImageDraw.Draw(im)
        f = font(S(13), "SemiBold"); t = "M C P   I N   O N E   P I C T U R E"
        tw = d.textlength(t, font=f); px, py = S(22), S(9)
        x0 = (W - tw) / 2 - px; y0 = S(22)
        d.rounded_rectangle((x0, y0, x0 + tw + 2 * px, y0 + S(13) + 2 * py), radius=S(20), fill=(255, 255, 255, 200))
        d.text(((W - tw) / 2, y0 + py - S(1)), t, font=f, fill=SUB)
        f2 = font(S(40), "Bold"); a = "The chef only "; b = "reads the label."
        wa = d.textlength(a, font=f2); wb = d.textlength(b, font=f2); x = (W - wa - wb) / 2; y = S(66)
        d.text((x, y), a, font=f2, fill=INK); d.text((x + wa, y), b, font=f2, fill=TEAL)
        self.cache["title"] = im; return im

    def tag(self, key, x, y, eyebrow, name, sub=None):
        if key in self.cache:
            return self.cache[key]
        S = self.S; im = layer((self.W, self.H)); d = ImageDraw.Draw(im)
        d.text((S(x), S(y)), eyebrow, font=font(S(11), "SemiBold"), fill=MUTED, spacing=0)
        d.text((S(x), S(y + 15)), name, font=font(S(19), "Bold"), fill=INK)
        if sub:
            nx = S(x) + d.textlength(name, font=font(S(19), "Bold")) + S(8)
            d.text((nx, S(y + 19)), sub, font=font(S(14), "Medium"), fill=SUB)
        self.cache[key] = im; return im

    def chip(self, text, col, cx, cy):
        key = ("chip", text, col)
        if key not in self.cache:
            S = self.S; im = layer((self.W, self.H)); d = ImageDraw.Draw(im)
            f = font(S(16), "SemiBold"); tw = d.textlength(text, font=f); px = S(18); h = S(38)
            x0 = S(cx); y0 = S(cy) - h / 2
            d.rounded_rectangle((x0, y0, x0 + tw + 2 * px, y0 + h), radius=h / 2, fill=(255, 255, 255, 245), outline=col, width=max(2, S(2)))
            d.ellipse((x0 + S(12), S(cy) - S(4), x0 + S(20), S(cy) + S(4)), fill=col)
            d.text((x0 + px + S(6), y0 + (h - S(16)) / 2 - S(2)), text, font=f, fill=col)
            sh = layer((self.W, self.H)); shadowed(sh, im, blur=S(8), off=S(3), op=0.18)
            self.cache[key] = sh
        return self.cache[key]

    def rulebook(self):
        if "rb" in self.cache:
            return self.cache["rb"]
        S = self.S; im = layer((self.W, self.H)); d = ImageDraw.Draw(im)
        x0, y0, w, h = S(34), S(150), S(250), S(84)
        d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=S(12), fill=(255, 255, 255, 250), outline=(124, 92, 240, 120), width=S(2))
        dx, dy = x0 + S(16), y0 + S(14)
        d.rounded_rectangle((dx, dy, dx + S(42), dy + S(56)), radius=S(6), fill=(124, 92, 240, 25), outline=(124, 92, 240, 120), width=S(2))
        for k, yy in enumerate((12, 22, 32, 42)):
            d.rounded_rectangle((dx + S(9), dy + S(yy), dx + S(9) + S(16 if k == 3 else 24), dy + S(yy) + S(4)), radius=S(2), fill=(124, 92, 240, 150))
        tx = dx + S(58)
        d.text((tx, dy + S(2)), "YOUR RULEBOOK", font=font(S(10), "SemiBold"), fill=MUTED)
        d.text((tx, dy + S(18)), "Naming · Descriptions", font=font(S(14), "SemiBold"), fill=PURPLE)
        d.text((tx, dy + S(36)), "Danger flags · Access", font=font(S(14), "SemiBold"), fill=PURPLE)
        sh = layer((self.W, self.H)); shadowed(sh, im, blur=S(10), off=S(4), op=0.16)
        self.cache["rb"] = sh; return sh

    def caption(self, text):
        key = ("cap", text)
        if key not in self.cache:
            S = self.S; im = layer((self.W, self.H)); d = ImageDraw.Draw(im)
            f = font(S(19), "Medium"); tw = d.textlength(text, font=f); px = S(20); h = S(40)
            x0 = (self.W - tw) / 2 - px; y0 = self.H - S(62)
            d.rounded_rectangle((x0, y0, x0 + tw + 2 * px, y0 + h), radius=h / 2, fill=(255, 255, 255, 215))
            d.text(((self.W - tw) / 2, y0 + (h - S(19)) / 2 - S(3)), text, font=f, fill=SUB)
            self.cache[key] = im
        return self.cache[key]

    def frame(self, base, t):
        im = base.convert("RGBA")
        def put(lay, a, dy=0):
            l2 = apply_alpha(lay, a, dy)
            if l2 is not None:
                im.alpha_composite(l2)
        intro = ease(seg(t, 0.3, 1.0))
        put(self.title(), intro, (1 - intro) * -self.S(10))
        put(self.tag("agent", 52, 652, "THE AI AGENT", "The chef"), ease(seg(t, 0.6, 1.2)))
        put(self.tag("server", 300, 124, "THE MCP SERVER", "The cupboard", "tools in front of your systems"), ease(seg(t, 0.8, 1.4)))
        CH = [(1.9, 3.5, "Reads “Look up a customer”", TEAL),
              (3.6, 5.8, "No label: guesses, tries again", AMBER),
              (5.9, 9.4, "Label says read. It deletes.", RED),
              (10.1, 11.9, "Checking every jar against your rulebook", PURPLE),
              (11.9, 14.0, "A person approves each fix", TEAL),
              (14.0, 99, "Every label checked", TEAL)]
        for a, b, txt, col in CH:
            if a - 0.05 <= t <= b + 0.05:
                put(self.chip(txt, col, 34, 292), window(t, a, b, 0.25, 0.2) if b < 99 else ease(seg(t, a, a + 0.3)))
        rb = ease(seg(t, 9.6, 10.2)); put(self.rulebook(), rb, (1 - rb) * self.S(12))
        put(self.caption("Missing, messy or swapped labels: wasted calls and real risk."), window(t, 7.4, 10.2, 0.4, 0.4))
        put(self.caption("Agent = the chef  ·  MCP server = the cupboard  ·  Tool description = the label"), ease(seg(t, 14.5, 15.1)))
        return im.convert("RGB")


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True)
    files = sorted(glob.glob(os.path.join(src, "*.png")))
    if len(sys.argv) > 3:
        want = set(int(x) for x in sys.argv[3:]); files = [f for f in files if int(re.findall(r"(\d+)\.png$", f)[0]) in want]
    ov = None
    for f in files:
        n = int(re.findall(r"(\d+)\.png$", f)[0]); base = Image.open(f)
        if ov is None or ov.W != base.width:
            ov = Overlay(base.width, base.height)
        ov.frame(base, (n - 1) / FPS).save(os.path.join(dst, os.path.basename(f)))
    print("composited", len(files))
