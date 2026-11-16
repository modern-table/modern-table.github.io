#!/usr/bin/env python3
"""Standardize a set's hand-cut pack wrappers (draft/packs/<set>/booster-N.webp).

    python3 tools/pack_wrappers.py <set> <template N> [--width 320]

Every wrapper of the set comes out the same pixel size with the same silhouette:
- the pack is found in each picture (largest opaque shape; stray specks and edge
  crumbs from the background removal are dropped) and cropped to it, so no
  picture carries a transparent margin that makes it look smaller in its slot;
- anything inside that crop that isn't pack (holes the background removal cut
  into the art, ragged edges) plus a thin band along the old edge (where white or
  grey background halos live) is filled from the neighbouring pack pixels;
- the crop is resized to the set's size: --width wide, as tall as the template's
  pack is in proportion;
- the template's outline (booster-<template N>, the cleanest cut), smoothed,
  mirrored to be symmetric and anti-aliased, becomes every wrapper's alpha.
Wizards' own cut-outs (FRA, FIN from the Pack images workflow) don't need this.
"""
import sys, glob, os, argparse
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as nd
import cv2

def clean_mask(a):
    m = a > 127
    m = nd.binary_opening(m, iterations=1)
    lab, n = nd.label(m)
    if n == 0:
        raise SystemExit('no opaque pixels')
    k = np.argmax(nd.sum(m, lab, range(1, n + 1))) + 1
    m = lab == k
    m = nd.binary_closing(m, iterations=2)
    return nd.binary_fill_holes(m)

def bbox(m):
    ys, xs = np.where(m)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

def silhouette(path, W, H):
    a = np.array(Image.open(path).convert('RGBA'))[:, :, 3]
    m = clean_mask(a)
    x0, y0, x1, y1 = bbox(m)
    m = m[y0:y1, x0:x1].astype(np.float32)
    S = 4  # supersample, smooth, threshold, average down: an even 1-px anti-aliased edge
    big = cv2.resize(m, (W * S, H * S), interpolation=cv2.INTER_LINEAR)
    big = (big + big[:, ::-1]) / 2
    big = cv2.GaussianBlur(big, (0, 0), S * 0.9)
    big = (big >= 0.5).astype(np.float32)
    small = cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA)
    return (small * 255 + 0.5).astype(np.uint8)

def content(path, W, H):
    im = np.array(Image.open(path).convert('RGBA'))
    a = im[:, :, 3]
    m = clean_mask(a)
    x0, y0, x1, y1 = bbox(m)
    rgb = np.ascontiguousarray(im[y0:y1, x0:x1, :3])
    good = (a[y0:y1, x0:x1] > 127) & m[y0:y1, x0:x1]
    # pixels within ~2 px of the old edge carry the old background's colour
    good = nd.binary_erosion(good, iterations=2, border_value=0)
    # and pale, colourless specks a little further in are leftover white/grey background
    near = nd.distance_transform_edt(m[y0:y1, x0:x1]) <= 7
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    pale = (hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 150)
    good &= ~(near & pale)
    unknown = (~good).astype(np.uint8) * 255
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    bgr = cv2.inpaint(bgr, unknown, 3, cv2.INPAINT_TELEA)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    up = W > rgb.shape[1]
    out = Image.fromarray(rgb).resize((W, H), Image.LANCZOS)
    if up:  # small sources: a light sharpen after enlarging
        out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('set')
    ap.add_argument('template', type=int)
    ap.add_argument('--width', type=int, default=320)
    o = ap.parse_args()
    d = os.path.join(os.path.dirname(__file__), '..', 'draft', 'packs', o.set)
    files = sorted(glob.glob(os.path.join(d, 'booster-*.webp')))
    tpl = os.path.join(d, 'booster-%d.webp' % o.template)
    ta = np.array(Image.open(tpl).convert('RGBA'))[:, :, 3]
    x0, y0, x1, y1 = bbox(clean_mask(ta))
    W = o.width
    H = round(W * (y1 - y0) / (x1 - x0))
    alpha = silhouette(tpl, W, H)
    outs = [(f, content(f, W, H)) for f in files]
    for f, rgb in outs:
        im = rgb.convert('RGBA')
        im.putalpha(Image.fromarray(alpha))
        im.save(f, 'WEBP', quality=90, method=6)
        print(os.path.basename(f), '->', im.size)

if __name__ == '__main__':
    main()
