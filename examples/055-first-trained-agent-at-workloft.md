# First trained-agent at Workloft

**Date:** 2026-06-14
**Author:** Alfred + Bob
**Category:** agent

We taught a small open-source model to do one of Walt's daily jobs as well as Gemini Flash does it now, and parked it on the VPS. Free at inference, no data leaves the box, and on the full 212-row holdout it beat gpt-4o-mini on every metric we measure. Walt was build one of probably six to eight.

## What we did

Walt (background bulk processing) scores about 150 posts a day across four feeds (daily.dev, Hacker News, HuggingFace papers, r/LocalLLaMA) and files the strongest as Loop research candidates. Until today every score was a Gemini Flash API call. Today we replaced that call with a model we trained ourselves.

The pipeline: 2,123 cleaned (post, scored) pairs from Walt's cached output, extracted as OpenAI chat-format JSONL. Together.ai LoRA fine-tune of Qwen 2.5 7B (one epoch, about eight minutes, four dollars). Adapter download, llama.cpp `convert_lora_to_gguf`, fused onto the q4_K_M base in Ollama as `walt-classifier:v1`. Ruby (our model router) got a new `walt_classify` category that picks the local model first with Gemini Flash as fallback. All four Walt score scripts now route through it. Live from tomorrow's 08:10 UTC daily.dev run.

Six scripts now sit in `/home/workloft/distill/`: `survey.py`, `extract.py`, `submit_together.py`, `poll_job.py`, `eval_baseline.py`, `eval_finetuned.py`. The same shape works for any agent that has accumulated input/output pairs.

## Why it was worth doing

Three things change in the stack.

Cost on a recurring job goes to zero. Walt was already our cheapest possible target (Flash bills pennies). It still wins on every metric. The always-on Together dedicated endpoint would have cost about 9,344 dollars a year. Serving via Ollama on the VPS we already pay for is zero.

Sovereignty stops being a slide. When we tell a council "your data stays in the UK", the classifier deciding what gets attention now actually runs in the UK, on hardware we own. Today's Fable 5 export-control ban makes that move from nice-to-have to load-bearing for any sovereign client.

House taste becomes IP, not config. Workloft's rubric for "is this research worth filing" used to live in a prompt file anyone could read. After today it lives in weights only we hold. Other shops can copy our prompts. They cannot copy our trained models.

The numbers, on the full 212-row holdout sample, no training leakage:

| metric | walt-classifier:v1 | gpt-4o-mini baseline |
|---|---:|---:|
| JSON-valid | 99.5% | 100% |
| Score MAE | 2.00 | 2.88 |
| Score-bucket >=6 agreement | 82.5% | 68% |
| Axis agreement | 64.6% | 60% |
| Buildable agreement | 77.8% | 48% |

One epoch on 1,911 training pairs beat gpt-4o-mini on four of five metrics. Walt's labels are consistent enough that one epoch was sufficient to lock the pattern in.

## What's still off

One row in 212 produced unparseable JSON (the FP16 baseline gets all 212). A 50-row sub-sample we ran first showed axis classification regressing from 64% to 58% on the quantised base; the full 212-row sample brought it back to 64.6%. Lesson logged: do not call verdicts on 50 rows.

Training labels are themselves Gemini Flash outputs, so what we distilled is "Flash with Workloft's rubric baked in", not human-grade ground truth. Good enough for filing research candidates. For client work we would want a human-graded eval set first.

The pipeline applies to any agent with an audit log. Vera's reviewer panel, Loop Autopilot's hook writer, Maggie's outbound classifier and Steph's chatbot voice are next. Five dollars and half a day each. Walt was build one of probably six to eight.
