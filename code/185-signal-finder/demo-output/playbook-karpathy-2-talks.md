# Building and working with LLMs: a practical playbook

LLMs are a new kind of programmable computer. They are powerful but uneven: strong on common patterns and weak on novel work. They do not learn between sessions, and they are easily misled. The approach that works is to treat prompts and context as programs. Keep a human verifying output in a fast loop. Ship partial-autonomy products whose autonomy can rise over time. Judge progress by sustained reliability, not demos. Expect agents to mature over roughly a decade. Build products and documentation that are easy for both humans and models to check and use.

## Principles
- Prompts and context are programs. Be fluent in explicit code, trained networks and prompting, and choose the right one for each feature. _(S1 03:19, S1 05:45, S1 05:00)_
- Models generate and humans verify. Design everything to make this loop fast, because model intelligence is jagged and the human reviewer is the bottleneck. _(S1 16:19, S1 22:16, S1 20:13, S1 22:39 +2 more)_
- Build partial-autonomy products with an autonomy slider rather than flashy fully autonomous agents. Let people move up a layer of abstraction gradually and supervise the rest. _(S1 28:31, S1 20:48, S2 39:28, S2 1:11:25 +1 more)_
- A working demo is only the first nine of reliability. Each further nine takes similar effort, and where failure is costly the gap between demo and product is large. Expect agents to take about a decade. _(S1 27:31, S2 01:16, S2 1:44:54, S2 1:46:10 +3 more)_
- Calibrate to what models can actually do. They excel at boilerplate and patterns that are common online. They struggle with code that has never been written before. Sometimes the right answer is not to use AI. _(S2 31:44, S2 33:16, S2 35:58, S2 2:04:51 +2 more)_
- The context window is working memory and the weights are only a hazy recollection, so what you put in context matters more than what the model might remember. _(S1 17:06, S2 19:27, S2 19:49, S2 18:22)_
- Meet models halfway. Text-based domains with existing tooling, such as diffs, suit agents best, and other domains need that infrastructure built first. _(S1 37:40, S2 1:15:51, S2 1:16:24, S1 34:19 +1 more)_
- Stay the architect. Building and directing the work yourself exposes gaps in your understanding that delegating would hide. _(S2 29:55, S2 29:07, S2 34:07, S2 34:45)_

## Steps
1. Decide whether AI suits the problem at all. Favour short-horizon, digital, low-context tasks, and choose code, a trained model or prompting for each part. _(S2 2:02:04, S1 05:45, S2 1:11:11, S2 2:04:51)_
2. Load the relevant material directly into context, and build dedicated apps that manage context and orchestrate model calls instead of pasting into a chatbot. _(S2 19:49, S1 17:06, S1 19:23, S2 1:41:01)_
3. Write concrete prompts and work in small, verifiable increments rather than accepting large generated diffs. _(S1 24:43, S1 23:59, S1 23:00)_
4. Add auditable intermediate artefacts and visual interfaces, such as diffs with accept and reject, so humans can check output quickly. _(S1 25:26, S1 20:13, S1 22:39, S2 1:16:24)_
5. Ship with a low autonomy setting and raise it only as measured reliability improves, keeping humans supervising the remaining work. _(S1 20:48, S1 28:31, S2 1:11:25, S2 1:46:10)_
6. Harden for failure. Guard against prompt injection and data leaks, plan for provider outages and switching, and treat production code as high-stakes. _(S1 17:44, S1 07:42, S2 1:45:24)_
7. Make your product readable by models. Provide an llms.txt file and markdown documentation, and replace instructions to click with commands an agent can run. _(S1 34:19, S1 36:09, S1 37:40)_
8. Test beyond the demo. Use the product in real conditions, treat sudden near-perfect scores from an LLM judge as a red flag, and sample the same prompt repeatedly to detect collapsed outputs. _(S2 1:46:43, S2 47:49, S2 47:07, S2 49:17 +1 more)_

## Quotes (checked verbatim against the transcript)
> "usually they are doing the generation and we as humans are doing the verification. It is in our interest to make this loop go as fast as possible."  
> [S1 22:16](https://www.youtube.com/watch?v=LCEmiRjPEtQ&t=1336s)

> "it's not useful to me to get a diff of 10,000 lines of code to my repo. Like I have to I'm still the bottleneck, right?"  
> [S1 23:00](https://www.youtube.com/watch?v=LCEmiRjPEtQ&t=1380s)

> "It's less like building flashy demos of autonomous agents and more building partial autonomy products."  
> [S1 28:31](https://www.youtube.com/watch?v=LCEmiRjPEtQ&t=1711s)

> "if you give it the full chapter and ask it questions, you're going to get much better results because it's now loaded in the working memory of the model."  
> [S2 19:49](https://www.youtube.com/watch?v=lXUZvyajciY&t=1189s)

> "there's a very large demo-to-product gap where the demo is very easy, but the product is very hard."  
> [S2 1:44:54](https://www.youtube.com/watch?v=lXUZvyajciY&t=6294s)

> "When you get a demo and something works 90% of the time, that's just the first nine."  
> [S2 1:46:10](https://www.youtube.com/watch?v=lXUZvyajciY&t=6370s)

## Contradictions and tensions
- One source says LLMs can already click around interfaces, so making things easier for them is about cost and reliability. The other says current agents cannot really do computer use. _(S1 37:40 vs S2 02:13)_
- Karpathy argues compute is not being overbuilt because tools like coding agents are creating huge demand. Elsewhere he says it is strikingly hard to get economic value from these models outside coding. _(S2 1:56:09 vs S2 1:17:35)_

## Sources
- **S1** Andrej Karpathy: Software Is Changing (Again) (Y Combinator), 2025-06-17. https://www.youtube.com/watch?v=LCEmiRjPEtQ (captions via Supadata (en))
- **S2** Andrej Karpathy: “We’re summoning ghosts, not building animals” (Dwarkesh Patel), 2025-10-17. https://www.youtube.com/watch?v=lXUZvyajciY (captions via Supadata (en))

_106 ideas extracted. 106 quotes proposed by the model, 4 dropped because they were not in the source word for word. Transcripts are machine-made: check a quote against the recording before you repeat it._
