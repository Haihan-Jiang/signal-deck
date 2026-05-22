#!/usr/bin/env python3
"""Generate a no-cost local AI-style video sample.

This intentionally avoids paid APIs and remote model calls. It uses only
OpenCV + NumPy to synthesize animated scenes, overlays, and captions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "no_cost_ai_video_sample.mp4"
MANIFEST = ROOT / "manifest.json"
STORYBOARD = ROOT / "storyboard.md"
SRT = ROOT / "no_cost_ai_video_sample.srt"

WIDTH = 1280
HEIGHT = 720
FPS = 24
DURATION_SECONDS = 20
TOTAL_FRAMES = FPS * DURATION_SECONDS

BG_TOP = np.array([18, 24, 28], dtype=np.float32)
BG_BOTTOM = np.array([5, 8, 12], dtype=np.float32)
TEAL = (180, 230, 205)
MINT = (90, 220, 170)
AMBER = (70, 190, 255)
CORAL = (96, 130, 255)
WHITE = (240, 246, 248)
MUTED = (150, 164, 168)

Y_GRAD = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None]
BASE_BG = np.repeat((BG_TOP * (1 - Y_GRAD) + BG_BOTTOM * Y_GRAD).astype(np.uint8)[:, None, :], WIDTH, axis=1)
XS = np.linspace(-1, 1, WIDTH, dtype=np.float32)[None, :]
YS = np.linspace(-1, 1, HEIGHT, dtype=np.float32)[:, None]
VIGNETTE_YY, VIGNETTE_XX = np.ogrid[:HEIGHT, :WIDTH]
VIGNETTE_DIST = np.sqrt(
    ((VIGNETTE_XX - WIDTH / 2) / WIDTH) ** 2 + ((VIGNETTE_YY - HEIGHT / 2) / HEIGHT) ** 2
)
VIGNETTE = np.clip(1.0 - VIGNETTE_DIST * 0.95, 0.55, 1.0).astype(np.float32)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def base_frame(t: float) -> np.ndarray:
    frame = BASE_BG.copy()
    field = (
        np.sin((XS * 4.5) + t * 0.95)
        + np.cos((YS * 3.2) - t * 0.7)
        + np.sin((XS + YS) * 3.0 + t * 0.4)
    )
    glow = np.clip((field + 3.0) / 6.0, 0, 1)
    tint = np.zeros_like(frame, dtype=np.float32)
    tint[:, :, 0] = 18 * glow
    tint[:, :, 1] = 35 * glow
    tint[:, :, 2] = 22 * glow
    frame = np.clip(frame.astype(np.float32) + tint, 0, 255).astype(np.uint8)
    return frame


def add_grid(frame: np.ndarray, t: float) -> None:
    spacing = 64
    offset = int((t * 18) % spacing)
    for x in range(-spacing + offset, WIDTH + spacing, spacing):
        cv2.line(frame, (x, 0), (x, HEIGHT), (24, 41, 42), 1, cv2.LINE_AA)
    for y in range(-spacing + offset, HEIGHT + spacing, spacing):
        cv2.line(frame, (0, y), (WIDTH, y), (24, 41, 42), 1, cv2.LINE_AA)


def put_text(
    frame: np.ndarray,
    text: str,
    xy: tuple[int, int],
    scale: float,
    color: tuple[int, int, int] = WHITE,
    thickness: int = 2,
) -> None:
    cv2.putText(
        frame,
        text,
        xy,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def centered_text(
    frame: np.ndarray,
    text: str,
    y: int,
    scale: float,
    color: tuple[int, int, int] = WHITE,
    thickness: int = 2,
) -> None:
    (w, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    put_text(frame, text, ((WIDTH - w) // 2, y), scale, color, thickness)


def pill(frame: np.ndarray, text: str, xy: tuple[int, int], color: tuple[int, int, int]) -> None:
    x, y = xy
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
    pad_x = 18
    pad_y = 13
    cv2.rectangle(
        frame,
        (x, y - th - pad_y),
        (x + tw + pad_x * 2, y + pad_y),
        (20, 31, 33),
        -1,
        cv2.LINE_AA,
    )
    cv2.rectangle(
        frame,
        (x, y - th - pad_y),
        (x + tw + pad_x * 2, y + pad_y),
        color,
        1,
        cv2.LINE_AA,
    )
    put_text(frame, text, (x + pad_x, y), 0.62, WHITE, 2)


def add_particles(frame: np.ndarray, t: float) -> None:
    rng = np.random.default_rng(14)
    for i in range(72):
        x0 = rng.uniform(0, WIDTH)
        y0 = rng.uniform(0, HEIGHT)
        x = int((x0 + math.sin(t * 0.7 + i) * 26) % WIDTH)
        y = int((y0 + math.cos(t * 0.4 + i * 0.3) * 18) % HEIGHT)
        pulse = 0.5 + 0.5 * math.sin(t * 1.5 + i)
        color = (
            int(90 + 40 * pulse),
            int(125 + 70 * pulse),
            int(115 + 80 * pulse),
        )
        cv2.circle(frame, (x, y), 1 + int(pulse > 0.72), color, -1, cv2.LINE_AA)


def add_neural_mesh(frame: np.ndarray, t: float, alpha: float = 1.0) -> None:
    nodes = []
    for row in range(4):
        for col in range(7):
            x = 210 + col * 140 + int(math.sin(t * 0.8 + row + col) * 18)
            y = 185 + row * 88 + int(math.cos(t * 0.7 + col) * 14)
            nodes.append((x, y))
    overlay = frame.copy()
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if j <= i:
                continue
            dist = math.hypot(a[0] - b[0], a[1] - b[1])
            if dist < 168:
                pulse = 0.5 + 0.5 * math.sin(t * 2.0 + i * 0.7 + j * 0.3)
                color = (45, int(92 + 70 * pulse), int(86 + 80 * pulse))
                cv2.line(overlay, a, b, color, 1, cv2.LINE_AA)
    for i, pt in enumerate(nodes):
        pulse = 0.5 + 0.5 * math.sin(t * 2.4 + i)
        cv2.circle(overlay, pt, int(4 + 3 * pulse), MINT, -1, cv2.LINE_AA)
        cv2.circle(overlay, pt, int(9 + 4 * pulse), (38, 96, 72), 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def add_data_panel(frame: np.ndarray, t: float, x: int, y: int, w: int, h: int) -> None:
    cv2.rectangle(frame, (x, y), (x + w, y + h), (16, 25, 27), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (65, 105, 96), 1, cv2.LINE_AA)
    put_text(frame, "MODEL-FREE LOCAL RENDER", (x + 24, y + 44), 0.68, MINT, 2)
    put_text(frame, "No API key | No paid credits | No stock footage", (x + 24, y + 82), 0.6, MUTED, 1)

    chart_x = x + 48
    chart_y = y + 132
    chart_w = w - 96
    chart_h = h - 190
    points = []
    for i in range(120):
        px = chart_x + int(i / 119 * chart_w)
        signal = (
            math.sin(i * 0.11 + t * 1.8)
            + 0.45 * math.cos(i * 0.26 - t * 0.9)
            + 0.18 * math.sin(i * 0.51)
        )
        py = chart_y + chart_h // 2 - int(signal * chart_h * 0.23)
        points.append((px, py))
    for gx in range(0, chart_w + 1, chart_w // 4):
        cv2.line(frame, (chart_x + gx, chart_y), (chart_x + gx, chart_y + chart_h), (30, 47, 48), 1)
    for gy in range(0, chart_h + 1, chart_h // 3):
        cv2.line(frame, (chart_x, chart_y + gy), (chart_x + chart_w, chart_y + gy), (30, 47, 48), 1)
    cv2.polylines(frame, [np.array(points, dtype=np.int32)], False, AMBER, 3, cv2.LINE_AA)
    cursor = points[int((0.5 + 0.5 * math.sin(t * 0.8)) * (len(points) - 1))]
    cv2.circle(frame, cursor, 8, CORAL, -1, cv2.LINE_AA)


def add_phone_mock(frame: np.ndarray, t: float) -> None:
    x, y, w, h = 820, 118, 260, 470
    cv2.rectangle(frame, (x, y), (x + w, y + h), (22, 29, 31), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 120, 110), 2, cv2.LINE_AA)
    cv2.rectangle(frame, (x + 24, y + 40), (x + w - 24, y + 98), (33, 55, 52), -1, cv2.LINE_AA)
    put_text(frame, "SHORT", (x + 42, y + 78), 0.82, WHITE, 2)
    for i in range(5):
        yy = y + 136 + i * 58
        length = int(128 + 58 * math.sin(t * 1.2 + i))
        cv2.rectangle(frame, (x + 34, yy), (x + 34 + length, yy + 18), (55, 88, 80), -1, cv2.LINE_AA)
        cv2.circle(frame, (x + w - 48, yy + 9), 12, (60, 118, 100), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x + 62, y + h - 64), (x + w - 62, y + h - 34), (68, 150, 116), -1, cv2.LINE_AA)


def add_scene_text(frame: np.ndarray, scene: dict[str, str], local_t: float) -> None:
    slide = int(lerp(-24, 0, ease(min(local_t, 1.0))))
    put_text(frame, scene["label"], (74, 116 + slide), 0.62, MINT, 2)
    put_text(frame, scene["title"], (72, 188 + slide), 1.45, WHITE, 3)
    put_text(frame, scene["line1"], (76, 246 + slide), 0.72, (204, 218, 216), 2)
    put_text(frame, scene["line2"], (76, 288 + slide), 0.72, (204, 218, 216), 2)


SCENES = [
    {
        "start": 0,
        "end": 4,
        "label": "SAMPLE 01",
        "title": "NO-COST AI VIDEO",
        "line1": "Created locally with generated motion graphics.",
        "line2": "No paid API, no account, no stock footage.",
    },
    {
        "start": 4,
        "end": 8,
        "label": "FORMAT",
        "title": "EXPLAINER / DEMO",
        "line1": "For product demos, workflow walkthroughs,",
        "line2": "and compact technical explainers.",
    },
    {
        "start": 8,
        "end": 12,
        "label": "FORMAT",
        "title": "DATA RECAP",
        "line1": "For trading reviews, KPI summaries,",
        "line2": "and chart-first research updates.",
    },
    {
        "start": 12,
        "end": 16,
        "label": "FORMAT",
        "title": "SOCIAL SHORT",
        "line1": "For short vertical ads, hook-driven reels,",
        "line2": "and launch teasers with captions.",
    },
    {
        "start": 16,
        "end": 20,
        "label": "NEXT STEP",
        "title": "SWAP IN MODEL CLIPS",
        "line1": "This scaffold can accept free/open-source",
        "line2": "model renders later if local hardware fits.",
    },
]


def active_scene(t: float) -> dict[str, str]:
    for scene in SCENES:
        if scene["start"] <= t < scene["end"]:
            return scene
    return SCENES[-1]


def draw_frame(frame_index: int) -> np.ndarray:
    t = frame_index / FPS
    frame = base_frame(t)
    add_grid(frame, t)
    add_particles(frame, t)

    scene = active_scene(t)
    local_t = t - float(scene["start"])
    progress = local_t / max(0.001, float(scene["end"] - scene["start"]))

    if t < 4:
        add_neural_mesh(frame, t, 0.9)
        centered_text(frame, "AUTOMATED VIDEO SAMPLE", 398, 0.86, MINT, 2)
        centered_text(frame, "FREE LOCAL PIPELINE", 462, 1.22, WHITE, 3)
        pill(frame, "OpenCV + NumPy", (458, 548), MINT)
        pill(frame, "No paid credits", (684, 548), AMBER)
    elif t < 8:
        add_neural_mesh(frame, t, 0.55)
        add_data_panel(frame, t, 704, 150, 460, 330)
        pill(frame, "Script", (705, 558), MINT)
        pill(frame, "Storyboard", (836, 558), AMBER)
        pill(frame, "MP4", (1018, 558), CORAL)
    elif t < 12:
        add_data_panel(frame, t, 640, 118, 520, 440)
        bars = [0.42, 0.65, 0.51, 0.74, 0.58]
        for i, val in enumerate(bars):
            x = 98 + i * 76
            h = int(210 * (val + 0.08 * math.sin(t * 2 + i)))
            cv2.rectangle(frame, (x, 575 - h), (x + 42, 575), (58, 146, 118), -1, cv2.LINE_AA)
            cv2.rectangle(frame, (x, 575 - h), (x + 42, 575), MINT, 1, cv2.LINE_AA)
    elif t < 16:
        add_phone_mock(frame, t)
        for i in range(3):
            x = 640 + int(45 * math.sin(t + i))
            y = 220 + i * 112
            cv2.rectangle(frame, (x, y), (x + 120, y + 66), (33, 55, 52), -1, cv2.LINE_AA)
            put_text(frame, f"HOOK {i+1}", (x + 18, y + 42), 0.58, WHITE, 2)
    else:
        add_neural_mesh(frame, t, 0.75)
        phase = ease(progress)
        cv2.rectangle(frame, (760, 176), (1120, 526), (16, 25, 27), -1, cv2.LINE_AA)
        cv2.rectangle(frame, (760, 176), (1120, 526), (65, 105, 96), 1, cv2.LINE_AA)
        put_text(frame, "OPTIONAL UPGRADE", (806, 236), 0.72, MINT, 2)
        put_text(frame, "Free model clips", (806, 304), 1.0, WHITE, 2)
        put_text(frame, "need disk + GPU", (806, 356), 0.74, MUTED, 2)
        cv2.rectangle(frame, (806, 414), (806 + int(230 * phase), 440), MINT, -1, cv2.LINE_AA)
        cv2.rectangle(frame, (806, 414), (1036, 440), (100, 160, 138), 1, cv2.LINE_AA)

    add_scene_text(frame, scene, local_t)

    # Gentle vignette.
    frame = np.clip(frame.astype(np.float32) * VIGNETTE[..., None], 0, 255).astype(np.uint8)
    return frame


def write_sidecars() -> None:
    storyboard = """# No-Cost AI-Style Video Sample

