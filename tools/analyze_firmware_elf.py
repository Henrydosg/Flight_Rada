"""Record static memory sections and prove the RGB ISR callbacks link to IRAM."""
import argparse
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir', type=Path, default=root / 'build-baseline')
parser.add_argument('--out', type=Path, default=root / 'docs/validation/elf-memory.json')
opts = parser.parse_args()
with (opts.build_dir / 'esp32flight.elf').open('rb') as stream:
    elf = ELFFile(stream)
    sections = {s.name: {'bytes': s['sh_size'], 'address': hex(s['sh_addr'])}
                for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']}
    callbacks = {}
    for symbol in elf.get_section_by_name('.symtab').iter_symbols():
        if symbol.name in ('rgb_lcd_on_vsync_event', 'lvgl_port_notify_rgb_vsync'):
            section = elf.get_section(symbol['st_shndx']).name
            callbacks[symbol.name] = {'section': section, 'address': hex(symbol['st_value']),
                                      'bytes': symbol['st_size']}
    if len(callbacks) != 2 or any('iram' not in c['section'] for c in callbacks.values()):
        raise RuntimeError(f'RGB ISR callback outside IRAM or missing: {callbacks}')
report = {'sections': sections, 'rgb_isr_callbacks': callbacks,
          'configured_rgb_framebuffers_bytes': 3 * 800 * 480 * 2,
          'configured_bounce_buffers_bytes': 2 * 10 * 800 * 2,
          'runtime_heap_psram_bandwidth': 'NOT TESTED; see device lcd-perf logs after manual deployment'}
opts.out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
