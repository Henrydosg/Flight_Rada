"""Package only verified local 8 MB firmware artifacts; never flashes hardware."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from validate_firmware import ROOT, validate_build

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir', type=Path, default=ROOT / 'build-baseline')
opts = parser.parse_args()
build = opts.build_dir.resolve()
report = validate_build(build)
destination = (ROOT / 'output/waveshare7-8mb').resolve()
assert destination.is_relative_to(ROOT.resolve())
destination.mkdir(parents=True, exist_ok=True)
packaged = set()


def copy_artifact(source, filename):
    target = (destination / filename).resolve()
    if not target.is_relative_to(destination):
        raise ValueError('Unsafe artifact path')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    packaged.add(target)


flash = json.loads((build / 'flasher_args.json').read_text())
files = {'flasher_args.json', 'flash_args', 'sdkconfig', 'project_description.json'}
files.update(flash['flash_files'].values())
for filename in sorted(files):
    source = (build / filename).resolve()
    if not source.is_relative_to(build):
        raise ValueError('Unsafe artifact path')
    copy_artifact(source, filename)
copy_artifact(ROOT / 'partitions-8mb.csv', 'partitions-8mb.csv')
copy_artifact(ROOT / 'LICENSE', 'LICENSE')
if (ROOT / 'ATTRIBUTIONS.md').exists():
    copy_artifact(ROOT / 'ATTRIBUTIONS.md', 'ATTRIBUTIONS.md')
copy_artifact(ROOT / 'docs/DEPLOYMENT_WINDOWS.md', 'DEPLOYMENT_WINDOWS.md')
if (ROOT / 'dependencies.lock').exists():
    copy_artifact(ROOT / 'dependencies.lock', 'dependencies.lock')

# Include the reviewable report, font notices and its supporting evidence.
# Do not recursively package the output tree: previous release manifests/logs
# could otherwise ship stale identities or introduce circular bundle hashes.
documents = ['IMPLEMENTATION_REPORT_VI.md', 'KNOWN_GOOD_HARDWARE.md',
             'BUILD_WINDOWS.md', 'DEPLOYMENT_WINDOWS.md', 'UI_DESIGN.md']
evidence = ['final.json', 'baseline.json', 'assets.json', 'fonts.json',
            'elf-memory.json', 'size.txt', 'offline-tests.log',
            'host-ui-build.log', 'ui-stress-smoke.log',
            'ui-fetch-failure-smoke.log', 'vscode-task-build.log',
            'app-image-info.log', 'bootloader-image-info.log',
            'reference-sha256-before.json', 'reference-sha256-after.json',
            'reference-git-status-after.txt', 'serial-port-inventory.json']
for filename in documents:
    source = ROOT / 'docs' / filename
    if source.exists():
        copy_artifact(source, 'docs/' + filename)
for filename in evidence:
    source = ROOT / 'docs/validation' / filename
    if source.exists():
        copy_artifact(source, 'docs/validation/' + filename)
for pattern in ('font-licenses/*.txt', 'ui/concept-*.png', 'ui/firmware-*.png'):
    for source in sorted((ROOT / 'docs').glob(pattern)):
        copy_artifact(source, 'docs/' + source.relative_to(ROOT / 'docs').as_posix())

(destination / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
(destination / 'README.txt').write_text(
    'FLIGHT_RADAR_BUILD_PASS_HARDWARE_TEST_REQUIRED\n'
    'Waveshare LCD-7 800x480 / ESP32-S3 / physical 8 MB / OPI 8 MB PSRAM.\n'
    'No upload, erase or serial monitor was run by this packaging tool.\n'
    'Read DEPLOYMENT_WINDOWS.md and verify a full 8 MB backup before manual deployment.\n'
    'Build and board notes: docs/BUILD_WINDOWS.md and docs/KNOWN_GOOD_HARDWARE.md.\n'
    'This bundle includes bootloader, table, OTA metadata, app and SPIFFS assets.\n')
packaged.update(destination / name for name in ('validation.json', 'README.txt'))
hashes = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(packaged)}
(destination / 'SHA256SUMS.txt').write_text(''.join(f'{h}  {name}\n' for name, h in hashes.items()))
packaged.add(destination / 'SHA256SUMS.txt')
archive = ROOT / 'output/flight-radar-waveshare7-8mb.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(packaged):
        bundle.write(path, path.relative_to(destination.parent))
release = {'status': 'FLIGHT_RADAR_BUILD_PASS_HARDWARE_TEST_REQUIRED',
           'build_dir': str(build), 'bundle': str(archive), 'bundle_bytes': archive.stat().st_size,
           'bundle_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': hashes}
(ROOT / 'docs/validation/release.json').write_text(json.dumps(release, indent=2) + '\n')
print(json.dumps({k: v for k, v in release.items() if k != 'files'}, indent=2))
