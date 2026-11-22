"""Run production C logic and Flash regression tests on Windows."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
build = root / "build-host"
build.mkdir(exist_ok=True)
gcc = root / ".cache/host-compiler/mingw64/bin/gcc.exe"
env = os.environ.copy()
env["PATH"] = str(gcc.parent) + os.pathsep + env["PATH"]
subprocess.run([sys.executable, str(root / "tools/test_firmware_safety.py"), "-v"], check=True)
command = [str(gcc), "-O2", "-std=gnu11", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
           "-include", str(root / "tools/simshot/windows_compat.h"), "-I", str(root / "main"),
           "-I", str(root / "apkflight/shim"), "-I", str(root / "apkflight/vendor"),
           str(root / "tools/test_flight_data.c"), str(root / "main/flight_data.c"),
           str(root / "main/geo_math.c"), str(root / "apkflight/vendor/cJSON.c"),
           str(root / "tools/simshot/sim_compat.c"), str(root / "tools/simshot/http_stub.c"),
           "-lm", "-o", str(build / "logic_tests.exe")]
subprocess.run(command, env=env, check=True)
subprocess.run([str(build / "logic_tests.exe"), str(root / "docs/validation/adsb-lol-hcmc.json")], env=env, check=True)
subprocess.run([str(gcc), '-O2', '-std=gnu11', '-I', str(root / 'main'),
                str(root / 'tools/test_ota_guard.c'), '-o', str(build / 'ota_tests.exe')], env=env, check=True)
subprocess.run([str(build / 'ota_tests.exe'), str(root / 'build-baseline/esp32flight.bin')], env=env, check=True)
