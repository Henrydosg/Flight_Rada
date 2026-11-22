#!/usr/bin/env python3
"""Offline safety gate for the physical LCD-7 N8R8. Never opens a serial port."""
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

FLASH_BYTES = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    value = value.strip()
    multiplier = {"K": 1024, "M": 1024 * 1024}.get(value[-1:].upper(), 1)
    return int(value[:-1] if multiplier != 1 else value, 0) * multiplier


def read_partitions(path):
    rows = []
    for row in csv.reader(path.read_text(encoding="utf-8-sig").splitlines()):
        if not row or row[0].strip().startswith("#"):
            continue
        name, kind, subtype, offset, size = [v.strip() for v in row[:5]]
        require(offset and size, "Explicit partition offsets and sizes required")
        rows.append(dict(name=name, type=kind, subtype=subtype,
                         offset=number(offset), size=number(size)))
    validate_partitions(rows)
    return rows


def validate_partitions(rows):
    require(rows, "Empty partition table")
    end = 0x9000
    names = set()
    for p in sorted(rows, key=lambda p: p["offset"]):
        require(p["name"] not in names, "Duplicate partition name")
        names.add(p["name"])
        require(p["size"] > 0 and p["offset"] >= end, "Partition overlap or invalid size")
        require(p["offset"] % 0x1000 == 0, "Partition must be sector-aligned")
        if p["type"] == "app":
            require(p["offset"] % 0x10000 == 0, "App offset must be 64 KB aligned")
        end = p["offset"] + p["size"]
        require(end <= FLASH_BYTES, f'{p["name"]} exceeds physical 8 MB flash')
    by_name = {p["name"]: p for p in rows}
    for name in ("nvs", "phy_init", "otadata", "ota_0", "ota_1", "assets"):
        require(name in by_name, f"Missing {name}")
    require(by_name["nvs"]["offset"] == 0x9000 and by_name["nvs"]["size"] == 0x5000,
            "NVS boundary must match the 20 KiB reference partition; never auto-migrate pages")
    require(by_name["ota_0"]["size"] == by_name["ota_1"]["size"], "OTA slots must match")


def check_config(text):
    config = dict(line.split("=", 1) for line in text.splitlines()
                  if line.startswith("CONFIG_") and "=" in line)
    expected = {
        "CONFIG_IDF_TARGET": '"esp32s3"',
        "CONFIG_ESPTOOLPY_FLASHSIZE_8MB": "y",
        "CONFIG_ESPTOOLPY_FLASHSIZE": '"8MB"',
        "CONFIG_ESPTOOLPY_FLASHMODE_QIO": "y",
        "CONFIG_ESPTOOLPY_FLASHFREQ_80M": "y",
        "CONFIG_CANFLIGHT_BOARD_WAVESHARE_7": "y",
        "CONFIG_CANFLIGHT_WAVESHARE7_KNOWN_GOOD": "y",
        "CONFIG_SPIRAM": "y", "CONFIG_SPIRAM_MODE_OCT": "y",
        "CONFIG_SPIRAM_SPEED_80M": "y",
        "CONFIG_EXAMPLE_LVGL_PORT_ROTATION_180": "y",
        "CONFIG_PARTITION_TABLE_CUSTOM_FILENAME": '"partitions-8mb.csv"',
    }
    for key, value in expected.items():
        require(config.get(key) == value, f"Unsafe config: {key} must be {value}")
    require(config.get("CONFIG_ESPTOOLPY_FLASHSIZE_16MB") != "y", "16 MB forbidden")
    return config


def check_image(data, name):
    require(len(data) >= 24 and data[0] == 0xE9, f"Invalid ESP image: {name}")
    require(data[3] >> 4 == 3, f"{name}: image header must declare 8 MB")
    require(struct.unpack_from("<H", data, 12)[0] == 9, f"{name}: expected ESP32-S3 chip ID")
    return {"bytes": len(data), "flash_header_mb": 8,
            "chip_id": 9, "sha256": hashlib.sha256(data).hexdigest()}


