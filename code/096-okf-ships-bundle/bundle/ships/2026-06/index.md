# Ships — 2026-06

* [An agent on a box you own](agent-per-person-own-box.md) - We run two AI agents for two different people, each on its own server the owner controls, reachable from Telegram by text, screenshot or vo…
* [Burr Crash-Recoverable Agents](burr-crash-recoverable-agents.md) - We rebuilt Bob's Loop pipeline on Apache Burr, hard-killed it mid-run, and measured the recovery.
* [The Clean Repo That Runs You](clean-repo-that-runs-you.md) - Mozilla showed AI coding agents getting owned by clean GitHub repos that execute on a normal command.
* [The 120x Code Index, Measured](the-120x-code-index-measured.md) - A code-index MCP server claims 120x fewer tokens.
* [We Made 86 Ships Answer-Engine-Citable](we-made-86-ships-answer-engine-citable.md) - Answer engines quote sentences, not pages.
* [The Verifier Is the Environment](the-verifier-is-the-environment.md) - We reproduced the synthesis core of a new agent-environments survey.
* [Reproducing Agents' Last Exam: the full-pass collapse](agents-last-exam-repro.md) - We reproduced the core mechanism of Agents' Last Exam on a bounded suite of office tasks.
* [Voting Resamples, Distillation Teaches](prompt-level-distillation.md) - The sequel to our voting-harness test.
* [We gave our agent a memory that reorganises itself](self-maintaining-agent-memory.md) - We opened up our agent's long-term memory for a tidy-up and found a third of it was invisible.
* [The agent passed along five papers it never opened · Workloft Ships](cite-check.md) - Our agent handed over five arXiv IDs and admitted it had not checked them.
* [llama.cpp: the all-cores --threads trap](llama-cpp-threads-trap.md) - We benchmarked llama.cpp thread scaling on a shared 12-vCPU cloud box.
* [The job finished. Nobody woke the agent. · Workloft Ships](wake-on-completion.md) - Our agent kept promising to ping when a background job finished, then went silent.
* [Memory-rot watchdog: when 200 isn't saved](memory-rot-watchdog.md) - Our agent's long-term memory silently stored zero facts for two months while every health check stayed green.
* [Talk to Bob: a voice line to our agent](talk-to-bob-voice.md) - We built a two-way voice line to our agent in an afternoon.
* [An MCP Server Can Tell Your Agent to Read Your SSH Key](trust-no-mcp-server.md) - A remote MCP server's tool descriptions are read by your agent as instructions.
* [Sovereign Agents, Locked Down](agents-locked-down.md) - Prompt injection against coding agents is now exploited in the wild and it hits our exact stack.
* [HarnessX AEGIS Gate Reproduction](harnessx-aegis-gate-reproduction.md) - We reproduced the symbolic core of HarnessX (arXiv:2606.14249) in 470 lines of Python.
* [SelfCompact Reproduced](selfcompact-reproduced.md) - We reproduced the core mechanism of SelfCompact (arXiv:2606.23525): an agent that decides for itself when to compact its own context.
* [Our AI Judge Was Wrong 29% of the Time](we-audited-our-own-ai-judge.md) - We pointed a second model at our own three-model AI judge and found it was killing good work 29% of the time.
* [The Long-Context Recency Cliff](long-context-recency-cliff.md) - A controlled micro-eval: Gemini 2.5 Flash holds 100% on labelled needle retrieval to 436k tokens, but state-tracking falls off a cliff past…
* [Reproducing Claw Patrol's agent firewall](claw-patrol-repro.md) - Deno open-sourced Claw Patrol, a wire-level firewall for agents.
* [Organising My Hobbies With My Agent](organising-my-hobbies-with-my-agent.md) - I turned three hobbies into slash-commands my Claude Code agent runs: /running, /sourdough, /pizza.
* [Vera Standing: a nightly eval for every agent](vera-standing.md) - We had a good judge but no standing eval.
* [FORT-Searcher Reproduction](fort-searcher-reproduction.md) - We reproduced FORT-Searcher's shortcut-resistant task synthesis in 260 lines of dependency-free Python.
* [Adaptive Auto-Harness Reproduction](adaptive-auto-harness-reproduction.md) - We rebuilt a new paper's self-improving agent harness on a drifting task stream.
* [Pulling YouTube Transcripts Past the Block](pulling-youtube-transcripts-past-the-block.md) - YouTube's 2026 crackdown killed every free transcript route from our server.
* [Reviewer Back in the Loop](reviewer-back-in-the-loop.md) - We built the thing Research Note 38 promised: an independent reviewer put back into a self-improving agent harness loop.
* [Predictive Alignment Is Diagnostic Not Curative](predictive-alignment-diagnostic-not-curative.md) - We reproduced the World-In-Agent mechanism from Role-Agent (arXiv:2606.10917) at inference time.
* [Vera Disagreement Map](vera-disagreement-map.md) - Our model panel already votes ship-or-kill.
* [When the Harness Costs More Than the Model](when-the-harness-costs-more-than-the-model.md) - We stress-tested the claim that a voting harness makes a cheap model near-perfect.
* [Agent libOS: authority belongs at the primitive](agent-libos-authority-boundary.md) - We reproduced the core of Agent libOS (arXiv:2606.03895): an agent runtime where capability checks at the primitive, not the tool registry,…
* [Personalize-then-Store Repro](personalize-then-store-repro.md) - A CPU-runnable reproduction of the Personalize-then-Store memory paper.
* [The Generator in the Garage](the-generator-in-the-garage.md) - We built one command that revokes every cloud key mid-flight and proves our router keeps working on a local model.
* [After Fable 5: the UK builder's read](after-fable-5-uk-builders-read.md) - The US Commerce Department disabled Anthropic's Fable 5 and Mythos 5 worldwide on 13 Jun 2026.
* [First trained-agent at Workloft](first-trained-agent-at-workloft.md) - We closed the first trace-to-trained-agent loop at Workloft.
* [MiniMax Sparse Attention, reproduced](minimax-sparse-attention-reproduction.md) - We reproduced the two core claims of MiniMax Sparse Attention on a CPU.
* [The night Fable 5 went dark](fable-5-went-dark.md) - US Commerce export control disabled Anthropic's Claude Fable 5 and Mythos 5 on Friday.
* [SkillOpt prototype](skillopt-prototype.md) - We implemented the SkillOpt loop end to end on a small benchmark.
* [Enterprise Watch: a daily agent-platform market scan](enterprise-watch.md) - A public page that scans eight enterprise agent-platform newsrooms every morning, scores each item with a cheap model, and explains why it…
* [Local SVM scorer for our paper queue: AUC 0.86](local-svm-paper-scorer.md) - We trained an arxiv-sanity-lite style TF-IDF + linear SVM on the 36 papers Walt has filed to Gary, evaluated it against the rest of our 668…
* [The chat widget is now a real agent over the build log](chat-widget-real-agent.md) - The workloft.ai chat widget now grounds every answer in the published Ships + Labs corpus: 91 articles scored per question, top excerpts in…
* [Live AgentPass: fresh-signed credential on /verify](live-agentpass.md) - workloft.ai now issues a fresh AgentPass V0.1 credential on demand: a signed W3C Verifiable Credential with real standing data, verified en…
* [Mission Control: live fleet telemetry on the homepage](mission-control.md) - workloft.ai now shows the agent fleet working in real time: last ship, Labs picks, wall tags and seven agent heartbeats, fed by one cached…
* [Question-Mode Selection](question-mode-selection.md) - We A/B-tested a thesis-plus-counter-question prompt against a plain directive for picking the next loop item.
* [Say Hi! A graffiti wall for the Workloft homepage](say-hi-wall.md) - We gave workloft.ai a public graffiti wall.
* [codemap: a local code-symbol index for agents](codemap.md) - A pure-stdlib SQLite index of every function, class and type across our repos.
* [rebound: a tool-failure recovery harness](rebound.md) - A harness that replays real tool-failure events from our audit log and measures whether the fleet recovered.
* [skill-distiller: worked demonstrations into a reusable skill](skill-distiller.md) - A distiller that turns one or more worked demonstrations of a task into a structured SKILL.md draft.
* [slim: token-trim filter for agents](slim-token-filter.md) - A pluggable filter that strips verbose CLI output before it reaches the model.
* [sluice: an outbound egress guard](sluice.md) - A guard that scans every message an agent sends for leaked secrets and private identifiers, then blocks or redacts them.
* [Wiring r/LocalLLaMA into the Workloft Loop](localllama-loop.md) - We added r/LocalLLaMA as a fifth feed to the Workloft Loop.
* [Stealing Jon's browser hardening for Larry](stealing-jons-browser-hardening-for-larry.md) - A fellow builder, Jon, shared his hardened agent-browser setup.
* [Vera A/B Mode](vera-ab-mode.md) - A before/after harness for Vera.
* [Vera Reward Mode](vera-reward-mode.md) - An unsupervised reward for the Vera panel, read from each juror's next-token probabilities instead of a self-reported confidence number.
* [trojan-scan: catching backdoors in our own memory](trojan-scan.md) - We built trojan-scan, a scanner that defends our agent harness against ClawTrojan-style backdoors: a hidden instruction smuggled in through…
* [Agentic Social Posting Dedup](agentic-social-posting-dedup.md) - Our agent kept re-queuing posts we'd already published.
* [daily.dev wired into the Workloft Loop](daily-dev-loop.md) - We connected daily.dev's trending feed to the Workloft Loop.
* [Grok tested for code tier, didn't earn the slot](grok-code-tier.md) - We wired xAI's Grok into our model router and benchmarked it for the code tier.
* [Queued posts auto-clear from the to-do list](queued-posts-auto-clear.md) - Once a post is queued for review, the reminder to publish it now closes on its own.
* [AlphaXiv MCP Wire-In](alphaxiv-mcp-wire-in.md) - We wired the AlphaXiv MCP server into our agent so it searches, ranks and reads arXiv papers as native tools.
* [Layered SOP Enforcement: turning checklists into code](layered-sop-enforcement.md) - Our agent kept skipping documented steps.
* [Ruby learned routing: a bandit that stops overpaying](ruby-learned-routing.md) - We put an epsilon-greedy bandit on top of our model router.
* [Vera-escalate auto-tier in Ruby](vera-escalate-auto-tier.md) - Ruby now grades its own cheap answers with a three-juror panel and climbs the model tier ladder on its own when the answer is weak, instead…
