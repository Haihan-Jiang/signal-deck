# Synthetic Short-Video Task Model

This is a local, no-cost demo for using generated tasks to make a small model.
The domain is generic short-video generation, not any existing project.

What it does:
- Generates synthetic short-video briefs.
- Labels each brief as one of six video formats.
- Trains a small text classifier with NumPy.
- Saves the trained model as JSON.
- Predicts the best short-video structure for new briefs.

Labels:
- `product_demo`: feature-led product showcase.
- `howto_tutorial`: steps, checklist, practical tutorial.
- `storytime_lifestyle`: vlog, mood, daily-life story.
- `data_fact_short`: chart/fact/ranking short.
- `ai_visual_montage`: surreal AI visual transformation or loop.
- `promo_ad`: offer-led short ad with CTA.

Files:
- `synthetic_task_model.py`: generator, trainer, evaluator, predictor.
- `short_video_tasks_train.jsonl`: generated training tasks.
- `short_video_tasks_test.jsonl`: generated test tasks.
- `short_video_task_model.json`: trained model.
- `evaluation_report.json`: test metrics and confusion matrix.
- `probe_predictions.json`: predictions for hand-written probes.
- `teacher_prompt_template.md`: prompt for using a local/free AI teacher later.

Run everything:

```bash
python3 generated_models/synthetic_task_model/synthetic_task_model.py run-all
```

Predict one brief:

```bash
python3 generated_models/synthetic_task_model/synthetic_task_model.py predict "AI生成一个杯子变成森林的小短片，文字越少越好，可以循环"
```

Current verified result:
- Training rows: 848
- Test rows: 216
- Test accuracy on generated holdout data: 1.0
- Caveat: this proves the model learned the generated-task distribution. It does
  not prove broad real-world short-video understanding.

How this maps to a real AI-generated-task workflow:
1. Use an AI teacher to generate many labeled short-video briefs.
2. Keep a small hand-labeled anchor set for boundary cases.
3. Train a cheap student model on those tasks.
4. Evaluate on held-out generated tasks plus human-written probes.
5. Use the student model to route new video briefs into a scene template.

This demo uses a local synthetic teacher instead of a paid model, so it has no
API cost and requires no downloaded resources.