def check_binary_table(data, rows):
    actual = []
    md5_found = False
    for offset in range(0, len(data), 32):
        entry = data[offset:offset + 32]
        if entry[:2] == b"\xeb\xeb":
            require(entry[16:32] == hashlib.md5(data[:offset]).digest(), "Partition MD5 mismatch")
            md5_found = True
            break
        if entry[:2] == b"\xff\xff":
            break
        require(len(entry) == 32, "Truncated partition entry")
        magic, kind, subtype, pos, size, label, flags = struct.unpack("<HBBII16sI", entry)
        require(magic == 0x50AA, "Invalid partition binary magic")
        actual.append((label.rstrip(b"\0").decode(), pos, size, kind, subtype))
    require(md5_found, "Missing partition MD5")
    kinds = {"app": 0, "data": 1}
    subtypes = {"nvs": 2, "phy": 1, "ota": 0, "ota_0": 16, "ota_1": 17, "spiffs": 0x82}
    expected = [(p["name"], p["offset"], p["size"], kinds[p["type"]],
                 subtypes[p["subtype"]]) for p in rows]
    require(actual == expected, "Generated partition binary differs from reviewed CSV")


def validate_build(build):
    asset_source = ROOT / "assets-8mb"
    if asset_source.exists():
        expected = set((asset_source / "manifest.txt").read_text(encoding="utf-8").splitlines()) | {"manifest.txt"}
        actual = {p.relative_to(asset_source).as_posix() for p in asset_source.rglob("*") if p.is_file()}
        require(actual == expected, f"Assets differ from manifest (runtime test files must not ship): {sorted(actual ^ expected)}")
    config = check_config((build / "sdkconfig").read_text(encoding="utf-8"))
    rows = read_partitions(ROOT / "partitions-8mb.csv")
    by_name = {p["name"]: p for p in rows}
    check_binary_table((build / "partition_table/partition-table.bin").read_bytes(), rows)
    app_data = (build / "esp32flight.bin").read_bytes()
    app = check_image(app_data, "application")
    require(len(app_data) >= 112 and app_data[32:36] == b"\x32\x54\xcd\xab", "Invalid app descriptor")
    require(b"\0" in app_data[48:80] and b"\0" in app_data[80:112], "Unterminated app identity")
    app_version = app_data[48:80].split(b"\0", 1)[0].decode("ascii")
    app_project = app_data[80:112].split(b"\0", 1)[0].decode("ascii")
    require(app_version.endswith("-w7-8mb-local") and app_project == "esp32flight", "Wrong binary board identity")
    app["version"] = app_version
    boot = check_image((build / "bootloader/bootloader.bin").read_bytes(), "bootloader")
    require(boot["bytes"] <= 0x8000, "Bootloader overlaps partition table")
    for slot in ("ota_0", "ota_1"):
        require(app["bytes"] <= by_name[slot]["size"], f"Firmware does not fit {slot}")
    description = json.loads((build / "project_description.json").read_text(encoding="utf-8"))
    require(description["project_version"].endswith("-w7-8mb-local"), "Wrong firmware identity")
    require(description["project_version"] == app_version, "Build metadata differs from binary descriptor")
    args = json.loads((build / "flasher_args.json").read_text(encoding="utf-8"))
    require(args["flash_settings"]["flash_size"] == "8MB", "Flasher args declare wrong size")
    ranges = []
    for address, filename in args["flash_files"].items():
        start = int(address, 0)
        data = (build / filename).read_bytes()
        require(start + len(data) <= FLASH_BYTES, f"Flash payload exceeds 8 MB: {filename}")
        ranges.append((start, start + len(data), filename))
        if filename.endswith("assets.bin"):
            require(start == by_name["assets"]["offset"] and len(data) <= by_name["assets"]["size"],
                    "Assets exceed reviewed partition")
    for a, b in zip(sorted(ranges), sorted(ranges)[1:]):
        require(a[1] <= b[0], f"Flash payloads overlap: {a[2]}, {b[2]}")
    return {"status": "PASS", "physical_flash_bytes": FLASH_BYTES,
            "application": app, "bootloader": boot, "partitions": rows,
            "ota_slot_bytes": by_name["ota_0"]["size"],
            "ota_headroom_bytes": by_name["ota_0"]["size"] - app["bytes"],
            "psram": "OPI 80 MHz configured; runtime capacity/heap not measured",
            "hardware_runtime": "NOT TESTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build-waveshare7")
    parser.add_argument("--json-out", type=Path)
    opts = parser.parse_args()
    try:
        report = validate_build(opts.build_dir.resolve())
        output = json.dumps(report, indent=2)
        print(output)
        if opts.json_out:
            opts.json_out.write_text(output + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
