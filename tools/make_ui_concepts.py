"""Code-native 800x480 design studies using the saved real ADS-B snapshot."""
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/ui"
OUT.mkdir(exist_ok=True)
snapshot = json.loads((ROOT / "docs/validation/adsb-lol-hcmc.json").read_text())
aircraft = sorted(snapshot.get("ac", []), key=lambda a: a.get("dst", 1e6))


class Canvas:
    def __init__(self):
        self.svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="480" viewBox="0 0 800 480">']
        self.im = Image.new("RGB", (1600, 960), "#07121f")
        self.draw = ImageDraw.Draw(self.im)

    def rect(self, x, y, w, h, fill, radius=0):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')
        self.draw.rounded_rectangle((x*2, y*2, (x+w)*2, (y+h)*2), radius=radius*2, fill=fill)

    def text(self, x, y, text, size=14, color="#deedf7", mono=False):
        family = "Consolas" if mono else "Arial"
        self.svg.append(f'<text x="{x}" y="{y+size}" font-family="{family},sans-serif" font-size="{size}" fill="{color}">{html.escape(text)}</text>')
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf" if mono else "C:/Windows/Fonts/arial.ttf", size*2)
        self.draw.text((x*2, y*2), text, font=font, fill=color)

    def line(self, x1, y1, x2, y2, color="#224256", width=1):
        self.svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="{width}" fill="none"/>')
        self.draw.line((x1*2, y1*2, x2*2, y2*2), fill=color, width=width*2)

    def ring(self, x, y, r, color="#224256"):
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}"/>')
        self.draw.ellipse(((x-r)*2, (y-r)*2, (x+r)*2, (y+r)*2), outline=color, width=2)

    def save(self, name):
        (OUT / f"{name}.svg").write_text("\n".join(self.svg + ["</svg>"]), encoding="utf-8")
        self.im.resize((800, 480), Image.Resampling.LANCZOS).save(OUT / f"{name}.png")


def radar(c, cx, cy, radius, labels=False, green=False):
    accent = "#56e398" if green else "#43d9e6"
    for step in range(1, 4):
        c.ring(cx, cy, radius*step/3)
    c.line(cx-radius, cy, cx+radius, cy)
    c.line(cx, cy-radius, cx, cy+radius)
    c.text(cx-5, cy-radius-22, "N", color=accent, mono=True)
    c.rect(cx-3, cy-3, 6, 6, accent, 3)
    for a in aircraft:
        if "lat" not in a or "lon" not in a:
            continue
        east = (a["lon"]-106.7009)*60*math.cos(math.radians(10.7769))
        north = (a["lat"]-10.7769)*60
        x, y = cx+east/50*radius, cy-north/50*radius
        if math.hypot(x-cx, y-cy) > radius:
            continue
        heading = math.radians(a.get("track", 0))
        c.line(x, y, x+math.sin(heading)*17, y-math.cos(heading)*17, accent, 2)
        c.ring(x, y, 3, accent)
        if labels:
            c.text(x+8, y-7, a.get("flight", a.get("hex", "")).strip(), 12, accent, True)
    c.text(cx-radius, cy+radius+13, "HCMC  /  50 NM  /  NORTH UP", 12, "#8da9bb", True)


def header(c, title):
    c.rect(0, 0, 800, 48, "#0e2031")
    c.text(16, 8, title, 19, "#43d9e6")
    c.text(16, 30, "800 x 480  /  DESIGN STUDY", 10, "#8da9bb", True)
    c.text(442, 14, f"SNAPSHOT  /  {len(aircraft)} AIRCRAFT", 13, "#8da9bb", True)
    c.rect(684, 2, 44, 44, "#173149", 8)
    c.text(691, 14, "VIEW", 11)
    c.rect(744, 2, 44, 44, "#173149", 8)
    c.text(754, 14, "SET", 11)


def detail(c, a, x, y):
    c.text(x, y, a.get("flight", a.get("hex", "")).strip(), 24, "#43d9e6", True)
    c.text(x, y+35, a.get("t", "TYPE UNKNOWN"), 14)
    alt = a.get("alt_baro", "--")
    c.text(x, y+68, f"{alt} FT", 22, mono=True)
    c.text(x, y+100, f'{a.get("gs", "--")} KT', 22, mono=True)


c = Canvas()
header(c, "A / MODERN AVIATION RADAR")
radar(c, 290, 248, 161)
c.rect(574, 68, 208, 358, "#0e2031", 12)
if aircraft:
    detail(c, aircraft[0], 590, 92)
c.text(590, 338, "REAL API SNAPSHOT", 11, "#8da9bb")
c.text(590, 360, "NO LIVE CONNECTION", 11, "#8da9bb")
c.save("concept-a")

c = Canvas()
header(c, "B / PROFESSIONAL ATC")
radar(c, 397, 251, 166, labels=True, green=True)
c.text(18, 70, "SECTOR VVTS", 16, "#56e398", True)
c.text(18, 96, "RANGE 50 NM", 13, "#8da9bb", True)
c.text(18, 438, "SNAPSHOT ONLY / SOURCE: ADSB.LOL / NOT FOR NAVIGATION", 11, "#8da9bb", True)
c.save("concept-b")

c = Canvas()
header(c, "FLIGHT RADAR / HCMC")
c.rect(0, 48, 310, 432, "#0b1928")
for i, label in enumerate(("DETAIL", "ROUTE", "RADAR", "STATS", "RETRO")):
    c.rect(8+i*59, 54, 55, 44, "#24616e" if i == 2 else "#173149", 7)
    c.text(13+i*59, 69, label, 10, "#deedf7")
for i, a in enumerate(aircraft[:5]):
    y = 108+i*68
    c.rect(8, y, 286, 62, "#173c50" if i == 0 else "#102438", 9)
    c.text(20, y+8, a.get("flight", a.get("hex", "")).strip(), 19, mono=True)
    c.text(228, y+12, a.get("t", "--"), 12, "#43d9e6", True)
    c.text(20, y+37, f'{a.get("alt_baro", "--")} FT  /  {a.get("gs", "--")} KT', 13, "#8da9bb", True)
radar(c, 551, 234, 149)
c.rect(326, 418, 458, 46, "#0e2031", 9)
c.text(340, 427, "REAL SNAPSHOT / ADSB.LOL", 13, "#43d9e6", True)
c.text(340, 447, "Design preview; firmware renders current data only", 11, "#8da9bb")
c.save("concept-c-selected")
print("Created three 800x480 SVG + PNG concepts in docs/ui")
