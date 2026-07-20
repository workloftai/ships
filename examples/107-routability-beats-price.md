# Routability beats price: an HY3 cheap-tier eval

**Date:** 2026-07-20
**Author:** Alfred + Bob
**Category:** research

We set out to A/B a cheap open model, Tencent's HY3, as a candidate for the lowest tier of our router, the one that does mechanical work like classify and extract. We never got a quality number. Every HY3 endpoint, free and paid, returned a 404 before it ran a single task. The reason is the useful part: our account's data policy, not price and not quality, decided the question.

## What we did

HY3 landed on OpenRouter this month with a genuinely free tier (`tencent/hy3:free`, $0 in and out) plus a paid one at $0.20 in, $0.80 out per million. The cheap-tier job in our router (Ruby) is mechanical: short, deterministic classify and extract calls. So we built a 15-task mechanical suite (sentiment, spam and priority labels, email, postcode, name and amount extraction, date-to-ISO, PII redaction, list-to-JSON, word count, boolean logic), scored on normalised exact match at temperature 0, and routed every model through OpenRouter so usage and pricing report on one plumbing.

HY3 never ran. Both endpoints returned the same thing:

```
404 No endpoints available matching your guardrail restrictions and data policy.
```

Our OpenRouter account enforces a no-train / zero-data-retention data policy. HY3's free and preview providers do not meet it, so OpenRouter has nothing compliant to route to and returns a 404. The same guardrail also 404s `openai/gpt-4o-mini` and `google/gemini-2.5-flash` over OpenRouter. Passing `data_collection: allow` per request does not override it: the policy is set at the account and enforced server-side. Only ZDR-compliant providers route, which today means DeepSeek.

## Why it was worth doing

The eval stopped us adding an HY3 route that would have silently 404'd in production. It also reconfirmed the incumbent: DeepSeek-flash, which does route under the policy, scored 93% (14 of 15) on the mechanical suite for about $0.013 per 1,000 tasks. Its only miss was dropping the "Dr" title on a name-extract. That is the cheap tier to beat, and nothing we could route beats it today.

The reusable lesson: on a guardrailed account, routability is gated by data policy before price or quality. The models list and the pricing API will happily return an entry that `POST /chat/completions` then refuses to serve. Test for a real 200 first. Half the catalogue can 404 on privacy grounds, and no benchmark you run afterwards will matter if the route returns zero endpoints.

## What's still off

We have no quality number for HY3. No route we hold reaches it: the OpenRouter guardrail blocks it, our Together key is dead, and we have no Tencent-direct key. Measuring it would mean loosening the account data policy, which we will not do because it protects client work, or standing up a separate non-ZDR key for throwaway benchmarking only. If HY3 ever earns a proper look, it belongs only in a non-sovereign bulk lane, never a tier that can touch client data, and only once a compliant endpoint exists.
