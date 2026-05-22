# No-Cost Batch Short Videos

This folder contains ten local short-video calls. Each call is one JSONL row in
`calls.jsonl`, and each row renders to one vertical MP4.

Cost policy:
- No paid API calls.
- No remote model calls.
- No model downloads.
- No stock footage.
- Local Python, OpenCV, and NumPy only.

Run:

```bash
python3 generated_videos/no_cost_ai_video_batch/generate_batch.py
```

Verify:

```bash
python3 generated_videos/no_cost_ai_video_batch/verify_batch.py
```

Outputs:
- `outputs/`: ten vertical MP4 files.
- `thumbnails/`: one preview frame per video.
- `contact_sheet.jpg`: 2x5 preview sheet.
- `manifest.json`: paths, dimensions, duration, and call metadata.

Current clip spec:
- 10 clips
- 360x640 vertical
- 15 fps
- 6 seconds each
- 90 frames per clip

This is the no-extra-fee route for quickly testing short-video concepts before
using any paid video generation model.
