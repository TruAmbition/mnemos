#!/usr/bin/env python3
"""Regenerate Mnemos vector/native icons. Development only: requires Pillow.

Geometry lives here so SVG, PNG, ICO and ICNS share the same mark.
Prebuilt assets are committed; end users and desktop builds need no Pillow.
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = '#11172c'
BORDER = '#374161'
VIOLET = '#b49aff'
CYAN = '#4de1e8'
# M as two connected memory paths; the diamond is the shared context core.
PATH = [(26, 94), (26, 34), (64, 66), (102, 34), (102, 94)]
CORE = [(64, 77), (75, 88), (64, 99), (53, 88)]


def main():
    web = ROOT / 'web'
    brand = ROOT / 'assets/brand'; brand.mkdir(parents=True, exist_ok=True)
    points = ' '.join(f'{x},{y}' for x,y in PATH)
    diamond = ' '.join(f'{x},{y}' for x,y in CORE)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <title>Mnemos memory core</title>
  <rect x="2" y="2" width="124" height="124" rx="29" fill="{BACKGROUND}" stroke="{BORDER}" stroke-width="2"/>
  <polyline points="{points}" fill="none" stroke="{VIOLET}" stroke-width="10" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M64 66V81" stroke="{VIOLET}" stroke-width="6"/>
  <polygon points="{diamond}" fill="{CYAN}"/>
</svg>
'''
    (web/'mnemos-icon.svg').write_text(svg)
    scale = 16
    image = Image.new('RGBA', (128*scale,128*scale))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2*scale,2*scale,126*scale,126*scale),radius=29*scale,fill=BACKGROUND,outline=BORDER,width=2*scale)
    path=[(x*scale,y*scale) for x,y in PATH]
    draw.line(path,fill=VIOLET,width=10*scale,joint='curve')
    for x,y in PATH:
        draw.ellipse(((x-5)*scale,(y-5)*scale,(x+5)*scale,(y+5)*scale),fill=VIOLET)
    draw.line([(64*scale,66*scale),(64*scale,81*scale)],fill=VIOLET,width=6*scale)
    draw.polygon([(x*scale,y*scale) for x,y in CORE],fill=CYAN)
    image=image.resize((1024,1024),Image.Resampling.LANCZOS)
    image.save(web/'mnemos-icon.png')
    image.save(brand/'mnemos.icns',format='ICNS')
    image.save(brand/'mnemos.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print('Wrote SVG, PNG, macOS ICNS, and Windows ICO icons.')


if __name__ == '__main__':
    main()
