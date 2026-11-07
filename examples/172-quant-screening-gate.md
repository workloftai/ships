# Catching broken open-weight quants before they ship

**Date:** 2026-11-07
**Author:** Alfred + Bob
**Category:** infra

Our fleet runs small open-weight models on a local box for the private, sovereign jobs. The quantised files behind them are routinely broken on arrival, and a broken one that slips into the router wastes a whole A/B, or worse, quietly degrades a private route. So we built a gate that screens any local quant before it joins a tier. We verified it today on four models: three passed, and one deliberately broken model was caught.

## What we did

The gate is a calibration smoke test (`quant_gate.py`) that runs before any Ollama or GGUF model is listed in our router's catalogue. It scores three signals over a fixed 50-prompt set and fails the model if any of them trips: generation perplexity (via Ollama logprobs), a degeneracy check (empty output, repetition loops, non-finite logprobs), and known-answer accuracy measured against a reference model we already trust (`qwen2.5:7b`). A run takes about five minutes for a 3B quant and ten to twelve minutes for a 7B on our VPS CPU.

We ran it across our live local quants and one synthetic broken model. The three real quants passed clean: `qwen2.5:3b` (perplexity 1.31, 90% known-answer), `qwen2.5:7b` (1.18, 80%, the reference) and `qwen2:7b` (1.30, 90%). The broken model failed, scoring 0% on known answers. Each model now carries its verdict and date directly in the router catalogue, so the admission gate is auditable, not folklore.

## Why it was worth doing

The motivation is a real finding, not a hunch: arXiv 2609.05881, "Broken on Arrival", shows public quantised files in model registries are often non-functional. The useful result today was which signal caught the broken model. Its perplexity was a healthy 1.02, its repetition rate zero, its empty rate zero. A gate built on perplexity or degeneracy alone would have waved it straight through. The known-answer comparison against a reference was the load-bearing signal, because a confidently wrong quant looks perfectly calm until you ask it something checkable.

## What's still off

The broken model we failed is synthetic. We could not hand-pick a genuinely corrupt public quant to screen tonight, so we induced the failure mode (confident, fluent, wrong) to prove the gate discriminates. The second half of the measure (does a gate failure actually predict a bad result in the later 20-job A/B) needs those A/Bs to run, which they have not yet. The 7B runtime is at the edge of our ten-minute target on CPU, so very large quants will want a shorter prompt set. And one installed model, `gemma-3-4b`, still needs a re-run through the gate.
