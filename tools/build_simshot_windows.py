"""Build the real LVGL UI headlessly using portable MinGW, no network IO."""
import concurrent.futures
import os
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "tools/simshot"
BUILD = ROOT / "build-host"
BUILD.mkdir(exist_ok=True)
GCC = ROOT / ".cache/host-compiler/mingw64/bin/gcc.exe"
LVGL = ROOT / "managed_components/lvgl__lvgl"
if not LVGL.exists():
    LVGL = ROOT / ".cache/lvgl-host"
APK = ROOT / "apkflight"
env = os.environ.copy()
env["PATH"] = str(GCC.parent) + os.pathsep + env["PATH"]
flags = ["-O1", "-g", "-std=gnu11", "-Wno-format", "-Wno-unused-function",
         "-ffunction-sections", "-fdata-sections", "-DLV_CONF_INCLUDE_SIMPLE",
         "-DLV_LVGL_H_INCLUDE_SIMPLE", "-DAPKFLIGHT_NO_WIFI", "-DAPKFLIGHT", "-DSIMSHOT",
         "-include", str(SIM / "windows_compat.h"), "-include", str(APK / "shim/path_remap.h")]
for folder in (SIM, APK, APK / "shim", APK / "vendor", ROOT / "main", LVGL, LVGL / "src", BUILD):
    flags += ["-I", str(folder)]
(BUILD / "apk_version.h").write_text('#define APK_VERSION "0.4.7-w7-8mb-local"\n')
headers = list((ROOT / 'main').glob('*.h')) + list((APK / 'shim').rglob('*.h')) + list(SIM.glob('*.h'))
signature = hashlib.sha256(repr(flags).encode() + b''.join(p.read_bytes() for p in sorted(headers))).hexdigest()
signature_path = BUILD / 'compile-signature.txt'
reuse = signature_path.exists() and signature_path.read_text() == signature
signature_path.write_text(signature)
exclude = {"main.c", "lvgl_port.c", "wifi_mgr.c", "mqtt_pub.c", "settings.c",
           "http_util.c", "web_server.c"}
sources = list((LVGL / "src").rglob("*.c"))
sources += [p for p in (ROOT / "main").glob("*.c") if p.name not in exclude and not p.name.endswith("_lcd_port.c")]
sources += list((ROOT / "main/fonts").glob("*.c"))
sources += [APK / "platform" / name for name in
            ("apk_settings.c", "paths.c", "settings_file.c", "shim_misc.c", "shim_rtos.c", "stubs.c")]
sources += [APK / "vendor/cJSON.c"]
sources += [SIM / name for name in ("sim_main.c", "headless_port.c", "http_stub.c", "sim_compat.c", "windows_stubs.c")]


def compile_one(source):
    stem = str(source.relative_to(ROOT)).replace("/", "_").replace("\\", "_").replace(".", "_")
    target = BUILD / (stem + ".o")
    if reuse and target.exists() and target.stat().st_mtime > source.stat().st_mtime:
        return target
    result = subprocess.run([str(GCC), *flags, "-c", str(source), "-o", str(target)], env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    return target


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    objects = list(pool.map(compile_one, sources))
response_file = BUILD / "link.rsp"
response_file.write_text("\n".join('"' + str(p).replace("\\", "/") + '"' for p in objects))
subprocess.run([str(GCC), "@" + str(response_file), "-Wl,--gc-sections", "-o", str(BUILD / "simshot.exe"),
                "-lpthread", "-lm"], env=env, check=True)
print(f"PASS: {len(sources)} real source files compiled; {BUILD / 'simshot.exe'}")
