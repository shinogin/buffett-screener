#!/usr/bin/env python3
"""ホーム画面用のアイコンPNGを生成する（Pillowのみ使用）。
   出力: icon-192.png / icon-512.png / icon-180.png / icon-512-maskable.png"""
from PIL import Image, ImageDraw

BG = "#153F45"
BARS = [0.34, 0.52, 0.72, 1.0]
COLORS = ["#2E7F86", "#4FA5A9", "#8FD6D8", "#E8C36A"]


def icon(size, maskable=False):
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    m = size * (0.22 if maskable else 0.14)
    w = size - 2 * m
    bw = w / (len(BARS) * 1.7)
    gap = (w - bw * len(BARS)) / (len(BARS) - 1)
    base = size - m
    for i, h in enumerate(BARS):
        x0 = m + i * (bw + gap)
        d.rounded_rectangle([x0, base - w * h * 0.78, x0 + bw, base],
                            radius=bw * 0.22, fill=COLORS[i])
    return img


if __name__ == "__main__":
    for s in (192, 512, 180):
        icon(s).save("icon-%d.png" % s)
    icon(512, True).save("icon-512-maskable.png")
    print("アイコンを生成しました")
