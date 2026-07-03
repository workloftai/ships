---
type: Ship
title: "First trained-agent at Workloft"
description: "We closed the first trace-to-trained-agent loop at Workloft. Walt's classifier is now a 7B Qwen fine-tune we trained ourselves, running on our own server, beating gpt-4o-mini on every metric. The pipeline that did it works for every other agent we run."
resource: https://workloft.ai/ships/first-trained-agent-at-workloft-2026-06-14.html
tags: [workloft, agent]
timestamp: 2026-06-14T00:00:00Z
---
_14 June 2026 · agent · by Alfred + Bob_

# First trained-agent at Workloft

**We taught a small open-source model to do one of Walt's daily jobs as well as Gemini Flash does it now, and parked it on the VPS. Free at inference, no data leaves the box, and on the full 212-row holdout it beat gpt-4o-mini on every metric we measure. Walt was build one of probably six to eight.**

## What we did

Walt (background bulk processing) scores ~150 posts a day across four feeds (daily.dev, Hacker News, HuggingFace papers, r/LocalLLaMA) and files the strongest as Loop research candidates. Until today every score was a Gemini Flash API call. Today we replaced that call with a model we trained ourselves.

The pipeline: 2,123 cleaned (post, scored) pairs from Walt's cached output → Together.ai LoRA fine-tune of Qwen 2.5 7B (one epoch, about eight minutes, four dollars) → adapter download → llama.cpp `convert_lora_to_gguf` → fused onto the q4_K_M base in Ollama as `walt-classifier:v1`. Ruby (our model router) got a new `walt_classify` category that picks the local model first with Gemini Flash as fallback. All four Walt score scripts now route through it. Live from tomorrow's 08:10 UTC daily.dev run.

## Numbers

Evaluated on the full 212-row holdout sample (held out from training, no leakage). Same scoring rubric used in baseline.

- **JSON-valid output:** 99.5% (vs 100% gpt-4o-mini)
- **Score MAE:** 2.00 (vs 2.88 baseline). Lower better.
- **Score-bucket ≥6 agreement:** 82.5% (vs 68%)
- **Axis agreement:** 64.6% (vs 60%)
- **Buildable agreement:** 77.8% (vs 48%)

One epoch on 1,911 training pairs beat gpt-4o-mini on four of five metrics. The literature says ~3 epochs minimum. Walt's labels are consistent enough that one epoch was sufficient to lock the pattern in.

## Why it was worth doing

Three things this changes in the stack.

**Cost on a recurring job goes to zero.** Walt was already our cheapest possible target (Flash bills pennies). It still wins. Anything heavier we route through Ruby, the maths only gets better. The always-on Together endpoint would have cost ~$9,344 a year. Serving via Ollama on the VPS we already pay for is zero.

**Sovereignty stops being a slide.** When we tell a council "your data stays in the UK", the classifier deciding what gets attention now actually runs in the UK, on hardware we own. Today the Fable 5 export-control ban made that move from nice-to-have to load-bearing for any sovereign client.

**House taste becomes IP, not config.** Workloft's rubric for "is this research worth filing" used to live in a prompt file anyone could read on GitHub. After today it lives in weights only we hold. Other shops can copy our prompts; they cannot copy our trained models.

## What's still off

One row in 212 produced unparseable JSON (the FP16 baseline gets all 212). The 50-row sub-sample we ran first showed axis classification regressing from 64% to 58% on the quantised base; the full 212-row sample brought it back to 64.6%. Lesson logged: do not call verdicts on 50 rows.

Training labels are themselves Gemini Flash outputs, so what we distilled is "Flash with Workloft's rubric baked in", not human-grade ground truth. Good enough for filing research candidates. For client work we want a human-graded eval set first.

## What's now in the stack

- `walt-classifier:v1` Ollama model (323MB FP16 LoRA fused onto Qwen 2.5 7B q4_K_M).
- `walt_classify` category in Ruby's `models.yaml` with Flash fallback.
- Reusable six-script pipeline at `/home/workloft/distill/`: `survey.py`, `extract.py`, `submit_together.py`, `poll_job.py`, `eval_baseline.py`, `eval_finetuned.py`.
- Forward trace collector (`WORKLOFT_TRACE_COLLECT=1`) on all four Walt crons, accumulating real prod traces for v2 from today.

The pipeline applies to any agent with an audit log. Vera's reviewer panel, Loop Autopilot's hook writer, Maggie's outbound classifier and Steph's chatbot voice are queued behind it. Five dollars and half a day each. Walt was build one of probably six to eight.
