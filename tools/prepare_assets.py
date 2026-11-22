#!/usr/bin/env python3
"""Prepare the 8 MB SPIFFS assets on Windows, without ImageMagick or shell tools.

Requires Pillow. Downloads only public data/assets; no API keys or aircraft
fixtures. Original committed font C files and aircraft sprites are reused.
"""
import concurrent.futures
import csv
import hashlib
import io
import json
import shutil
import urllib.request
import time
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache/asset-sources"
OUT = ROOT / "assets-8mb"
SOURCES = {
    "airports.csv": "https://davidmegginson.github.io/ourairports-data/airports.csv",
    "runways.csv": "https://davidmegginson.github.io/ourairports-data/runways.csv",
    "land.geojson": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson",
    "flag-codes.json": "https://flagcdn.com/en/codes.json",
}


def fetch(url, path):
    if path.exists() and path.stat().st_size:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ESP32FlightRadar-asset-builder/1.0"})
    print(f"fetch {url}", flush=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read()
            break
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1)
    path.write_bytes(data)
    return data


def png_asset(job):
    url, cached, target = job
    raw = fetch(url, cached)
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGBA").quantize(colors=64, method=Image.Quantize.FASTOCTREE)
        target.parent.mkdir(parents=True, exist_ok=True)
        im.save(target, optimize=True)


def prepare():
    for name, url in SOURCES.items():
        fetch(url, CACHE / name)
    OUT.mkdir(exist_ok=True)
    airports = list(csv.DictReader((CACHE / "airports.csv").open(encoding="utf-8-sig", newline="")))
    keep = {}
    with (OUT / "airports.tsv").open("w", encoding="utf-8", newline="\n") as out:
        for row in airports:
            icao = row["icao_code"] or row["ident"]
            if len(icao) != 4:
                continue
            if row["type"] in ("large_airport", "medium_airport") and row["scheduled_service"] == "yes":
                keep[row["ident"]] = icao
            if row["iata_code"] and row["type"] in ("large_airport", "medium_airport", "small_airport"):
                fields = [icao, row["iata_code"], row["municipality"], row["iso_country"],
                          row["latitude_deg"], row["longitude_deg"], row["name"]]
                out.write("\t".join(x.replace("\t", " ") for x in fields) + "\n")
    with (OUT / "runways.tsv").open("w", encoding="utf-8", newline="\n") as out:
        for row in csv.DictReader((CACHE / "runways.csv").open(encoding="utf-8-sig", newline="")):
            coords = [row["le_latitude_deg"], row["le_longitude_deg"],
                      row["he_latitude_deg"], row["he_longitude_deg"]]
            if row["airport_ident"] in keep and row["closed"] != "1" and all(coords):
                out.write("\t".join([keep[row["airport_ident"]]] + coords) + "\n")

    # Geographic fallback from real Natural Earth land polygons, not invented
    # tiles. The live local radar continues to use the upstream tile worker.
    land = json.loads((CACHE / "land.geojson").read_text())
    (OUT / "map").mkdir(exist_ok=True)
    for filename, width, height in (("world.png", 800, 400), ("world_small.png", 490, 245)):
        im = Image.new("RGB", (width, height), "#07121f")
        draw = ImageDraw.Draw(im)
        for feature in land["features"]:
            geom = feature["geometry"]
            polygons = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            for polygon in polygons:
                for index, ring in enumerate(polygon):
                    points = [((lon + 180) / 360 * (width - 1), (90 - lat) / 180 * (height - 1))
                              for lon, lat, *unused in ring]
                    draw.polygon(points, fill="#173149" if index == 0 else "#07121f")
        im.quantize(colors=64).save(OUT / "map" / filename, optimize=True)

    codes = json.loads((CACHE / "flag-codes.json").read_text())
    jobs = [(f"https://flagcdn.com/h20/{code}.png", CACHE / "flags" / f"{code}.png",
             OUT / "flags" / f"{code}.png") for code in codes if "-" not in code]
    index_path = ROOT / "assets/logos/index.txt"
    index = set(index_path.read_text().split())
    selected = set((ROOT / "tools/airlines_top.txt").read_text().splitlines()[:100])
    selected.update(("HVN", "VJC", "BAV", "PIC", "VAG", "VFC", "SIA", "AXM", "THA", "CPA"))
    jobs.extend((f"https://raw.githubusercontent.com/theqkash/esp32flight-logos/main/logos/{code}.png",
                 CACHE / "logos" / f"{code}.png", OUT / "logos" / f"{code}.png")
                for code in sorted(selected & index))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        # Any missing or corrupt required asset fails the preparation explicitly.
        list(executor.map(png_asset, jobs))
    (OUT / "logos").mkdir(exist_ok=True)
    shutil.copyfile(index_path, OUT / "logos/index.txt")
    files = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file() and p.name != "manifest.txt")
    (OUT / "manifest.txt").write_text("\n".join(files) + "\n", encoding="utf-8")
    report = {"sources": SOURCES, "fallback_map": "Natural Earth public-domain 1:110m land polygons",
              "logos": "https://github.com/theqkash/esp32flight-logos",
              "files": len(files), "total_file_bytes": sum((OUT / p).stat().st_size for p in files),
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in CACHE.iterdir() if p.is_file()}}
    (ROOT / "docs/validation/assets.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    prepare()
