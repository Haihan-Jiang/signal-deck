#!/usr/bin/env python3
"""Verify all ten no-cost generated short videos."""

from __future__ import annotations

import json
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "manifest.json"


def inspect_video(path: Path) -> dict[str, object]:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    meta = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
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
    meta["nonblank"] = all(v is not None and v > 4 for v in meta["sample_frame_stddev"])
    meta["pass"] = (
        meta["exists"]
        and meta["opened"]
        and meta["width"] == 360
        and meta["height"] == 640
        and round(float(meta["fps"]), 2) == 15.0
        and meta["frames"] == 90
        and meta["nonblank"]
    )
    return meta


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    videos = [ROOT / item["video"] for item in manifest["outputs"]]
    report = {
        "manifest": str(MANIFEST_PATH),
        "call_count": manifest.get("call_count"),
        "video_count": len(videos),
        "videos": [inspect_video(path) for path in videos],
        "contact_sheet_exists": (ROOT / manifest["contact_sheet"]).exists(),
    }
    report["pass"] = (
        report["call_count"] == 10
        and report["video_count"] == 10
        and report["contact_sheet_exists"]
        and all(item["pass"] for item in report["videos"])
    )
    print(json.dumps(report, indent=2))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