This video was generated locally with Python, OpenCV, and NumPy.

Cost policy:
- No paid API calls.
- No remote model calls.
- No stock footage.
- No downloaded assets were required for this first sample.

Deliverable:
- `no_cost_ai_video_sample.mp4`

Scene plan:
1. `0-4s`: No-cost AI video sample title.
2. `4-8s`: Explainer/demo format.
3. `8-12s`: Data recap format.
4. `12-16s`: Social short format.
5. `16-20s`: Optional upgrade path for free/open-source model clips.

Reusable prompt set for a future true video model:
1. Abstract local AI production pipeline, dark technical workspace, glowing node network, clean typography, cinematic motion.
2. Product explainer animation, floating data panels, generated interface elements, calm professional tone.
3. Trading/data recap animation, line charts and KPI bars, subtle motion, high readability.
4. Social short teaser, mobile-first layout, fast readable captions, generated graphic cards.
5. Open-source model upgrade path, local GPU render queue, progress bar, practical engineering mood.
"""
    STORYBOARD.write_text(storyboard, encoding="utf-8")

    srt = """1
00:00:00,000 --> 00:00:04,000
No-cost local AI-style video sample. No paid API or stock footage.

2
00:00:04,000 --> 00:00:08,000
Useful for product explainers, demos, and workflow walkthroughs.

3
00:00:08,000 --> 00:00:12,000
Useful for trading reviews, KPI summaries, and data recaps.

4
00:00:12,000 --> 00:00:16,000
Useful for social shorts, launch teasers, and caption-first clips.

5
00:00:16,000 --> 00:00:20,000
Future clips can be replaced by free local model renders if hardware fits.
"""
    SRT.write_text(srt, encoding="utf-8")

    manifest = {
        "output": OUT.name,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "duration_seconds": DURATION_SECONDS,
        "cost_policy": "no paid API, no remote model call, no stock footage",
        "tools": ["python3", "opencv", "numpy"],
        "downloaded_assets": [],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUT), fourcc, FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("Could not open OpenCV VideoWriter for MP4 output")

    for idx in range(TOTAL_FRAMES):
        if idx % FPS == 0:
            print(f"Rendering second {idx // FPS}/{DURATION_SECONDS}", flush=True)
        writer.write(draw_frame(idx))
    writer.release()
    write_sidecars()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
