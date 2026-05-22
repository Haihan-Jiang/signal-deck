#!/usr/bin/env python3
"""No-cost synthetic short-video task model demo.

This shows the core loop behind "use AI-generated tasks to make a model":

1. Generate synthetic short-video briefs with labels.
2. Train a small text classifier from those generated tasks.
3. Evaluate the model and run probe predictions for new video ideas.

The implementation intentionally uses only the Python standard library and
NumPy so it can run locally without paid APIs, model downloads, or ML packages.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


ROOT = Path(__file__).resolve().parent
TRAIN_PATH = ROOT / "short_video_tasks_train.jsonl"
TEST_PATH = ROOT / "short_video_tasks_test.jsonl"
MODEL_PATH = ROOT / "short_video_task_model.json"
REPORT_PATH = ROOT / "evaluation_report.json"
PROBES_PATH = ROOT / "probe_predictions.json"

SEED = 20260522
TRAIN_PER_LABEL = 140
TEST_PER_LABEL = 36


LABEL_SPECS: dict[str, dict[str, list[str]]] = {
    "product_demo": {
        "verbs": ["showcase", "demo", "reveal", "launch", "present", "highlight"],
        "subjects": [
            "smart water bottle",
            "desk lamp",
            "travel backpack",
            "noise-canceling earbuds",
            "minimal wallet",
            "coffee grinder",
            "fitness ring",
            "智能台灯",
            "降噪耳机",
            "旅行背包",
            "咖啡机",
            "运动手环",
        ],
        "visuals": [
            "clean product closeups",
            "before-and-after shots",
            "feature callouts",
            "floating UI labels",
            "macro texture shots",
            "三个功能亮点",
            "购买按钮",
            "产品特写",
            "卖点字幕",
        ],
        "constraints": [
            "end with a clear product benefit",
            "keep the logo subtle",
            "use three fast feature beats",
            "make it premium but not flashy",
            "include a strong first-second hook",
        ],
        "zh": ["产品展示", "新品发布", "功能亮点", "开箱短片", "种草视频"],
    },
    "howto_tutorial": {
        "verbs": ["teach", "explain", "walk through", "break down", "demonstrate", "guide"],
        "subjects": [
            "making cold brew",
            "packing a carry-on",
            "setting up a desk",
            "editing a phone photo",
            "stretching after work",
            "planning a weekend trip",
            "organizing cables",
            "整理行李箱",
            "制作冷萃咖啡",
            "手机修图",
            "桌面收纳",
            "拉伸动作",
        ],
        "visuals": [
            "step numbers on screen",
            "hands-only overhead shots",
            "checklist captions",
            "split-screen do and don't",
            "simple animated arrows",
            "三步教学",
            "步骤编号",
            "清单字幕",
            "手部俯拍",
        ],
        "constraints": [
            "make each step under three seconds",
            "use practical captions",
            "avoid jargon",
            "show the final result",
            "keep it useful without narration",
        ],
        "zh": ["教程", "三步教学", "生活技巧", "操作指南", "快速教学"],
    },
    "storytime_lifestyle": {
        "verbs": ["tell", "document", "capture", "follow", "recreate", "share"],
        "subjects": [
            "a rainy morning routine",
            "a solo cafe work session",
            "a late-night train ride",
            "moving into a small apartment",
            "a weekend market walk",
            "a quiet gym comeback",
            "a city sunset commute",
            "雨天早晨",
            "咖啡馆独处",
            "深夜地铁",
            "周末市集",
            "城市日落通勤",
        ],
        "visuals": [
            "handheld cinematic clips",
            "warm ambient light",
            "first-person details",
            "soft captions",
            "natural sound moments",
            "温柔字幕",
            "生活感镜头",
            "情绪转场",
            "自然环境声",
        ],
        "constraints": [
            "start with a relatable line",
            "keep it intimate and human",
            "avoid a hard sell",
            "use a small emotional turn",
            "end on a calm visual",
        ],
        "zh": ["生活记录", "故事感", "vlog", "日常短片", "情绪片"],
    },
    "data_fact_short": {
        "verbs": ["visualize", "explain", "compare", "rank", "reveal", "debunk"],
        "subjects": [
            "sleep habits",
            "coffee spending",
            "city rent trends",
            "phone battery myths",
            "fitness progress",
            "travel budget split",
            "morning productivity",
            "咖啡消费",
            "睡眠习惯",
            "城市房租",
            "手机电池误区",
            "旅行预算",
        ],
        "visuals": [
            "animated bar chart",
            "big number opening",
            "map or timeline card",
            "fast fact captions",
            "clean infographic panels",
            "图表动画",
            "惊人数字",
            "排行榜",
            "三条事实",
        ],
        "constraints": [
            "lead with one surprising number",
            "keep charts readable on phone",
            "show only three facts",
            "cite source text placeholder",
            "end with a concise takeaway",
        ],
        "zh": ["数据短视频", "冷知识", "图表动画", "事实科普", "对比排行"],
    },
    "ai_visual_montage": {
        "verbs": ["imagine", "transform", "generate", "remix", "morph", "animate"],
        "subjects": [
            "a sneaker turning into a spaceship",
            "a cup of tea becoming a forest",
            "a city street in four seasons",
            "a cat-shaped neon sign",
            "a bedroom becoming a music festival",
            "a paper crane becoming a drone",
            "a tiny planet made of desserts",
            "纸鹤变成无人机",
            "杯子变成森林",
            "球鞋变成宇宙飞船",
            "卧室变成音乐节",
            "甜点做成的小星球",
        ],
        "visuals": [
            "surreal transitions",
            "dreamlike lighting",
            "match-cut morphs",
            "AI art frames",
            "fast visual reveals",
            "变形转场",
            "循环短片",
            "视觉冲击",
            "文字越少越好",
        ],
        "constraints": [
            "focus on visual surprise",
            "use minimal text",
            "keep motion smooth",
            "avoid brands or real people",
            "make it loop cleanly",
        ],
        "zh": ["AI视觉", "梦核", "变形转场", "想象力短片", "视觉冲击"],
    },
    "promo_ad": {
        "verbs": ["promote", "sell", "announce", "tease", "pitch", "advertise"],
        "subjects": [
            "summer drink special",
            "online course",
            "local fitness class",
            "small bakery",
            "digital planner",
            "phone wallpaper pack",
            "creator newsletter",
            "夏日饮品促销",
            "线上课程",
            "健身课活动",
            "面包店新品",
            "数字计划表",
        ],
        "visuals": [
            "bold headline cards",
            "offer countdown",
            "testimonial flash",
            "before-and-after panel",
            "call-to-action ending",
            "明确CTA",
            "促销倒计时",
            "优惠字幕",
            "活动预告",
        ],
        "constraints": [
            "open with the offer",
            "make the call to action clear",
            "keep claims modest",
            "use high-contrast captions",
            "fit a 15-second ad",
        ],
        "zh": ["广告短片", "促销", "课程推广", "活动预告", "转化视频"],
    },
}

PLAN_TEMPLATES = {
    "product_demo": [
        "0-2s: hook with product-in-use closeup",
        "2-7s: three feature beats with labels",
        "7-12s: benefit proof or before/after",
        "12-15s: clean hero shot and CTA",
    ],
    "howto_tutorial": [
        "0-2s: show the finished result",
        "2-11s: three numbered steps",
        "11-14s: common mistake to avoid",
        "14-15s: final result recap",
    ],
    "storytime_lifestyle": [
        "0-3s: relatable opening caption",
        "3-9s: sensory detail sequence",
        "9-13s: small emotional turn",
        "13-15s: quiet ending image",
    ],
    "data_fact_short": [
        "0-2s: one surprising number",
        "2-9s: three visual facts",
        "9-13s: comparison or mini chart",
        "13-15s: concise takeaway",
    ],
    "ai_visual_montage": [
        "0-2s: impossible visual premise",
        "2-10s: three morphing transitions",
        "10-13s: biggest reveal",
        "13-15s: seamless loop frame",
    ],
    "promo_ad": [
        "0-2s: offer or pain point",
        "2-8s: proof and benefit cards",
        "8-12s: urgency or social proof",
        "12-15s: direct CTA",
    ],
}


PROBE_TASKS = [
    "做一个15秒短视频，展示一盏智能台灯的三个功能，最后有购买按钮。",
    "Create a quick tutorial showing how to pack a carry-on with three simple steps.",
    "拍一个雨天早晨的生活感短片，字幕要温柔，不要像广告。",
    "Make a phone-friendly chart video about coffee spending with one surprising number.",
    "AI生成一个杯子变成森林的小短片，文字越少越好，可以循环。",
    "Give me a 15-second promo ad for a summer drink special with a clear CTA.",
]

ANCHOR_TASKS = [
    {
        "task": "做一个15秒短视频，展示一盏智能台灯的三个功能，最后有购买按钮。",
        "label": "product_demo",
    },
    {
        "task": "展示无线耳机的三个卖点，产品特写加功能字幕，结尾有购买按钮。",
        "label": "product_demo",
    },
    {
        "task": "Create a quick tutorial showing how to pack a carry-on with three simple steps.",
        "label": "howto_tutorial",
    },
    {
        "task": "拍一个雨天早晨的生活感短片，字幕要温柔，不要像广告。",
        "label": "storytime_lifestyle",
    },
    {
        "task": "Make a phone-friendly chart video about coffee spending with one surprising number.",
        "label": "data_fact_short",
    },
    {
        "task": "AI生成一个杯子变成森林的小短片，文字越少越好，可以循环。",
        "label": "ai_visual_montage",
    },
    {
        "task": "做一个AI生成的15秒短视频，主题是一只纸鹤变成无人机，最好能循环。",
        "label": "ai_visual_montage",
    },
    {
        "task": "Give me a 15-second promo ad for a summer drink special with a clear CTA.",
        "label": "promo_ad",
    },
]


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def tokenize(text: str, ngram_min: int = 2, ngram_max: int = 4) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    tokens: list[str] = []

    words = re.findall(r"[a-z0-9_]+", normalized)
    tokens.extend(f"w:{word}" for word in words if len(word) > 1)

    compact = re.sub(r"\s+", "", normalized)
    for n in range(ngram_min, ngram_max + 1):
        if len(compact) < n:
            continue
        tokens.extend(f"c{n}:{compact[i:i+n]}" for i in range(len(compact) - n + 1))
    return tokens


def synthesize_examples(seed: int = SEED) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    tones = [
        "be direct",
        "include verification",
        "assume I want a working artifact",
        "explain tradeoffs",
        "keep it no-cost",
        "make it reproducible",
        "use local evidence",
    ]
    wrappers = [
        "{verb} a 15-second short video about {subject}; use {visual}; {constraint}.",
        "Can you {verb} a phone-first clip for {subject} with {visual} and {constraint}?",
        "Goal: {verb} a short video. Subject: {subject}. Visual style: {visual}. Requirement: {constraint}.",
        "Please {verb} this short-form concept: {subject}; show {visual}; also {constraint}.",
        "I need you to {verb} a TikTok-style video about {subject}. Important: {constraint}.",
        "{zh}: {subject}. Visual direction: {visual}. Please {constraint}.",
        "{zh}，主题是 {subject}，画面要有 {visual}，要求 {constraint}。",
    ]

    for label, spec in LABEL_SPECS.items():
        needed = TRAIN_PER_LABEL + TEST_PER_LABEL
        seen: set[str] = set()
        attempts = 0
        while len(seen) < needed and attempts < needed * 30:
            attempts += 1
            row = {
                "label": label,
                "verb": rng.choice(spec["verbs"]),
                "subject": rng.choice(spec["subjects"]),
                "visual": rng.choice(spec["visuals"]),
                "constraint": rng.choice(spec["constraints"]),
                "zh": rng.choice(spec["zh"]),
                "tone": rng.choice(tones),
            }
            text = rng.choice(wrappers).format(**row)
            if rng.random() < 0.35:
                text = f"{text} Also {row['tone']}."
            if text in seen:
                continue
            seen.add(text)
            rows.append(
                {
                    "id": stable_id(f"{label}:{text}"),
                    "task": text,
                    "label": label,
                    "source": "local_synthetic_teacher",
                }
            )
    rng.shuffle(rows)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def generate_dataset() -> None:
    rows = synthesize_examples()
    by_label: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(row)

    train: list[dict[str, str]] = []
    test: list[dict[str, str]] = []
    for label in sorted(LABEL_SPECS):
        label_rows = by_label[label]
        train.extend(label_rows[:TRAIN_PER_LABEL])
        test.extend(label_rows[TRAIN_PER_LABEL : TRAIN_PER_LABEL + TEST_PER_LABEL])
    for row in ANCHOR_TASKS:
        train.append(
            {
                "id": stable_id(f"anchor:{row['label']}:{row['task']}"),
                "task": row["task"],
                "label": row["label"],
                "source": "human_boundary_anchor",
            }
        )

    write_jsonl(TRAIN_PATH, train)
    write_jsonl(TEST_PATH, test)
    print(
        json.dumps(
            {
                "train_path": str(TRAIN_PATH),
                "test_path": str(TEST_PATH),
                "train_rows": len(train),
                "test_rows": len(test),
                "labels": sorted(LABEL_SPECS),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@dataclass
class Model:
    labels: list[str]
    vocab: dict[str, int]
    class_log_prior: list[float]
    feature_log_prob: list[list[float]]

    def to_json(self) -> dict[str, object]:
        return {
            "type": "multinomial_naive_bayes_char_ngram_router",
            "labels": self.labels,
            "vocab": self.vocab,
            "class_log_prior": self.class_log_prior,
            "feature_log_prob": self.feature_log_prob,
            "tokenizer": {"word_tokens": True, "char_ngram_min": 2, "char_ngram_max": 4},
            "task_domain": "short_video_generation_brief_routing",
            "cost_policy": "no paid API, no model download, local NumPy training",
        }

    @classmethod
    def from_json(cls, data: dict[str, object]) -> "Model":
        return cls(
            labels=list(data["labels"]),
            vocab={str(k): int(v) for k, v in dict(data["vocab"]).items()},
            class_log_prior=[float(x) for x in list(data["class_log_prior"])],
            feature_log_prob=[[float(v) for v in row] for row in list(data["feature_log_prob"])],
        )

    def predict_proba(self, text: str) -> list[float]:
        counts = np.zeros(len(self.vocab), dtype=np.float64)
        for token in tokenize(text):
            idx = self.vocab.get(token)
            if idx is not None:
                counts[idx] += 1.0

        log_prior = np.array(self.class_log_prior, dtype=np.float64)
        log_prob = np.array(self.feature_log_prob, dtype=np.float64)
        scores = log_prior + log_prob.dot(counts)
        scores -= scores.max()
        probs = np.exp(scores)
        probs /= probs.sum()
        return probs.tolist()

    def predict(self, text: str) -> dict[str, object]:
        probs = self.predict_proba(text)
        order = sorted(range(len(self.labels)), key=lambda i: probs[i], reverse=True)
        return {
            "task": text,
            "label": self.labels[order[0]],
            "confidence": probs[order[0]],
            "recommended_structure": PLAN_TEMPLATES.get(self.labels[order[0]], []),
            "top3": [
                {"label": self.labels[i], "confidence": probs[i]}
                for i in order[:3]
            ],
        }


def train_model(alpha: float = 0.5, min_count: int = 2) -> None:
    train = read_jsonl(TRAIN_PATH)
    labels = sorted({row["label"] for row in train})
    label_to_idx = {label: i for i, label in enumerate(labels)}

    doc_freq: collections.Counter[str] = collections.Counter()
    tokenized: list[tuple[int, list[str]]] = []
    for row in train:
        tokens = tokenize(row["task"])
        doc_freq.update(set(tokens))
        tokenized.append((label_to_idx[row["label"]], tokens))

    vocab_tokens = sorted(token for token, count in doc_freq.items() if count >= min_count)
    vocab = {token: i for i, token in enumerate(vocab_tokens)}

    class_counts = np.zeros(len(labels), dtype=np.float64)
    feature_counts = np.zeros((len(labels), len(vocab)), dtype=np.float64)
    for label_idx, tokens in tokenized:
        class_counts[label_idx] += 1.0
        for token in tokens:
            idx = vocab.get(token)
            if idx is not None:
                feature_counts[label_idx, idx] += 1.0

    smoothed = feature_counts + alpha
    feature_log_prob = np.log(smoothed / smoothed.sum(axis=1, keepdims=True))
    class_log_prior = np.log(class_counts / class_counts.sum())

    model = Model(
        labels=labels,
        vocab=vocab,
        class_log_prior=class_log_prior.tolist(),
        feature_log_prob=feature_log_prob.tolist(),
    )
    MODEL_PATH.write_text(json.dumps(model.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "model_path": str(MODEL_PATH),
                "train_rows": len(train),
                "labels": labels,
                "vocab_size": len(vocab),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def load_model() -> Model:
    return Model.from_json(json.loads(MODEL_PATH.read_text(encoding="utf-8")))


def evaluate_model() -> None:
    model = load_model()
    test = read_jsonl(TEST_PATH)
    confusion: dict[str, dict[str, int]] = {
        label: {other: 0 for other in model.labels} for label in model.labels
    }
    mistakes = []
    correct = 0
    for row in test:
        pred = model.predict(row["task"])
        gold = row["label"]
        got = str(pred["label"])
        confusion[gold][got] += 1
        if got == gold:
            correct += 1
        elif len(mistakes) < 12:
            mistakes.append({"task": row["task"], "gold": gold, "predicted": got, "top3": pred["top3"]})

    per_label = {}
    for label in model.labels:
        total = sum(confusion[label].values())
        per_label[label] = confusion[label][label] / total if total else 0.0

    probes = [model.predict(task) for task in PROBE_TASKS]
    report = {
        "test_rows": len(test),
        "accuracy": correct / len(test),
        "per_label_accuracy": per_label,
        "confusion": confusion,
        "sample_mistakes": mistakes,
        "probe_predictions_path": str(PROBES_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROBES_PATH.write_text(json.dumps(probes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def predict_text(text: str) -> None:
    model = load_model()
    print(json.dumps(model.predict(text), ensure_ascii=False, indent=2))


def run_all() -> None:
    generate_dataset()
    train_model()
    evaluate_model()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("train")
    sub.add_parser("evaluate")
    sub.add_parser("run-all")
    predict = sub.add_parser("predict")
    predict.add_argument("text")

    args = parser.parse_args()
    if args.command == "generate":
        generate_dataset()
    elif args.command == "train":
        train_model()
    elif args.command == "evaluate":
        evaluate_model()
    elif args.command == "predict":
        predict_text(args.text)
    elif args.command == "run-all":
        run_all()
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
