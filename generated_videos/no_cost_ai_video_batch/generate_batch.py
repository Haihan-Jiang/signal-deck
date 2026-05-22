#!/usr/bin/env python3
"""Render ten no-cost short-video calls locally.

This is intentionally model-free at render time: no paid APIs, no remote model
calls, and no downloads. Each JSONL row in calls.jsonl is treated as one local
"call" and becomes one vertical MP4 plus a thumbnail.
"""

from __future__ import annotations

import json
import math
import textwrap
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
CALLS_PATH = ROOT / "calls.jsonl"
OUTPUT_DIR = ROOT / "outputs"
THUMB_DIR = ROOT / "thumbnails"
MANIFEST_PATH = ROOT / "manifest.json"
CONTACT_SHEET_PATH = ROOT / "contact_sheet.jpg"

WIDTH = 360
HEIGHT = 640
FPS = 15
DURATION_SECONDS = 6
FRAMES = FPS * DURATION_SECONDS

WHITE = (242, 246, 248)
MUTED = (158, 168, 170)
DARK = (12, 17, 18)

LABEL_THEMES = {
    "ai_visual_montage": {
        "accent": (120, 220, 255),
        "accent2": (220, 120, 255),
        "bg_top": (24, 18, 34),
        "bg_bottom": (7, 8, 18),
        "tag": "AI VISUAL LOOP",
    },
    "product_demo": {
        "accent": (105, 230, 180),
        "accent2": (255, 190, 90),
        "bg_top": (18, 28, 27),
        "bg_bottom": (7, 12, 13),
        "tag": "PRODUCT DEMO",
    },
    "howto_tutorial": {
        "accent": (255, 210, 90),
        "accent2": (105, 210, 255),
        "bg_top": (34, 28, 16),
        "bg_bottom": (13, 10, 5),
        "tag": "HOW-TO",
    },
    "storytime_lifestyle": {
        "accent": (165, 210, 255),
        "accent2": (255, 170, 190),
        "bg_top": (19, 27, 36),
        "bg_bottom": (8, 10, 15),
        "tag": "STORYTIME",
    },
    "data_fact_short": {
        "accent": (110, 230, 205),
        "accent2": (255, 150, 90),
        "bg_top": (16, 31, 30),
        "bg_bottom": (5, 10, 12),
        "tag": "DATA SHORT",
    },
    "promo_ad": {
        "accent": (120, 180, 255),
        "accent2": (255, 220, 80),
        "bg_top": (32, 20, 23),
        "bg_bottom": (12, 7, 9),
        "tag": "PROMO",
    },
}


