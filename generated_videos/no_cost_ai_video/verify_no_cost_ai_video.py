#!/usr/bin/env python3
"""Verify the generated sample MP4 is readable and nonblank."""

from __future__ import annotations

import json
from pathlib import Path

import cv2


VIDEO = Path(__file__).resolve().parent / "no_cost_ai_video_sample.mp4"


def main() -> None:
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    meta = {
        "video": str(VIDEO),
        "opened": cap.isOpened(),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": fps,
        "frames": frame_count,
        "duration_seconds": frame_count / fps if fps else None,
        "sample_frame_stddev": [],
    }

    for idx in [0, frame_count // 2, max(0, frame_count - 1)]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        meta["sample_frame_stddev"].append(float(frame.std()) if ret else None)
    cap.release()

    meta["nonblank"] = all(v is not None and v > 5 for v in meta["sample_frame_stddev"])
    meta["pass"] = (
        meta["opened"]
        and meta["width"] == 1280
        and meta["height"] == 720
        and round(float(meta["fps"]), 2) == 24.0
        and meta["frames"] == 480
        and meta["nonblank"]
    )
    print(json.dumps(meta, indent=2))
    if not meta["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
