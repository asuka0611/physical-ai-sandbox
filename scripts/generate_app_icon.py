from __future__ import annotations

import math
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "assets" / "app-icon"
PNG_PATH = ICON_DIR / "AppIcon-1024.png"
ICNS_PATH = ICON_DIR / "PhysicalAISandbox.icns"


def _blend(
    dst: tuple[int, int, int, int],
    src: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    alpha = src[3] / 255.0
    inv = 1.0 - alpha
    return (
        int(src[0] * alpha + dst[0] * inv),
        int(src[1] * alpha + dst[1] * inv),
        int(src[2] * alpha + dst[2] * inv),
        255,
    )


def _draw_circle(
    pixels: list[list[tuple[int, int, int, int]]],
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    height = len(pixels)
    width = len(pixels[0])
    xmin = max(0, int(cx - radius - 1))
    xmax = min(width, int(cx + radius + 2))
    ymin = max(0, int(cy - radius - 1))
    ymax = min(height, int(cy + radius + 2))
    for y in range(ymin, ymax):
        for x in range(xmin, xmax):
            if math.hypot(x - cx, y - cy) <= radius:
                pixels[y][x] = _blend(pixels[y][x], color)


def _draw_line(
    pixels: list[list[tuple[int, int, int, int]]],
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    color: tuple[int, int, int, int],
) -> None:
    sx, sy = start
    ex, ey = end
    length = max(1, int(math.hypot(ex - sx, ey - sy)))
    for index in range(length + 1):
        t = index / length
        _draw_circle(pixels, sx + (ex - sx) * t, sy + (ey - sy) * t, width * 0.5, color)


def _write_png(path: Path, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b""),
    )


def generate_icon(size: int = 1024) -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    bg = (31, 36, 43, 255)
    pixels = [[bg for _ in range(size)] for _ in range(size)]
    shell = (235, 233, 220, 255)
    joint = (42, 46, 52, 255)
    blue = (38, 104, 235, 255)
    cube = (250, 124, 28, 255)

    # Subtle rounded field.
    _draw_circle(pixels, size * 0.50, size * 0.50, size * 0.46, (42, 48, 57, 255))
    _draw_circle(pixels, size * 0.50, size * 0.50, size * 0.42, bg)

    # Robot arm silhouette.
    base = (size * 0.28, size * 0.72)
    shoulder = (size * 0.38, size * 0.55)
    elbow = (size * 0.56, size * 0.43)
    wrist = (size * 0.70, size * 0.53)
    _draw_line(pixels, base, shoulder, size * 0.085, shell)
    _draw_line(pixels, shoulder, elbow, size * 0.078, shell)
    _draw_line(pixels, elbow, wrist, size * 0.068, shell)
    for point in [base, shoulder, elbow, wrist]:
        _draw_circle(pixels, *point, size * 0.062, joint)
        _draw_circle(pixels, *point, size * 0.034, blue)

    # Gripper.
    _draw_line(pixels, wrist, (size * 0.80, size * 0.48), size * 0.032, joint)
    _draw_line(pixels, (size * 0.80, size * 0.48), (size * 0.86, size * 0.42), size * 0.026, joint)
    _draw_line(pixels, (size * 0.80, size * 0.48), (size * 0.87, size * 0.54), size * 0.026, joint)

    # Cube.
    x0, y0, w = int(size * 0.66), int(size * 0.67), int(size * 0.16)
    for y in range(y0, y0 + w):
        for x in range(x0, x0 + w):
            pixels[y][x] = cube
    _draw_line(pixels, (x0, y0), (x0 + w, y0), size * 0.010, (255, 170, 70, 255))
    _draw_line(pixels, (x0, y0), (x0, y0 + w), size * 0.010, (255, 170, 70, 255))
    _write_png(PNG_PATH, pixels)


def build_icns() -> None:
    iconset = ICON_DIR / "PhysicalAISandbox.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        output = iconset / f"icon_{size}x{size}.png"
        subprocess.run(
            ["sips", "-z", str(size), str(size), str(PNG_PATH), "--out", str(output)],
            check=True,
        )
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS_PATH)], check=True)


def main() -> int:
    generate_icon()
    build_icns()
    print(ICNS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