def read_calls() -> list[dict[str, str]]:
    with CALLS_PATH.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if len(rows) != 10:
        raise ValueError(f"Expected exactly 10 calls, got {len(rows)}")
    return rows


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def put_text(
    frame: np.ndarray,
    text: str,
    xy: tuple[int, int],
    scale: float,
    color: tuple[int, int, int] = WHITE,
    thickness: int = 1,
) -> None:
    cv2.putText(frame, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def centered_text(
    frame: np.ndarray,
    text: str,
    y: int,
    scale: float,
    color: tuple[int, int, int] = WHITE,
    thickness: int = 1,
) -> None:
    (w, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    put_text(frame, text, ((WIDTH - w) // 2, y), scale, color, thickness)


def wrap_for_video(text: str, width: int = 23) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False)[:3]


def gradient_background(theme: dict[str, tuple[int, int, int] | str], t: float) -> np.ndarray:
    top = np.array(theme["bg_top"], dtype=np.float32)
    bottom = np.array(theme["bg_bottom"], dtype=np.float32)
    y = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None]
    bg = (top * (1 - y) + bottom * y).astype(np.uint8)
    frame = np.repeat(bg[:, None, :], WIDTH, axis=1)
    xs = np.linspace(-1, 1, WIDTH, dtype=np.float32)[None, :]
    ys = np.linspace(-1, 1, HEIGHT, dtype=np.float32)[:, None]
    field = np.sin(xs * 5.5 + t * 1.4) + np.cos(ys * 4.0 - t)
    glow = np.clip((field + 2) / 4, 0, 1)
    accent = np.array(theme["accent"], dtype=np.float32)
    tint = glow[..., None] * accent * 0.10
    return np.clip(frame.astype(np.float32) + tint, 0, 255).astype(np.uint8)


def add_header(frame: np.ndarray, call: dict[str, str], theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    cv2.rectangle(frame, (22, 28), (338, 88), (18, 24, 25), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (22, 28), (338, 88), accent, 1, cv2.LINE_AA)
    put_text(frame, str(theme["tag"]), (38, 63), 0.48, accent, 1)
    put_text(frame, call["style"].upper()[:24], (38, 82), 0.34, MUTED, 1)


def add_footer(frame: np.ndarray, idx: int, progress: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    x0, y0, x1 = 42, 594, 318
    cv2.rectangle(frame, (x0, y0), (x1, y0 + 7), (35, 42, 42), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x0, y0), (x0 + int((x1 - x0) * progress), y0 + 7), accent, -1, cv2.LINE_AA)
    centered_text(frame, f"LOCAL CALL {idx:02d}/10  |  NO API COST", 626, 0.34, MUTED, 1)


def draw_montage(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    accent2 = theme["accent2"]
    center = (WIDTH // 2, 326)
    morph = 0.5 + 0.5 * math.sin(t * 1.7)
    radius = int(54 + 18 * morph)
    angle = t * 2.5
    points = []
    for i in range(7):
        a = angle + i * math.tau / 7
        r = radius * (0.65 + 0.35 * ((i % 2) + morph) / 2)
        points.append((center[0] + int(math.cos(a) * r), center[1] + int(math.sin(a) * r)))
    cv2.polylines(frame, [np.array(points, dtype=np.int32)], True, accent, 2, cv2.LINE_AA)
    cv2.circle(frame, center, int(34 + 15 * (1 - morph)), accent2, 2, cv2.LINE_AA)
    for i, pt in enumerate(points):
        cv2.line(frame, center, pt, (60, 80, 92), 1, cv2.LINE_AA)
        cv2.circle(frame, pt, 4 + (i % 3), accent2 if i % 2 else accent, -1, cv2.LINE_AA)


def draw_product(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    accent2 = theme["accent2"]
    x, y, w, h = 124, 214, 112, 178
    bob = int(math.sin(t * 2.0) * 8)
    cv2.rectangle(frame, (x, y + bob), (x + w, y + h + bob), (28, 36, 36), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x, y + bob), (x + w, y + h + bob), accent, 2, cv2.LINE_AA)
    cv2.circle(frame, (x + w // 2, y + 44 + bob), 24, accent2, 2, cv2.LINE_AA)
    for i in range(3):
        yy = 442 + i * 34
        cv2.circle(frame, (74, yy), 10, accent, -1, cv2.LINE_AA)
        cv2.rectangle(frame, (96, yy - 7), (286, yy + 7), (35, 48, 46), -1, cv2.LINE_AA)


def draw_tutorial(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    for i in range(3):
        y = 238 + i * 86
        active = (int(t * 1.1) + i) % 3 == 0
        color = accent if active else (68, 72, 66)
        cv2.rectangle(frame, (55, y), (305, y + 54), (24, 28, 27), -1, cv2.LINE_AA)
        cv2.rectangle(frame, (55, y), (305, y + 54), color, 1, cv2.LINE_AA)
        cv2.circle(frame, (86, y + 27), 17, color, -1, cv2.LINE_AA)
        put_text(frame, str(i + 1), (80, y + 34), 0.45, DARK, 2)
        put_text(frame, ["HOOK", "STEP", "RESULT"][i], (124, y + 34), 0.52, WHITE, 1)


def draw_story(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    accent2 = theme["accent2"]
    for i in range(36):
        x = int((i * 29 + math.sin(t + i) * 8) % WIDTH)
        y = int((120 + i * 17 + t * 44) % 455)
        cv2.line(frame, (x, y), (x - 8, y + 24), (70, 98, 120), 1, cv2.LINE_AA)
    cv2.circle(frame, (180, 346), 72, (24, 32, 42), -1, cv2.LINE_AA)
    cv2.circle(frame, (180, 346), 72, accent, 1, cv2.LINE_AA)
    cv2.ellipse(frame, (180, 372), (86, 20), 0, 0, 360, accent2, 1, cv2.LINE_AA)


def draw_data(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    accent2 = theme["accent2"]
    cv2.rectangle(frame, (44, 212), (316, 430), (18, 26, 27), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (44, 212), (316, 430), accent, 1, cv2.LINE_AA)
    for i, base in enumerate([0.42, 0.7, 0.52, 0.84, 0.62]):
        h = int((base + 0.05 * math.sin(t * 2 + i)) * 140)
        x = 72 + i * 46
        cv2.rectangle(frame, (x, 398 - h), (x + 26, 398), accent if i != 3 else accent2, -1, cv2.LINE_AA)
    put_text(frame, "+38%", (128, 270), 1.1, accent2, 2)


def draw_promo(frame: np.ndarray, t: float, theme: dict[str, tuple[int, int, int] | str]) -> None:
    accent = theme["accent"]
    accent2 = theme["accent2"]
    pulse = ease((math.sin(t * 2.4) + 1) / 2)
    cv2.rectangle(frame, (48, 226), (312, 406), (27, 22, 24), -1, cv2.LINE_AA)
    cv2.rectangle(frame, (48, 226), (312, 406), accent, 2, cv2.LINE_AA)
    centered_text(frame, "LIMITED", 292, 0.86, accent2, 2)
    centered_text(frame, "DROP", 348, 1.24, WHITE, 2)
    cv2.rectangle(frame, (92, 450), (268, 496), accent, -1, cv2.LINE_AA)
    centered_text(frame, "CTA", 482, 0.76, DARK, 2)
    cv2.circle(frame, (282, 238), int(14 + 8 * pulse), accent2, 2, cv2.LINE_AA)


DRAWERS = {
    "ai_visual_montage": draw_montage,
    "product_demo": draw_product,
    "howto_tutorial": draw_tutorial,
    "storytime_lifestyle": draw_story,
    "data_fact_short": draw_data,
    "promo_ad": draw_promo,
}


def draw_frame(call: dict[str, str], idx: int, frame_no: int) -> np.ndarray:
    t = frame_no / FPS
    progress = frame_no / max(1, FRAMES - 1)
    theme = LABEL_THEMES[call["label"]]
    frame = gradient_background(theme, t + idx)

    for gx in range(-80, WIDTH + 80, 48):
        x = gx + int((t * 12 + idx * 7) % 48)
        cv2.line(frame, (x, 108), (x - 130, 560), (28, 38, 39), 1, cv2.LINE_AA)

    add_header(frame, call, theme)
    for line_idx, line in enumerate(wrap_for_video(call["headline"], 20)):
        centered_text(frame, line.upper(), 142 + line_idx * 34, 0.64, WHITE, 2)
    for line_idx, line in enumerate(wrap_for_video(call["hook"], 28)):
        centered_text(frame, line, 180 + line_idx * 23, 0.42, MUTED, 1)

    DRAWERS[call["label"]](frame, t + idx * 0.31, theme)

    # Fast caption card near the end.
    if progress > 0.68:
        fade = ease((progress - 0.68) / 0.22)
        overlay = frame.copy()
        cv2.rectangle(overlay, (34, 520), (326, 572), (16, 21, 22), -1, cv2.LINE_AA)
        cv2.rectangle(overlay, (34, 520), (326, 572), theme["accent2"], 1, cv2.LINE_AA)
        cv2.addWeighted(overlay, fade, frame, 1 - fade, 0, frame)
        centered_text(frame, "CALLABLE LOCAL SHORT", 553, 0.38, WHITE, 1)

    add_footer(frame, idx, progress, theme)
    return frame


def render_one(call: dict[str, str], idx: int) -> dict[str, object]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    THUMB_DIR.mkdir(exist_ok=True)
    video_path = OUTPUT_DIR / f"{idx:02d}_{call['id']}.mp4"
    thumb_path = THUMB_DIR / f"{idx:02d}_{call['id']}.jpg"

    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open writer for {video_path}")

    thumbnail = None
    for frame_no in range(FRAMES):
        frame = draw_frame(call, idx, frame_no)
        writer.write(frame)
        if frame_no == FRAMES // 2:
            thumbnail = frame.copy()
    writer.release()
    if thumbnail is None:
        raise RuntimeError(f"No thumbnail for {video_path}")
    cv2.imwrite(str(thumb_path), thumbnail)
    return {
        "index": idx,
        "id": call["id"],
        "brief": call["brief"],
        "label": call["label"],
        "headline": call["headline"],
        "video": str(video_path.relative_to(ROOT)),
        "thumbnail": str(thumb_path.relative_to(ROOT)),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "frames": FRAMES,
        "duration_seconds": DURATION_SECONDS,
    }


def write_contact_sheet(items: list[dict[str, object]]) -> None:
    thumbs = []
    for item in items:
        img = cv2.imread(str(ROOT / str(item["thumbnail"])))
        if img is None:
            continue
        img = cv2.resize(img, (180, 320), interpolation=cv2.INTER_AREA)
        thumbs.append(img)
    if len(thumbs) != 10:
        return
    rows = [np.hstack(thumbs[i : i + 5]) for i in range(0, 10, 5)]
    sheet = np.vstack(rows)
    cv2.imwrite(str(CONTACT_SHEET_PATH), sheet)


def main() -> None:
    calls = read_calls()
    outputs = []
    for idx, call in enumerate(calls, start=1):
        print(f"Rendering {idx:02d}/10: {call['id']}", flush=True)
        outputs.append(render_one(call, idx))
    write_contact_sheet(outputs)
    manifest = {
        "cost_policy": "no paid API, no remote model call, no downloads",
        "render_engine": "local Python + OpenCV + NumPy",
        "call_count": len(outputs),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "duration_seconds": DURATION_SECONDS,
        "outputs": outputs,
        "contact_sheet": CONTACT_SHEET_PATH.name,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
