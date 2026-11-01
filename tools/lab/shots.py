"""Frame statistics and contact sheets for run captures (frames stay outside git).

usage:
  python -I tools/lab/shots.py stats <png>...            size, colours, dominant colour and its share per frame
  python -I tools/lab/shots.py sheet <out.png> <png>...  frames side by side, half size, 2 per row, labelled
  python -I tools/lab/shots.py grid <out.png> <png>...   small thumbnails (1/6 size), 6 per row: a 30-frame record

Needs Pillow and numpy (<data>\\venv).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


def stats(path):
    a = np.asarray(Image.open(path).convert('RGB')).reshape(-1, 3)
    colours, counts = np.unique(a, axis=0, return_counts=True)
    top = counts.argmax()
    return (f'{os.path.basename(path)}: {Image.open(path).size}, {len(colours)} colours, dominant '
            f'#{"".join(f"{v:02x}" for v in colours[top])} {100 * counts[top] / len(a):.1f}%')


def sheet(out, paths, per_row=2, div=2):
    ims = [Image.open(p).convert('RGB') for p in paths]
    w, h = ims[0].size[0] // div, ims[0].size[1] // div
    rows = (len(ims) + per_row - 1) // per_row
    o = Image.new('RGB', (w * per_row, (h + 14) * rows), 'black')
    d = ImageDraw.Draw(o)
    for i, (im, p) in enumerate(zip(ims, paths)):
        x, y = (i % per_row) * w, (i // per_row) * (h + 14)
        o.paste(im.resize((w, h)), (x, y + 14))
        d.text((x + 2, y + 1), os.path.basename(p), fill='white')
    o.save(out)


if __name__ == '__main__':
    if sys.argv[1] == 'stats':
        for p in sys.argv[2:]:
            print(stats(p))
    elif sys.argv[1] == 'sheet':
        sheet(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == 'grid':
        sheet(sys.argv[2], sys.argv[3:], per_row=6, div=6)
