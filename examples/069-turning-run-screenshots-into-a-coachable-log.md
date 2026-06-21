# Turning Run Screenshots Into a Coachable Log

**Date:** 2026-06-21
**Author:** Alfred + Bob
**Category:** agent

I wanted my agent to track my running without me typing anything. Now I send it the screenshots from my running app and it does the rest: reads the metrics off the image, writes them into a clean log, keeps the originals as proof, and answers questions about progress from the data rather than a guess. The one decision that makes it trustworthy is the split: the model does the seeing, a deterministic helper does the maths.

## What we did

Built a `/running` skill for Claude Code. Send it screenshots from a running app (Garmin, Strava, Apple Fitness, a watch) plus any notes, and it pulls every visible field into a strict 34-column schema: date, distance, duration, pace, average and max heart rate, cadence, elevation, calories and the rest. It normalises the units (miles to km, pace to min per km, time to hh:mm:ss), checks the run is not already in the log, and appends a row to a CSV. It copies the screenshots into an evidence folder and links them to the row, so the raw proof is never lost. Ask it a question, "am I getting faster", "this week versus last", and it answers from the log.

## Why it was worth doing

Because models are good at reading a screenshot and bad at arithmetic, and most "AI fitness coach" demos blur the two. We split them on purpose. The model extracts, which is vision and where it is strong. A small Python helper does the counting, the averages, the rolling windows and the dedupe, which is exactly where a model would quietly drift. So when it tells you your average pace this month, that number came from the file, not a vibe. The same split buys honesty for free: it never invents a value, it leaves a field blank and flags it for review when a metric is obscured, and it prefers the screenshot over a typed note when the two disagree. On the first real day it earned its place. Comparing two runs at the same pace, it surfaced that one cost far more heart rate, the kind of pattern that is plain in the data and invisible in the moment.

## What's still off

It reads what is on the screen, so a metric the app does not show is a metric we do not have, and a cropped or blurry screenshot becomes a blank, by design rather than a guess. How a run actually felt is not on any screenshot, so perceived effort still comes from a one-line note. And this is a single-user tool pointed at one person's log, not a product. The pattern is the point, not the running: messy input in, strict schema out, deterministic maths on top.
