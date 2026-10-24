# Readiness

A multi-domain morning readiness brief for a performance department.

It reads the streams a staff already collects — subjective wellness, HRV,
neuromuscular (CMJ), plus training load and GPS — and posts one short message
before the athletes walk in: who to review, who to watch, and why. Thirty
seconds to read. The staff gets their morning back.

Built by [Mauro Castillo, MD, MS, CSCS, RSCC, CPSS](https://maurocastillomd.com). Concept
walkthrough: [maurocastillomd.com/readiness](https://maurocastillomd.com/readiness).

## Two rules

> **The AI does not write numbers. And it surfaces availability — it never predicts injury.**

Code reads the data and computes every baseline, z-score, and flag. The model
only takes a fact that is already true and says it in plain English. Every
number in the model's output is checked against the numbers the engine actually
computed ([`narrate.py`](src/readiness/narrate.py)); one invented number and the
output is discarded for a deterministic template. And nothing here forecasts
injury — no screening test predicts individual injuries with useful accuracy
(see [SCIENCE.md](SCIENCE.md)). It surfaces individual change so a human acts
earlier.

## What it flags on

Three **response domains**, each measured against the athlete's own 28-day
baseline, sign-normalized so a decline is always a negative z:

- **Perceptual** — subjective wellness. The highest signal-to-cost monitor.
- **Autonomic** — HRV, read as a 7-day rolling mean of ln rMSSD.
- **Neuromuscular** — CMJ via RSI-modified (a strategy-sensitive metric, not
  jump height).

Status escalates on **convergence**: any domain past −2.0 z is REVIEW, and so is
agreement across domains (two response domains at or under −1.2 z). One domain
down is MONITOR. Flagging on domains that *agree* beats flagging on any single
number.

**Load is context, never a flag.** Internal load (sRPE), external load (GPS),
and the acute:chronic workload ratio explain the "why". They never set status —
ACWR in particular is a flawed ratio with no evidence for load management. See
[SCIENCE.md](SCIENCE.md) for the citations behind every one of these choices.

## How it runs

```
adapter -> merge -> engine -> anonymize -> narrate -> verify -> Slack
(data in)  (identity  (all math,  (names off)  (one LLM   (numbers   (names back
            resolved)  convergence)             call)      checked)   on, out)
```

- **Adapter** ([`adapters.py`](src/readiness/adapters.py)) — every source returns
  the same `Reading` objects. Ships a synthetic-CSV adapter standing in for real
  devices (VALD, Catapult, a wearable, a wellness form).
- **Merge** ([`merge.py`](src/readiness/merge.py)) — resolves one athlete across
  sources that name people differently (the real janitor work of team data).
- **Engine** ([`engine.py`](src/readiness/engine.py)) — the deterministic core, no
  AI. Individual baselines, per-stream freshness, convergence status, load context.
- **Privacy wall** ([`anonymize.py`](src/readiness/anonymize.py)) — names come off
  before the model. It works on "Athlete 7"; code re-attaches the name after.
- **Narration** ([`narrate.py`](src/readiness/narrate.py)) — the only file that
  talks to a model, plus the number guard. No API key? Templates run everything.
- **Brief** ([`brief.py`](src/readiness/brief.py)) — assembles the message and posts
  it to a Slack webhook.

## Quickstart

```bash
./run.sh                                        # run the morning brief (creates .venv)
./run.sh --post                                 # also deliver to $SLACK_WEBHOOK_URL
.venv/bin/python scripts/generate_data.py       # rebuild the synthetic squad
.venv/bin/python -m pytest                       # the test suite
```

`ANTHROPIC_API_KEY` (in a local `.env`) enables Claude
phrasing; without it the deterministic templates run.

## What this is, and what it isn't

- Every athlete in `data/` is **synthetic**. Invented names, generated numbers.
- It **surfaces availability**; it does not diagnose or predict injury. It hands
  a human a prioritized list and gets out of the way.
- Load and ACWR are context only. They never flag anyone.
- Real-platform adapters (VALD ForceDecks, Catapult, a wearable API, an AMS
  export) are the same `fetch()` interface against a vendor API. They are not in
  this repo: credentials, data agreements, and CBA governance belong to a team
  engagement.

See [SCIENCE.md](SCIENCE.md) for the evidence base and citations.
