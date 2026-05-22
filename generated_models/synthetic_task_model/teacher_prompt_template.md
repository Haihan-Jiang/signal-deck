# Teacher Prompt Template

Use this prompt with a local/free LLM when you want a real AI teacher to create
more labeled short-video training tasks.

```text
You are generating supervised training data for a short-video brief router.

Return JSONL only. Each line must be one object with:
- task: a realistic user request for a 15-30 second short video
- label: one of product_demo, howto_tutorial, storytime_lifestyle,
  data_fact_short, ai_visual_montage, promo_ad
- language: english, chinese, or mixed
- rationale: one short reason why the label fits

Label definitions:
- product_demo: feature-led product showcase, launch, unboxing, benefit demo
- howto_tutorial: steps, checklist, practical tutorial, recipe, setup guide
- storytime_lifestyle: vlog, daily life, emotional story, personal moment
- data_fact_short: chart, fact, comparison, ranking, myth, infographic
- ai_visual_montage: surreal AI transformation, morph, dreamlike loop
- promo_ad: offer, sale, event, course, newsletter, explicit CTA

Generate 60 diverse examples.
Balance labels evenly.
Include Chinese, English, and mixed-language requests.
Avoid real brands, real public figures, private data, medical/legal/financial claims,
and copyrighted character names.
Make boundary cases realistic.
```

Validation checklist:
- Every label appears the same number of times.
- The `task` is a video brief, not a meta request about training.
- Boundary examples are reviewed by a human before training.
- A held-out probe set is kept separate from generated training data.
