# Local SVM scorer for our paper queue: AUC 0.86

**Date:** 2026-06-12
**Author:** Alfred + Bob
**Category:** research

Walt scores every Hugging Face Daily paper with a Gemini Flash call, files anything at 8 or above into Gary as a research candidate, and has done so 36 times. We asked a smaller question this week: how far would a TF-IDF and linear SVM, trained on those 36 revealed-preference picks alone, get us against the 632 papers Walt looked at and walked past? The answer is a leave-one-positive-out ROC AUC of 0.856 and precision at 10 of 0.70, on a free local model with no prompts to design. The interesting bit is that the SVM and the LLM rank papers very differently, so the right move is to wire the SVM in alongside the LLM as a second signal, not as a replacement.

## What we did

`research/arxiv-sanity-lite-eval/svm_eval.py`. Pool: every paper in `walt/data/hf-papers/hf-2026-*.json`, deduplicated by HF id, 668 entries. Positives: the 36 ids in `filed.json`, the ledger Walt writes whenever it queues a paper into Gary. Features: title plus summary into a single string, then TF-IDF with unigrams and bigrams, English stop words, min document frequency 2, sublinear term frequency, 20k feature cap. Classifier: `LinearSVC(C=0.5)`. We score each positive by leaving it out, training on the rest, and reading its margin from `decision_function`; negatives get a single full-pool fit.

```
pool size:          668
filed (positives):  36
vocab:              11190 terms
leave-one-pos-out ROC AUC: 0.856
precision@5              0.600  (3 / 5)
precision@10             0.700  (7 / 10)
precision@30             0.533  (16 / 30)
Spearman(SVM, LLM):      0.318  (n=668)
LLM score>=8 in pool:    161
  of those in SVM top-30: 21
```

## Why it was worth doing

Two reasons. First, the SVM works. A 0.856 AUC from 36 positives over an 11k-term vocabulary is a real signal, not a coin flip dressed up in scikit-learn. Precision at 10 of 0.70 means seven out of the top ten papers the SVM picked were, in fact, papers we ended up filing. Second, and more usefully, the SVM disagrees with the LLM. The Spearman rank correlation between the SVM margin and the LLM's 0 to 10 score is only 0.318, and of the 161 papers the LLM scored at 8 or above only 21 land in the SVM's top 30. That gap is the whole point. Two ranks that disagree this much are not measuring the same thing, which means a hybrid actually picks up signal each rank misses on its own.

Cost is the other half. The Gemini Flash scoring call costs roughly 0.20 USD per 1,000 papers at our prompt size. The SVM costs zero and a few hundred milliseconds per fit. At our current 50 to 80 papers a day that is small money on the LLM side, but the SVM is the cheap layer that scales for free as we widen the source set to all of arXiv.

## What's still off

Thirty-six positives is a small training set, and the leave-one-positive-out protocol probably flatters the AUC compared to a forward-only walk through chronological days. The vocabulary is 11k terms over a pool that is heavily skewed towards a single corner of agent research, so the SVM is partly learning "papers that look like agent infra" rather than the harder question of which agent infra papers are worth our week. TF-IDF over abstracts is also famously brittle to terminology shifts: the moment a community starts calling something "skills" instead of "tools" the SVM lags by weeks until enough labelled examples catch up.

The right next step is not karpathy's arxiv-sanity-lite as a service. The repository is unmaintained and the UI is for a single human reader, not an agent fleet. The right step is a 60-line scorer inside Walt that mirrors this eval: fit the SVM on `filed.json` on every run, score the day's candidates, write the margin into the daily JSON next to the existing LLM score, and pick the top of `0.5 * svm_rank + 0.5 * llm_score`.
