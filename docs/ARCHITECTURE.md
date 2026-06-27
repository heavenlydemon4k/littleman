# Littleman — Technical Architecture

> **Scope note.** Littleman is a general-purpose autonomous-agent platform; **Polymarket trading
> is the reference application, not the product** (see [META.md](META.md) and
> [ADR 0002](adr/0002-littleman-is-a-platform.md)). This document is the detailed system design
> and was written around that reference application, so its examples are trading-flavoured — read
> the trading specifics (risk governor, budget, positions) as belonging to *that application*.
> The meta/macro/task core, mental construct, heartbeat system, and runtime are domain-agnostic.
> For the platform-first overview, start with [META.md](META.md).

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Design Thesis](#2-design-thesis)
3. [Relationship to OpenClaw](#3-relationship-to-openclaw)
4. [LLM Provider Strategy](#4-llm-provider-strategy)
5. [System Overview](#5-system-overview)
6. [The Meta Layer](#6-the-meta-layer)
   - 6.1 World Model
   - 6.2 Situation Synthesizer
   - 6.3 Directive Engine
   - 6.4 Self-Scheduler
7. [The Macro Layer](#7-the-macro-layer)
   - 7.1 Goal Tree
   - 7.2 Strategy Planner
   - 7.3 Skill Registry
   - 7.4 Risk Governor
8. [The Task Layer](#8-the-task-layer)
9. [The Execution Layer](#9-the-execution-layer)
   - 9.1 Web Researcher
   - 9.2 Polymarket Client
   - 9.3 Knowledge Base
   - 9.4 Observation Logger
10. [The Heartbeat System](#10-the-heartbeat-system)
    - 10.1 Motivation
    - 10.2 Heartbeat Records
    - 10.3 The Scheduler Runtime
    - 10.4 Cascade Behavior
    - 10.5 Heartbeat Lifecycle
11. [The Domain Model](#11-the-domain-model)
    - 11.1 Polymarket Mechanics
    - 11.2 Topic Ontology
    - 11.3 Edge Theory
    - 11.4 Wallet and Budget Model
12. [The Planning Cycle](#12-the-planning-cycle)
13. [The Observation Loop](#13-the-observation-loop)
14. [Data Model](#14-data-model)
15. [Risk Management](#15-risk-management)
16. [Design Decisions and Tradeoffs](#16-design-decisions-and-tradeoffs)

---

## 1. Problem Statement

Many valuable domains are **ongoing, irregular, and research-intensive** — work that does not
arrive as discrete prompts but as a continuous stream where the hard part is deciding *what to do
right now*. The flagship reference application, Polymarket trading, is one such domain (scan
markets, research subjects, estimate probabilities, size positions, monitor, review on
resolution), but the same shape recurs in research pipelines, operations monitoring, content
operations, and personal-ops work.

In all of them a human operating manually must repeatedly answer: *what should I do right now?*
The sequence of decisions — what to research, when to research it, when to act, when to monitor,
when to re-evaluate — is itself a significant cognitive load, distinct from the object-level work.

Existing AI agents can execute individual tasks in this chain when a human provides the task.
What they do not do is generate the task themselves from an internal model of the situation. The
human's role is not only to approve or review — it is to maintain situational awareness across
time and decide what the next relevant action is. That work is not trivial and it is not
automated by tools that respond to prompts.

Littleman is a **platform** designed to eliminate the need for that ongoing human direction in
*any* such domain. The agent generates its own next action from its own model of the current
situation, plans its own schedule of future actions, and executes the full cycle without a human
specifying what to do between activations. The domain is supplied by an **application**
(`SOUL.md` + a skill pack + optional config); the platform machinery below is domain-agnostic.
Examples in this document are drawn from the Polymarket reference application — read the trading
specifics as belonging to *that application*, not the platform.

---

## 2. Design Thesis

The central claim of this architecture is:

**An autonomous agent requires a self-prompting capability — the ability to construct the input to its own reasoning process from stored state, not from a human-provided prompt.**

Most current agent architectures assume a human-in-the-loop who provides a prompt at the start of each session. That prompt encodes situational awareness the human built up between sessions: what happened, what matters now, what should be done. The agent then plans and executes from that prompt.

In this architecture, that pre-prompt cognitive work is a component of the system — the Directive Engine — that runs at the start of every session. It reads the world model (persisted state from prior sessions), synthesizes a situation report, and generates the directive that the rest of the session's planning and execution is based on.

This is not an LLM being asked open-ended questions about what to do. It is a structured process with defined inputs (world model fields) and a defined output format (a directive document that specifies current situation, immediate opportunities, outstanding tasks, and recommended focus). The LLM executes that process; the architecture defines what the process is.

The second claim is:

**An autonomous agent must plan its own activation schedule, not run on a fixed cadence.**

A fixed cron schedule (e.g., run every hour) is unsuitable because:

- It creates unnecessary runs when there is nothing to do (no positions to check, no markets closing soon)
- It fails to create runs when needed at irregular times (a market closing at 14:05 requires a run at approximately 14:10, not at 15:00)
- It does not encode intent — a 14:10 run should know it is there to check a specific position, not perform a full cycle from scratch

The heartbeat system replaces fixed scheduling with agent-authored scheduling. The agent creates heartbeat records during each session that specify when to run next, why, and with what context. The runtime executes heartbeats when their time arrives. The agent — not a human or a fixed clock — is the source of schedule entries.

---

## 3. Relationship to OpenClaw

Littleman's architecture is directly inspired by [OpenClaw](https://github.com/openclaw/openclaw), an open-source autonomous agent framework. Understanding the relationship — what we take, what we change, and what we discard — is important context for any contributor.

### What OpenClaw is

OpenClaw is a self-hosted, model-agnostic AI agent runtime. Its architecture is built around five concepts: a **Gateway** that routes messages from external channels, a **Brain** that runs an LLM in a ReAct (Reason + Act) loop, a **Memory** system backed by local Markdown files, a **Skills** system of modular callable capabilities, and a **Heartbeat** that runs the agent on a periodic schedule without user input.

OpenClaw's workspace is a directory of plain files the agent reads on every wake:

| File | Purpose |
|------|---------|
| `SOUL.md` | Agent identity, values, and persistent instructions — read on every wake |
| `HEARTBEAT.md` | Standing checklist of tasks to check on each periodic run |
| `MEMORY.md` | Persistent facts the agent has accumulated |
| `AGENTS.md` | Multi-agent coordination rules |
| `TOOLS.md` | Environment-specific capability configuration |

Its **Lane Queue** system serializes tasks per session to prevent race conditions, with configurable concurrency caps per lane type (main, subagent, cron). Its **provider abstraction** means the agent loop is identical regardless of whether the underlying model is a local Ollama instance or a cloud API — both look like OpenAI-compatible endpoints to the gateway.

### What Littleman adopts from OpenClaw

**Workspace-first configuration.** The agent's identity, mission, and embedded knowledge are defined in files that are read at the start of every session, not hardcoded in source. This makes the agent's behavior transparent and editable without touching code.

**SOUL.md pattern.** Littleman uses a `SOUL.md` file as its primary identity document. Where OpenClaw's `SOUL.md` defines persona and tone, Littleman's defines its domain mission (Polymarket trading), its embedded understanding of prediction markets, its risk philosophy, and its operating constraints. This is read at the start of every heartbeat session before any reasoning begins.

**Skills as discrete registered units.** OpenClaw skills are Markdown instruction files that describe a capability. Littleman's skill registry extends this into typed, callable Python functions with a parallel description layer that is included in the agent's context so it knows what it can do. The concept — modular, named, discoverable capabilities — is the same.

**Model-agnostic provider layer.** OpenClaw treats all LLM providers as interchangeable endpoints. Littleman does the same via LiteLLM (see [Section 4](#4-llm-provider-strategy)).

**ReAct agent loop.** The Reason + Act loop is the correct execution model for an agent that must decide between available skills and re-evaluate after each action. Littleman uses this loop within the task execution phase.

**Memory as layered storage.** OpenClaw uses Markdown files for memory with an FTS index. Littleman uses SQLite as its primary persistence layer with a similar two-tier pattern: structured tables for operational state (positions, heartbeats, world model) and a full-text-searchable knowledge base for accumulated research.

### Where Littleman diverges from OpenClaw

**The heartbeat is dynamic, not static.**

This is the most significant architectural departure. OpenClaw's `HEARTBEAT.md` is a human-authored static checklist. The agent reads it every 30 minutes and executes whatever tasks are listed. The schedule is fixed; the content is fixed; the human wrote it.

In Littleman, the agent writes its own heartbeat records. `HEARTBEAT.md` exists as a schema reference and default fallback, but the live schedule lives in the database as rows the agent creates, modifies, and cancels. Each heartbeat record carries the specific context that triggered it. The timing is derived from market close times and research windows, not a fixed interval. This is the core innovation over OpenClaw's pattern.

**The heartbeat carries intent and context.**

OpenClaw's heartbeat prompt is the same every run: "read HEARTBEAT.md, do what it says." Littleman's heartbeat fires with a `context` blob specifying exactly why this particular run exists — which positions to check, which markets to research, what information was expected. The agent does not re-derive its purpose from scratch; it is handed its purpose by the prior session that scheduled this wake.

**Domain specificity over generality.**

OpenClaw is general-purpose. Its `SOUL.md` can define any persona for any task. Littleman is purpose-built for a single domain: prediction market trading. Its domain knowledge (market mechanics, topic ontology, edge theory, calibration) is embedded in `SOUL.md` and the system prompt, not discovered at runtime. This depth is a deliberate tradeoff of generality for reliability in a specific domain.

**Explicit financial risk layer.**

OpenClaw has no concept of financial constraints. Littleman has a Risk Governor with hard limits that have veto power over all execution, circuit breakers for drawdown events, and position sizing derived from Kelly criterion. These are not prompt-level instructions; they are code-level enforcement.

**Goal tree persistence across sessions.**

OpenClaw's memory is a flat log of accumulated facts. Littleman maintains a hierarchical goal tree — structured as a database, not a Markdown file — that represents active strategies, their rationale, and the positions they have produced. This tree is the primary artifact of the macro layer and persists indefinitely across sessions.

---

## 4. LLM Provider Strategy

Littleman is model-agnostic by design. The choice of underlying LLM affects the quality of reasoning but not the architecture of the system. The provider layer is a thin abstraction that routes LLM calls to whichever backend is configured.

### Abstraction via LiteLLM

All LLM calls in Littleman go through [LiteLLM](https://github.com/BerriAI/litellm), an open-source gateway that exposes a single `completion()` interface regardless of backend. LiteLLM supports Anthropic, OpenAI, Ollama, LM Studio, vLLM, and 100+ other providers. The call site in Littleman code is always:

```python
from litellm import completion

response = completion(
    model=settings.llm_model,
    messages=messages,
    **settings.llm_kwargs,
)
```

The `settings.llm_model` string determines which backend is used. `anthropic/claude-sonnet-4-6` routes to Anthropic's API. `ollama/llama3.2` routes to a local Ollama instance. No other code changes.

### Configuration

All provider config lives in `.env`:

```bash
# Cloud
LLM_PROVIDER=anthropic
LLM_MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...

# Local (Ollama)
LLM_PROVIDER=ollama
LLM_MODEL=ollama/llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

### Model tiers by task

Not all tasks in Littleman require the same reasoning capability. Using a large cloud model for every operation is expensive and slow. Using an underpowered local model for high-stakes reasoning is risky. The system supports per-task-type model configuration:

| Task Type | Reasoning Demand | Default Tier |
|-----------|-----------------|--------------|
| Directive generation | High — synthesizes entire situation into focused intent | Primary model |
| Strategy planning | High — multi-step reasoning over goal tree | Primary model |
| Probability estimation | High — evidence weighing, calibration | Primary model |
| Web research extraction | Medium — structured extraction from text | Secondary model |
| Heartbeat scheduling | Low — deterministic rules, minimal LLM use | Secondary model or rule-based |
| Monitor checks | Low — position lookup, comparison | Secondary model |

The `PRIMARY_MODEL` and `SECONDARY_MODEL` env vars allow different models for each tier. In a local-only setup, both can point to the same Ollama model. In a cloud setup, primary might be Claude Sonnet and secondary might be Claude Haiku.

### Local-first operation

Littleman is designed to run fully offline once set up. The requirements for local-only operation:
- Ollama installed and running
- A model with sufficient context window (minimum 32k, recommended 64k+) pulled locally
- Polymarket API access (requires network, but the agent itself runs locally)
- Web research skills (require network for the research tasks themselves)

The agent process, the scheduler runtime, the database, and all config files run locally. No data is sent to cloud services unless the configured LLM provider is a cloud API.

### Recommended models by use case

| Use case | Recommended local | Recommended cloud |
|----------|------------------|-------------------|
| Solo dev, cost-sensitive | `ollama/llama3.1:8b` or `ollama/qwen2.5:14b` | `anthropic/claude-haiku-4-5` |
| Higher reasoning quality | `ollama/qwen2.5:32b` | `anthropic/claude-sonnet-4-6` |
| Maximum quality (slower/expensive) | `ollama/llama3.3:70b` | `anthropic/claude-opus-4-8` |

For a personal trading agent managing real capital, the recommendation is to use a capable cloud model for directive generation and strategy planning (the two highest-stakes reasoning tasks) and a local model for routine checks and research extraction. This gives quality where it matters and speed/cost efficiency for routine work.

---

## 5. System Overview

The system consists of five logical layers plus the heartbeat runtime.

```
┌─────────────────────────────────────────────────────────┐
│  META LAYER                                             │
│  World Model · Situation Synthesizer · Directive Engine │
│  Self-Scheduler                                         │
├─────────────────────────────────────────────────────────┤
│  MACRO LAYER                                            │
│  Goal Tree · Strategy Planner · Skill Registry          │
│  Risk Governor                                          │
├─────────────────────────────────────────────────────────┤
│  TASK LAYER                                             │
│  Task Tree Engine (Research / Analysis / Decision /     │
│  Monitor subtrees)                                      │
├─────────────────────────────────────────────────────────┤
│  EXECUTION LAYER                                        │
│  Web Researcher · Polymarket Client · Knowledge Base    │
│  Observation Logger                                     │
├─────────────────────────────────────────────────────────┤
│  DOMAIN MODEL (embedded, not retrieved)                 │
│  Polymarket Mechanics · Topic Ontology · Edge Theory    │
│  Wallet / Budget Model                                  │
└─────────────────────────────────────────────────────────┘

           HEARTBEAT RUNTIME (cross-cutting)
           Heartbeat Store · Scheduler Process · Context Loader
```

Each layer consumes outputs from the layer below it for domain context, and delegates work downward for execution. The meta layer does not directly execute any API calls or writes — it generates a directive that the macro layer acts on. The execution layer does not plan — it executes specific instructions issued by the task layer.

Data flows:
- **Downward**: directives, strategies, task specifications, execution instructions
- **Upward**: observations, results, resolved facts, updated balances
- **Sideways into meta**: world model is updated continuously as execution layer produces results
- **Into heartbeat store**: any layer may write a heartbeat record, but in practice the meta layer's self-scheduler writes most of them at end-of-session

---

## 6. The Meta Layer

The meta layer runs at the start of every session (every heartbeat wake) and produces the directive that drives the rest of the session. It also runs at the end of every session to plan future heartbeats.

### 4.1 World Model

The world model is the agent's persisted representation of current reality. It is not a knowledge base of facts about the world in general — it is the agent's operational state: what it knows, what it has done, what it is waiting for, and what its financial position is.

Fields:

```
WorldModel {
  // Financial state
  wallet_balance_usdc: Decimal
  open_positions: [Position]         // bets placed, not yet resolved
  pending_resolutions: [Resolution]  // markets closed, result awaited
  total_pnl: Decimal
  session_pnl: Decimal

  // Market state
  watched_markets: [MarketSnapshot]  // markets the agent is tracking but hasn't bet on
  recently_scanned: [MarketId]       // to avoid re-scanning the same markets
  last_full_scan: Timestamp

  // Information state
  active_research_topics: [Topic]    // topics currently being researched
  kb_summary: [KBEntry]             // high-level index of what's in the knowledge base
  recent_observations: [Observation] // last N observations from the observation logger

  // Temporal state
  next_heartbeats: [HeartbeatSummary] // what's scheduled and why
  current_session_start: Timestamp
  last_session_end: Timestamp

  // Calibration state
  accuracy_by_category: {category: CalibrationRecord}
  recent_outcomes: [Outcome]         // last N resolved bets with predicted vs actual
}
```

The world model is persisted between sessions. At the start of each heartbeat, the world model is loaded before any reasoning begins. It is the primary input to the situation synthesizer.

The world model is not a direct LLM context window — it is structured data stored in the database that gets serialized into a summary document for the LLM. Fields that have grown stale (e.g., scanned markets older than 6 hours) are flagged as potentially outdated.

### 4.2 Situation Synthesizer

The situation synthesizer is a structured prompt that takes the world model as input and produces a situation report as output. It does not plan or decide — it describes.

The situation report answers:
- What is the current financial state? (balance, open positions, recent P&L)
- What positions are pending resolution and when?
- What markets was the agent tracking and are any of them still open?
- What research was in progress and what was found?
- What information gaps currently exist that would affect active or potential positions?
- What has changed since the last session?

The situation report is a structured document (not free-form text) that can be parsed. Each section corresponds to a world model domain and is populated by the synthesizer. If a section has nothing to report, it is explicitly marked empty — the synthesizer does not omit sections.

### 4.3 Directive Engine

The directive engine is the component that replaces human meta-cognition. It takes the situation report as input and produces a directive — a structured description of what this session should accomplish and why.

The directive is not a task list. It is a statement of intent and priority that the macro layer will use to generate specific strategies and tasks. A directive looks like:

```
Directive {
  session_type: RESOLVE_AND_REASSESS | RESEARCH | MONITOR | FULL_CYCLE
  primary_focus: string                // e.g., "Market A resolution and follow-on sizing"
  secondary_focus: string | null
  financial_context: string            // current state summary in one paragraph
  opportunity_notes: [string]          // specific markets or topics flagged as worth attention
  constraint_notes: [string]           // risk limits, information gaps, time constraints
  explicit_skip: [string]              // things that looked interesting but are ruled out this session
}
```

The session type determines how the macro layer allocates work. A `RESOLVE_AND_REASSESS` session prioritizes checking position outcomes and re-evaluating budget allocation. A `RESEARCH` session prioritizes market scanning and information gathering. A `MONITOR` session is a lightweight check on an open position with no new betting expected. A `FULL_CYCLE` session does all of the above.

The directive engine uses an LLM call with the situation report as context. The system prompt for this call contains the agent's embedded domain knowledge and a description of what a directive is and how to construct one. The output format is enforced with structured output / function calling.

The directive is not stored permanently — it is produced each session and consumed by the macro layer in the same session. What is stored is the world model that produced it and the session log of what the directive led to.

### 4.4 Self-Scheduler

The self-scheduler runs at the end of every session, after the macro and execution layers have finished their work. It produces heartbeat records for future sessions.

Its inputs are:
- The world model (updated by the current session)
- The open positions and their expected resolution times
- The watched markets and their close times
- The research topics in progress and their expected information windows
- The current heartbeat schedule (to avoid duplicates and to cancel stale entries)

Its logic is:

1. For each open position: schedule a heartbeat at `resolution_time + grace_period` with context `{position_id, expected_outcome_source}`. Grace period is typically 5-10 minutes to allow the market to settle.

2. For each watched market that the agent has NOT yet bet on: assess whether a research window should be scheduled. If the market closes in more than 2 hours, schedule a heartbeat at `close_time - research_lead_time` where `research_lead_time` is category-dependent (politics: 2 hours, sports: 30 minutes, crypto: 15 minutes).

3. If there are active research topics with no scheduled follow-up: schedule a heartbeat for the next appropriate research window based on when relevant information is expected to be available.

4. If none of the above produce any scheduled heartbeats: schedule a maintenance heartbeat at `now + idle_interval` where `idle_interval` defaults to 4 hours. This ensures the agent wakes up periodically to scan for new markets even when there is nothing specific to monitor.

5. Review existing scheduled heartbeats. Cancel any whose trigger condition is no longer relevant (e.g., a market the agent was watching but has now decided not to bet on). Modify the context of any heartbeat where the context has changed (e.g., a position the agent expected to be pending is now resolved).

The self-scheduler does not use an LLM call for steps 1-4. These are deterministic rules applied to structured data. The LLM may be used for step 5 to evaluate whether context has changed enough to warrant amendment, but the scheduling decisions themselves are rule-based.

---

## 7. The Macro Layer

The macro layer receives the directive and produces a concrete plan: specific strategies to pursue, tasks to create, and skills to invoke. It is responsible for the goal tree and for routing work into the task layer.

### 5.1 Goal Tree

The goal tree is the hierarchical representation of what the agent is trying to accomplish. It is persisted and modified across sessions.

```
Goal (root)
  └── target: maximize risk-adjusted return on budget within time horizon
  └── budget: [user-set USDC amount]
  └── horizon: [user-set or rolling]

  Strategy (child nodes of Goal)
    └── e.g., "back undervalued YES positions in US political markets"
    └── e.g., "fade overconfident consensus in sports upsets"
    └── status: ACTIVE | PAUSED | COMPLETED | ABANDONED
    └── rationale: why this strategy is expected to have edge

    Position (child nodes of Strategy)
      └── market_id, direction, size, entry_price, current_price
      └── status: OPEN | CLOSED | PENDING_RESOLUTION

    ResearchTask (child nodes of Strategy or Position)
      └── topic, assigned_to_session, status, findings_summary
```

The goal tree is not reconstructed each session. It is a living document that the macro layer modifies. Strategies that have lost their rationale (e.g., the information advantage they relied on has been priced in) are marked PAUSED or ABANDONED. New strategies are added when the directive engine identifies a new category of opportunity.

The tree is the macro layer's memory of what it is doing and why. When a session starts with a directive, the macro layer reads the goal tree first to understand what ongoing commitments exist before generating new ones.

### 5.2 Strategy Planner

The strategy planner translates the directive into strategy modifications and task creation. It:

1. Reads the current goal tree
2. Reads the directive from the meta layer
3. Determines what strategies are relevant to this session's focus
4. For each relevant strategy: generates the concrete tasks required to advance it (research tasks, analysis tasks, decision tasks, monitor tasks)
5. For the opportunity notes in the directive: evaluates whether a new strategy should be created or whether the opportunity fits under an existing strategy
6. Writes new tasks to the task layer

The strategy planner is an LLM call with the goal tree and directive as context. Its output is a set of task creation instructions and goal tree modifications.

The strategy planner does not do research. It does not analyze specific markets. It decides what research and analysis needs to happen and creates tasks for the task layer to execute.

### 5.3 Skill Registry

The skill registry is the agent's self-knowledge of its own capabilities. It is a programmatic registry of callable functions that the agent can invoke, with descriptions that are included in the agent's context so it can reason about what it is capable of doing.

Each skill has:
```
Skill {
  name: string                      // e.g., "web_search"
  description: string               // what it does and when to use it
  parameters: Schema                // typed parameter schema
  cost_estimate: CostLevel          // LOW | MEDIUM | HIGH (time and API cost)
  requires: [string]                // other skills or data this depends on
}
```

Example skills:
- `web_search(query, source_filters)` — search the web and return structured results
- `browse_url(url)` — fetch and parse a specific page
- `scan_polymarket_markets(filters)` — query the Polymarket API for open markets
- `get_market_orderbook(market_id)` — get current order book depth and price
- `estimate_probability(topic, evidence)` — structured probability estimation
- `place_bet(market_id, direction, size_usdc)` — submit a bet via Polymarket API
- `cancel_position(position_id)` — exit an open position
- `write_to_kb(topic, content)` — write findings to the knowledge base
- `read_from_kb(topic)` — retrieve stored knowledge on a topic
- `update_world_model(fields)` — persist updates to the world model
- `create_heartbeat(fire_at, reason, context)` — schedule a future session

The skill registry is not dynamic — it does not change at runtime. New skills are added by developers. The agent cannot create new skills; it can only use the ones registered. This is an intentional constraint to keep the execution surface auditable.

### 5.4 Risk Governor

The risk governor is a constraint enforcement component that sits between the strategy planner and execution. It has veto power over any action that would:

- Exceed the maximum single-position size (default: user-configurable % of wallet)
- Exceed the maximum total exposure (default: user-configurable % of wallet in open positions)
- Increase exposure to a single market category beyond the concentration limit
- Execute a bet when the current session drawdown exceeds the session drawdown limit
- Execute a bet when total portfolio drawdown from peak exceeds the max drawdown limit

The risk governor does not use an LLM. It is a deterministic function that takes a proposed action and the current risk state and returns ALLOW or VETO with a specific reason.

When a veto occurs, the reason is written to the session log and the goal tree node that requested the action is marked with a risk-blocked flag. The directive engine sees this in the next session's world model and can adjust strategy accordingly.

User-set hard limits cannot be overridden by any agent-generated reasoning. They are enforced at the code level, not by prompt instructions.

---

## 8. The Task Layer

The task layer is the concrete execution plan for a single session. It decomposes the strategies from the macro layer into a sequenced tree of specific tasks.

Task types:

**RESEARCH** — gather information on a topic or market. Inputs: topic, source preferences, depth level. Outputs: structured findings written to KB.

**ANALYSIS** — given gathered information, produce a probability estimate and edge assessment for a specific market. Inputs: market_id, KB entries on relevant topic. Outputs: probability estimate, confidence interval, recommended action.

**DECISION** — given analysis, decide to BET, PASS, or MONITOR. Inputs: analysis output, current portfolio state, risk governor check. Outputs: bet instruction or pass reason.

**EXECUTE** — place a bet or cancel a position. Inputs: bet parameters from decision. Outputs: transaction confirmation, position record.

**MONITOR** — check the current state of an open position or market. Inputs: position_id or market_id. Outputs: updated position snapshot, flag if action needed.

**RESOLVE** — check the outcome of a position that has closed. Inputs: position_id. Outputs: outcome record, P&L update, calibration data point.

Tasks are created by the strategy planner and stored in the task tree. The task layer executor processes them in dependency order — a DECISION task cannot run before its ANALYSIS task; an EXECUTE task cannot run before its DECISION task and its risk governor check.

The task tree for a session is ephemeral — it is created at session start and archived at session end. The goal tree (in the macro layer) is what persists.

---

## 9. The Execution Layer

The execution layer contains the components that interact with external systems. It does not plan or decide — it executes specific instructions and reports results.

### 7.1 Web Researcher

Handles all information gathering from the web. Capabilities:

- **Search**: given a query and optional source filters, returns structured results (title, url, excerpt, date, source credibility score)
- **Fetch**: given a URL, returns the parsed text content
- **Aggregate**: given a topic, runs multiple searches and returns a deduplicated, structured summary

The web researcher maintains a session cache to avoid fetching the same URL twice in one session. It also checks the knowledge base before fetching — if the KB has recent (< threshold age) information on a topic, it returns that instead of making new requests.

Source credibility is scored statically by domain. The agent is instructed to weight information from primary sources (official announcements, regulatory filings, direct statements) above secondary sources (news articles, social commentary).

### 7.2 Polymarket Client

Handles all interactions with the Polymarket platform.

Read operations:
- `get_open_markets(filters)` — list markets matching category, close time, volume thresholds
- `get_market(market_id)` — full market detail including resolution criteria, current prices, volume
- `get_orderbook(market_id)` — current bid/ask depth
- `get_position(position_id)` — current state of an open position
- `get_resolved_market(market_id)` — outcome of a closed market

Write operations:
- `place_order(market_id, direction, size_usdc, price_limit)` — place a limit or market order
- `cancel_order(order_id)` — cancel a pending order

All write operations pass through the risk governor before execution. All write operations produce an audit log entry regardless of outcome.

Polymarket uses a CLOB (Central Limit Order Book) on their CLOB API. The client abstracts this: callers specify direction (YES/NO) and size in USDC; the client handles order construction, gas estimation, and Polygon transaction submission.

### 7.3 Knowledge Base

The knowledge base is a persistent store of structured information the agent has gathered through research. It is organized by topic and supports both exact retrieval and semantic search.

Each KB entry:
```
KBEntry {
  id: uuid
  topic: string                    // e.g., "2026_midterm_elections_georgia"
  content: string                  // the actual information
  source_urls: [string]
  gathered_at: Timestamp
  confidence: HIGH | MEDIUM | LOW  // agent-assigned based on source quality
  expires_at: Timestamp | null     // time after which this is considered stale
  linked_markets: [MarketId]       // markets this information is relevant to
}
```

The KB is not a general knowledge base — it only contains information the agent has explicitly gathered and written. It does not include the agent's embedded domain model (that is in the system prompt). It is the accumulation of session-specific research.

KB entries expire. Information relevant to a market that closes in 2 hours has a short expiry. Background information on a recurring topic (e.g., a political figure's polling trends) may have a longer expiry. Expired entries are flagged for refresh before use, not deleted.

### 7.4 Observation Logger

Every action taken by the execution layer is logged as an observation. Observations are structured records that associate an action with its stated rationale and later with its outcome.

```
Observation {
  id: uuid
  session_id: uuid
  action_type: BET | PASS | MONITOR | RESEARCH
  action_detail: json
  rationale: string                // agent's stated reason at time of action
  predicted_probability: Decimal   // for bets: agent's estimate at time of bet
  market_price_at_action: Decimal  // for bets: market's implied probability at time of bet
  outcome: string | null           // filled in when position resolves
  actual_probability: Decimal | null  // 1.0 or 0.0 on resolution
  pnl: Decimal | null
  logged_at: Timestamp
  resolved_at: Timestamp | null
}
```

Observation data is the input to calibration. After a meaningful number of resolved bets, the agent can compare its predicted probabilities against actual outcomes by category. Systematic overconfidence (predicting 70% on things that happen 50% of the time) becomes visible and feeds back into the situation synthesizer's framing of the agent's own reliability.

---

## 10. The Heartbeat System

### 8.1 Motivation

The agent needs to be active at specific times that are not knowable in advance and vary based on what positions are open and what markets the agent is tracking. A fixed-interval polling schedule is inefficient (runs when there is nothing to do) and imprecise (misses the specific window when a market closes).

The heartbeat system solves this by making the agent's activation schedule a data artifact that the agent itself produces and modifies. Every time the agent finishes a session, it writes records specifying when it wants to run next and why. A lightweight runtime process monitors those records and fires the agent when the time arrives.

This is architecturally similar to a job queue, but the jobs are created by the worker itself, not by an external dispatcher.

### 8.2 Heartbeat Records

A heartbeat record is a database row with the following structure:

```
Heartbeat {
  id: uuid
  fire_at: Timestamp               // when to run
  reason: string                   // human-readable explanation of why this exists
  session_type: string             // passed to the meta layer as a hint (RESOLVE | RESEARCH | MONITOR | FULL_CYCLE)
  context: json                    // structured data the session needs on wake
  status: SCHEDULED | RUNNING | DONE | CANCELLED | FAILED
  spawned_by: uuid | null          // id of the heartbeat session that created this record
  created_at: Timestamp
  started_at: Timestamp | null
  completed_at: Timestamp | null
  failure_reason: string | null
}
```

The `context` field is the critical component. It is a JSON document that the meta layer reads on wake to pre-populate the situation synthesizer with the information that triggered this heartbeat. Without it, the agent would have to re-derive the relevance of this session from the full world model, which is slower and less reliable.

Example context documents:

```json
// Position resolution check
{
  "primary_trigger": "position_resolution",
  "positions_to_check": ["pos_abc123"],
  "markets_to_check": ["mkt_xyz789"],
  "expected_outcome_sources": ["polymarket_api"],
  "follow_on_markets": ["mkt_def456"],
  "notes": "Market A resolved, check result and re-assess budget for Market B"
}

// Pre-close research window
{
  "primary_trigger": "market_close_approaching",
  "market_id": "mkt_def456",
  "closes_at": "2026-06-22T17:00:00Z",
  "research_focus": ["latest polling", "candidate statements"],
  "existing_kb_entries": ["kb_entry_001", "kb_entry_002"],
  "current_assessment": "leaning YES at 60%, market at 54%"
}

// Idle scan
{
  "primary_trigger": "idle_maintenance",
  "last_scan_age_hours": 4,
  "notes": "No specific positions to check. Scan for new markets."
}
```

### 8.3 The Scheduler Runtime

The scheduler runtime is a lightweight process separate from the agent itself. It runs continuously and does one thing: poll the heartbeat store and fire the agent when a heartbeat is due.

```
loop:
  heartbeats = db.query(
    "SELECT * FROM heartbeats WHERE status = 'SCHEDULED' AND fire_at <= now()"
  )
  for hb in heartbeats:
    db.update(hb.id, status='RUNNING', started_at=now())
    spawn_agent_session(heartbeat_id=hb.id, context=hb.context)
  sleep(30 seconds)
```

The runtime itself has no intelligence. It does not decide when to run — that decision is encoded in the `fire_at` field. It does not pass strategy to the agent — that is derived by the meta layer from the world model and the heartbeat context.

The runtime must handle:
- **Missed heartbeats**: if a heartbeat's `fire_at` has passed and it is still `SCHEDULED`, run it immediately when discovered. Log the delay.
- **Overlapping sessions**: if a heartbeat fires while a previous session is still `RUNNING`, hold the new heartbeat until the previous completes, or run it if the previous session has been running longer than a timeout threshold (indicating a hung session).
- **Failed sessions**: if an agent session ends in error, set the heartbeat status to `FAILED` with the reason and do not retry automatically. An alert should surface this to the user.

### 8.4 Cascade Behavior

The cascade is the mechanism by which the agent's schedule propagates forward in time without human intervention.

Each session, the self-scheduler component of the meta layer:
1. Reviews what happened in the current session
2. Determines what needs to happen next and when
3. Writes new heartbeat records for those future sessions
4. Amends or cancels existing scheduled heartbeats that are no longer relevant

The `spawned_by` field in each heartbeat record creates a directed graph of session lineage. This graph is the audit trail for how the agent's schedule evolved over time: which session created which future session, and why.

A cascade is never infinite by design — each heartbeat session must terminate and the sessions it spawns must terminate. The self-scheduler's rules produce a bounded number of new heartbeats per session. The idle maintenance heartbeat (a fallback when nothing specific is scheduled) creates exactly one successor heartbeat and no more.

Example cascade:

```
hb_001 (boot)
  ├── creates hb_002 (Market A resolve check, T+5h)
  └── creates hb_003 (Market B pre-close research, T+7h45m)

hb_002 (Market A resolved, WIN)
  ├── cancels hb_003 (amends context to include new budget)
  ├── creates hb_003_v2 (Market B pre-close research, same time, new context)
  └── creates hb_004 (Market C resolve check, T+9h)

hb_003_v2 (Market B pre-close)
  └── creates hb_005 (Market B resolve check, T+15m)

hb_005 (Market B resolved)
  └── creates hb_006 (idle maintenance, T+4h) if nothing else is open
```

### 8.5 Heartbeat Lifecycle

```
SCHEDULED → RUNNING → DONE
                    → FAILED
           → CANCELLED (before firing)
```

A heartbeat transitions:
- `SCHEDULED → RUNNING` when the scheduler runtime fires it
- `RUNNING → DONE` when the agent session completes successfully
- `RUNNING → FAILED` when the agent session ends in an unhandled error
- `SCHEDULED → CANCELLED` when the agent explicitly cancels it (via the `create_heartbeat` skill with a cancel instruction, or a dedicated cancel skill)

`DONE` and `CANCELLED` heartbeats are retained for audit purposes. They are never deleted. A periodic archival job can move old records to cold storage.

---

## 11. The Domain Model

The domain model is embedded knowledge — it is part of the agent's system prompt, not stored in the knowledge base or database. It does not change at runtime. It is the agent's prior knowledge of the domain it is operating in.

### 9.1 Polymarket Mechanics

The agent has embedded knowledge of how Polymarket works:

**Market structure**: Polymarket uses a Central Limit Order Book (CLOB) for most markets. Markets are binary (YES/NO) or categorical (one of N outcomes). Prices are denominated in USDC and represent the implied probability of the outcome: a YES price of $0.65 implies the market believes there is a 65% probability the outcome occurs.

**Resolution**: each market has a resolution source specified at creation — typically a named news source, official body, or oracle. The agent must read resolution criteria before betting. A market that says "resolves YES if X wins the primary" has a different resolution path than "resolves YES if X is certified as the winner by [specific date]." These distinctions affect timing of payout and the risk of no-resolution or disputed resolution.

**Liquidity**: thin order books on low-volume markets mean the agent's own order can move the price. The agent should check order book depth relative to intended position size. A large position on a thin market both increases cost (slippage) and signals the agent's view to other participants.

**Settlement**: resolved markets pay out in USDC. Winning YES positions receive $1.00 per share. Winning NO positions receive $1.00 per share. Settlement is on-chain and may take minutes to hours after resolution is declared.

**Gas and fees**: all transactions are on Polygon. Gas costs are low but non-zero. Polymarket charges a trading fee (currently a small percentage of winnings). These costs must be factored into minimum edge calculations — a 52% estimated probability on a 50% market is not necessarily a profitable bet after fees.

### 9.2 Topic Ontology

The agent has embedded knowledge of the categories of markets on Polymarket and the characteristics of each from a prediction-market-edge perspective.

**Political / Electoral**: high public interest, high volume, well-studied base rates. Primary source: official election results, FEC filings, state certification timelines. Edge sources: polling model divergence, non-obvious candidate viability signals, resolution-criteria interpretation (e.g., "wins the election" vs "wins the electoral college"). Risk: long time horizons, high correlation with other political markets (correlated exposure risk).

**Macroeconomic**: Fed decisions, GDP prints, CPI releases. Scheduled release dates are known in advance, which makes pre-release research windows well-defined. Primary source: official government releases (BLS, BEA, Federal Reserve). Edge sources: nowcasting models, historical revision patterns. Risk: market consensus is often informed by professional economists who are harder to beat than laypeople.

**Sports**: high volume, short time horizons, frequent resolution. Primary source: official league results. Edge sources: line movements, injury reports, historical head-to-head, weather (outdoor sports). Risk: highly liquid, professional sports bettors are the competition, not retail.

**Crypto**: asset prices, protocol events, regulatory decisions. Very short-horizon resolution for price markets. Primary source: on-chain data, exchange prices. Edge sources: on-chain transaction data, social sentiment divergence. Risk: highly correlated positions if betting multiple crypto markets simultaneously; crypto news cycles are rapid.

**Science and Tech**: publication dates, product launches, legal rulings on technology. Often low volume. Primary source: official announcements, court filings. Edge sources: insider knowledge of typical publication timelines, regulatory process understanding. Risk: low volume means wide spreads and high slippage.

### 9.3 Edge Theory

An edge in a prediction market exists when the agent's estimated probability of an outcome differs meaningfully from the market's implied probability, and the agent's estimate is more accurate than the market's.

Sources of edge the agent is designed to exploit:

**Information timing**: news that is publicly available but has not yet been priced into the market. This is the most common edge source. It requires faster research and synthesis than the market's average participant.

**Base rate calibration**: markets frequently misprice low-probability or high-probability events due to availability bias or anchoring. A market at 15% on an event with a historical base rate of 8% is a potential fade. The agent maintains calibration data to detect its own systematic biases and adjust.

**Resolution criteria interpretation**: market prices often reflect a colloquial understanding of the outcome rather than the precise resolution criteria. A careful reading of resolution criteria can reveal that the market is pricing the wrong thing.

**Consensus fragility**: in some categories (especially politics), public consensus can be confidently wrong. The agent can identify these by comparing primary source signals against market prices.

The agent does not attempt to exploit:
- **Latency arbitrage**: the agent is not designed to operate at millisecond speeds
- **Market manipulation**: placing large orders to move prices is prohibited and economically unsound at the scale this agent operates
- **Inside information**: the agent uses only publicly available information

### 9.4 Wallet and Budget Model

The agent operates with a single USDC wallet on Polygon. The user sets a budget at initialization. The agent does not have access to funds beyond the wallet balance — it cannot borrow or lever.

The budget is tracked at two levels:
- **Total wallet balance**: all USDC in the wallet including locked-in open positions
- **Available balance**: USDC not currently committed to open positions

The agent uses a fractional Kelly criterion for position sizing. The full Kelly formula (`edge / odds`) is used to calculate the theoretically optimal bet size, and the agent bets a fraction of that (default: 0.25x Kelly, configurable). Fractional Kelly reduces variance at the cost of some expected value, which is appropriate for an agent operating with a finite budget and a goal of long-term compounding rather than single-session maximization.

All sizing decisions are subject to the risk governor's hard limits regardless of what Kelly suggests.

---

## 12. The Planning Cycle

A complete planning cycle, from heartbeat wake to heartbeat creation:

```
1. WAKE
   Scheduler runtime fires heartbeat hb_N
   Agent process starts with heartbeat_id and context blob

2. WORLD MODEL LOAD
   Load persisted world model from database
   Merge heartbeat context into world model (context fields take precedence for this session)
   Flag any world model fields that are stale based on age thresholds

3. SITUATION SYNTHESIS (Meta Layer)
   Serialize world model to situation report document
   Identify and flag stale, missing, or contradictory information
   Produce structured situation report

4. DIRECTIVE GENERATION (Meta Layer)
   LLM call: situation report → directive
   Determine session_type, primary focus, opportunity notes, constraint notes
   Output: Directive record

5. STRATEGY PLANNING (Macro Layer)
   Load goal tree
   LLM call: directive + goal tree → strategy modifications + task creation instructions
   Write new tasks to task tree
   Update goal tree (new strategies, status changes)

6. TASK EXECUTION (Task Layer → Execution Layer)
   Process task tree in dependency order:
     RESEARCH tasks: web researcher → KB writes
     ANALYSIS tasks: KB reads + LLM estimation → probability assessments
     DECISION tasks: probability assessment + risk governor → BET or PASS
     EXECUTE tasks: Polymarket client → order confirmation → position record
     MONITOR tasks: Polymarket client → position snapshot → flag if changed
     RESOLVE tasks: Polymarket client → outcome record → P&L update → observation log

7. WORLD MODEL UPDATE (Meta Layer)
   Consolidate all updates from execution layer
   Update positions, balances, KB index, recent observations
   Persist updated world model

8. HEARTBEAT PLANNING (Meta Layer → Self-Scheduler)
   Evaluate: what needs to happen next and when?
   Create new heartbeat records
   Amend or cancel existing scheduled heartbeats
   Persist all heartbeat changes

9. SESSION END
   Mark current heartbeat as DONE
   Write session summary to audit log
   Agent process exits
```

---

## 13. The Observation Loop

The observation loop is the mechanism by which the agent's past performance informs its future behavior. It is not a training loop — it does not modify model weights. It is a calibration loop that modifies the agent's operational parameters and self-assessment.

At bet placement time, the observation logger records:
- The agent's estimated probability
- The market's implied probability at the time of bet
- The agent's stated rationale
- The position size and direction

When a position resolves, the observation logger records:
- The actual outcome
- The P&L
- The delta between predicted and actual probability

These records accumulate into calibration statistics by category:

```
CalibrationRecord {
  category: string
  n_bets: int
  brier_score: Decimal             // lower is better, measures probability accuracy
  mean_edge: Decimal               // average (predicted_prob - market_prob)
  realized_edge: Decimal           // average (actual_outcome - market_prob)
  accuracy_by_confidence_bucket: {
    "50-60%": {predicted: 55%, actual: ?%},
    "60-70%": {predicted: 65%, actual: ?%},
    ...
  }
}
```

These records are included in the world model and surface in the situation report. If the agent is systematically overconfident in a category (predicting 65% on things that happen 50% of the time), the situation synthesizer flags this. The directive engine then applies a discount to that category's estimated edges.

This is not automated model updating — it is information made available to the agent's reasoning. The agent can decide to apply a category discount, reduce position sizes in that category, or pause activity in that category entirely. The decision is made by the directive engine with the calibration data as context.

---

## 14. Data Model

The database is SQLite (WAL mode) managed via SQLAlchemy ORM and Alembic migrations. UUIDs are generated in Python and stored as strings. JSON columns use SQLite's native JSON type. Knowledge base full-text search uses SQLite FTS5 — no external vector store is required at this scale.

The authoritative schema is in `littleman/db/models.py`. What follows is a readable summary.

### Agent operation tables

```
heartbeats
  id            TEXT (UUID, PK)
  fire_at       DATETIME (timezone-aware)
  reason        TEXT
  session_type  TEXT    — SCHEDULED | RUNNING | DONE | FAILED | CANCELLED
  context       JSON    — structured data the session reads on wake
  status        TEXT    — SCHEDULED | RUNNING | DONE | FAILED | CANCELLED
  spawned_by    TEXT    — FK → heartbeats.id (lineage graph for cascade audit)
  created_at    DATETIME
  started_at    DATETIME (nullable)
  completed_at  DATETIME (nullable)
  failure_reason TEXT (nullable)

agent_sessions
  id                TEXT (UUID, PK)
  heartbeat_id      TEXT (nullable, FK → heartbeats.id)
  directive         JSON (nullable)   — the directive that drove this session
  tasks_created     INTEGER
  tasks_completed   INTEGER
  bets_placed       INTEGER
  research_calls    INTEGER
  heartbeats_created INTEGER
  started_at        DATETIME
  ended_at          DATETIME (nullable)
  outcome_summary   TEXT (nullable)

positions
  id                    TEXT (UUID, PK)
  market_id             TEXT
  market_title          TEXT
  direction             TEXT    — YES | NO
  size_usdc             NUMERIC(18,6)
  entry_price           NUMERIC(6,4)
  predicted_probability NUMERIC(6,4)
  strategy_id           TEXT (nullable, FK → strategies.id)
  status                TEXT    — OPEN | CLOSED | PENDING_RESOLUTION
  outcome               TEXT (nullable)   — WIN | LOSS
  pnl                   NUMERIC(18,6) (nullable)
  placed_at             DATETIME
  resolved_at           DATETIME (nullable)
  external_order_id     TEXT (nullable)  -- application-specific order reference

strategies                         — goal tree nodes
  id          TEXT (UUID, PK)
  parent_id   TEXT (nullable, FK → strategies.id)
  node_type   TEXT    — GOAL | STRATEGY | RESEARCH_TASK
  title       TEXT
  rationale   TEXT (nullable)
  status      TEXT    — ACTIVE | PAUSED | COMPLETED | ABANDONED
  created_at  DATETIME
  updated_at  DATETIME (nullable)
  metadata    JSON

kb_entries                         — accumulated research knowledge base
  id                TEXT (UUID, PK)
  topic             TEXT (indexed)
  content           TEXT
  source_urls       JSON    — list of URL strings
  confidence        TEXT    — HIGH | MEDIUM | LOW
  gathered_at       DATETIME
  expires_at        DATETIME (nullable)
  linked_market_ids JSON    — list of market ID strings
  (full-text search via SQLite FTS5 virtual table — no vector store needed)

observations                       — per-action records for calibration
  id                      TEXT (UUID, PK)
  session_id              TEXT
  heartbeat_id            TEXT (nullable, FK → heartbeats.id)
  action_type             TEXT    — BET | PASS | MONITOR | RESEARCH
  action_detail           JSON
  rationale               TEXT (nullable)
  predicted_probability   NUMERIC(6,4) (nullable)
  market_price_at_action  NUMERIC(6,4) (nullable)
  outcome                 TEXT (nullable)
  actual_probability      NUMERIC(6,4) (nullable)
  pnl                     NUMERIC(18,6) (nullable)
  logged_at               DATETIME
  resolved_at             DATETIME (nullable)

world_model                        — single row, updated in-place each session
  id                      INTEGER (PK, always 1)
  wallet_balance_usdc     NUMERIC(18,6)
  available_balance_usdc  NUMERIC(18,6)
  total_pnl               NUMERIC(18,6)
  last_full_scan          DATETIME (nullable)
  updated_at              DATETIME (nullable)
  extended_state          JSON    — overflow fields (open_positions, calibration, etc.)
```

### Chat and operator tables

```
chat_sessions                      — user↔LLM conversations + the Main agent narration session
  id          TEXT (PK)            — "main" is the reserved ID for the agent narration feed
  title       TEXT
  created_at  DATETIME
  updated_at  DATETIME

chat_messages
  id            TEXT (UUID, PK)
  session_id    TEXT (FK → chat_sessions.id, CASCADE DELETE)
  role          TEXT    — user | assistant | tool
  content       TEXT (nullable)
  thinking      TEXT (nullable)   — extended thinking block (if model supports it)
  tool_calls    JSON (nullable)   — [{id, name, args}]
  tool_call_id  TEXT (nullable)   — for tool result messages
  tool_name     TEXT (nullable)
  created_at    DATETIME

agent_guidance                     — operator-to-agent guidance injection
  id           TEXT (UUID, PK)
  text         TEXT
  created_at   DATETIME
  consumed_at  DATETIME (nullable)   — set when passed to a session; pending if null

llm_configs                        — LLM provider config (editable via Settings UI)
  id            TEXT (UUID, PK)
  name          TEXT (unique)
  provider      TEXT    — anthropic | openai | ollama | litellm
  model         TEXT    — full LiteLLM model string
  api_key       TEXT (nullable)
  base_url      TEXT (nullable)
  is_primary    BOOLEAN
  is_secondary  BOOLEAN
  extra_params  JSON
  created_at    DATETIME
```

---

## 15. Risk Management

Risk management is enforced at two levels: hard limits and soft constraints.

**Hard limits** are set by the user at initialization and cannot be modified by the agent:

| Limit | Default | Description |
|-------|---------|-------------|
| `max_position_pct` | 20% | Maximum single position as % of wallet balance |
| `max_exposure_pct` | 80% | Maximum total open positions as % of wallet balance |
| `max_session_drawdown_pct` | 15% | Maximum loss in a single session before halting new bets |
| `max_total_drawdown_pct` | 40% | Maximum drawdown from peak balance before full halt |
| `max_category_exposure_pct` | 40% | Maximum exposure to any single topic category |

Hard limits are checked by the risk governor as a precondition to any EXECUTE task. A violation returns VETO and the bet is not placed. No reasoning or override is possible within the agent.

**Soft constraints** are heuristics the agent applies in the strategy planning phase:

- Prefer markets with sufficient volume (above a configurable threshold) to avoid slippage
- Avoid taking positions in correlated markets where the combined exposure exceeds the category limit
- Apply a minimum edge threshold before betting (default: estimated probability must exceed market price by at least 3 percentage points after estimated fees)
- Apply a confidence threshold: only bet when the agent's confidence in its probability estimate is HIGH or MEDIUM; do not bet on LOW confidence estimates regardless of apparent edge

**Circuit breaker**: if total portfolio drawdown exceeds `max_total_drawdown_pct`, the agent enters a read-only mode. It continues to monitor positions and schedule heartbeats but will not place new bets. It surfaces this state prominently in the world model. Exiting read-only mode requires explicit user action (a configuration change), not a recovery in balance.

---

## 16. Design Decisions and Tradeoffs

**Why is the directive engine an LLM call and not a rule-based system?**

The situation synthesizer produces a situation report that has variable content — some sessions the dominant fact is a position resolution, others it is a new market opportunity, others it is a calibration warning. Determining which of these is most important in context, and what the appropriate session focus should be, requires reasoning over unstructured observations. A rule-based system would need explicit rules for every combination of states, which grows unmanageable. The LLM is used precisely where judgment over diverse inputs is required.

**Why is the risk governor rule-based and not an LLM call?**

Financial limits must be enforced deterministically. An LLM call could in principle reason its way around a hard limit ("the expected value justifies the exception"). This is unacceptable for a system managing real money. Hard limits are code, not instructions.

**Why are heartbeat contexts stored as JSON blobs rather than typed records?**

Different heartbeat types require different context fields. A position-resolution heartbeat needs position IDs and expected sources. A research heartbeat needs a topic and existing KB entries. A typed schema would require a separate schema for each heartbeat type, which increases rigidity. JSON blobs allow the agent to store exactly the context fields that are relevant to each specific heartbeat without schema migrations when new heartbeat patterns emerge.

**Why is the knowledge base session-accumulated rather than pre-populated?**

The agent should be able to reason about what it knows and how fresh that knowledge is. A pre-populated knowledge base of general world knowledge creates an opaque prior that the agent cannot audit. By having the KB contain only what the agent has explicitly researched, the agent can see exactly what information it is drawing on when making a decision. The embedded domain model covers the stable, structural knowledge that never needs refreshing.

**Why fractional Kelly rather than full Kelly?**

Full Kelly maximizes long-run expected log wealth but produces extreme variance in the short run, including large drawdowns. For an agent with a finite budget and a user who checks results periodically, a large drawdown is a worse outcome than a somewhat lower return. Fractional Kelly (25% of full Kelly by default) substantially reduces variance while retaining most of the long-run growth advantage. The fraction is configurable — users with higher risk tolerance can increase it.

**Why does the task tree reset each session while the goal tree persists?**

The task tree is the operational plan for a specific session given the current directive. It is specific to what this session found and decided to do. Persisting it across sessions would create stale tasks and ambiguity about what has been done. The goal tree is the strategic structure — which strategies are being pursued, why, and with what track record. This needs to persist because strategies play out over multiple sessions.
