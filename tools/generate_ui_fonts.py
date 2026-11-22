"""Generate small OFL Inter/IBM Plex Mono LVGL 8 subsets for the LCD-7 UI."""
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cache = root / ".cache/ui-font-sources"
out = root / "main/fonts"
licenses = root / "docs/font-licenses"
for directory in (cache, out, licenses):
    directory.mkdir(parents=True, exist_ok=True)
sources = {
    "Inter.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "IBMPlexMono-Medium.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-Medium.ttf",
    "Inter-OFL.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/OFL.txt",
    "Plex-OFL.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/OFL.txt",
}
for name, url in sources.items():
    path = licenses / name if name.endswith('.txt') else cache / name
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
env = os.environ.copy()
env['npm_config_cache'] = str(root / '.cache/npm')
for name, font, size in (("ui_inter_18", "Inter.ttf", 18),
                         ("ui_plex_20", "IBMPlexMono-Medium.ttf", 20),
                         ("ui_plex_26", "IBMPlexMono-Medium.ttf", 26)):
    subprocess.run(['npx.cmd', '--yes', 'lv_font_conv@1.5.3', '--bpp', '4', '--size', str(size),
                    '--font', (cache / font).relative_to(root).as_posix(), '-r', '0x20-0x7e,0xb0,0xb7,0x2014',
                    '--format', 'lvgl', '--no-compress', '-o', (out / (name + '.c')).relative_to(root).as_posix()],
                   env=env, cwd=root, check=True)
report = {'sources': sources, 'converter': 'lv_font_conv@1.5.3',
          'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir() if p.is_file()},
          'generated_source_bytes': {p.name: p.stat().st_size for p in out.glob('*.c')}}
(root / 'docs/validation/fonts.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
