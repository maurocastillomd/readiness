# The science behind Readiness

Readiness surfaces individual change in athlete readiness across domains. It
does **not** predict injury. No screening test predicts individual injuries
with useful accuracy — Bahr R. "Why screening tests to predict injury do not
work—and probably never will: a critical review." Br J Sports Med 2016.
https://doi.org/10.1136/bjsports-2016-096256

## What the engine flags on (response domains)

- **Perceptual (subjective wellness).** The highest signal-to-cost monitor:
  subjective self-report tracks acute and chronic load with superior
  sensitivity to objective measures — Saw AE, Main LC, Gastin PB. "Monitoring
  the athlete training response: subjective self-reported measures trump
  commonly used objective measures: a systematic review." Br J Sports Med 2016.
  https://doi.org/10.1136/bjsports-2015-094758
- **Autonomic (HRV).** Read as the 7-day rolling mean of ln rMSSD, individually
  z-scored; a low rolling HRV combined with high load raised overuse-problem
  risk while high load was tolerated when HRV held normal — Williams S, Booton
  T, Watson M, Rowland D, Altini M. J Sports Sci Med 2017;16(4):443-449.
  https://pubmed.ncbi.nlm.nih.gov/29238242/
- **Neuromuscular (CMJ).** Flagged on RSI-mod, a strategy-sensitive metric, not
  jump height: alternative CMJ mechanics variables detect acute fatigue and
  training adaptation with larger effect sizes than typical output like height
  — Gathercole RJ, Stellingwerff T, Sporer BC. J Strength Cond Res
  2015;29(1):37-46. https://doi.org/10.1519/JSC.0000000000000622

## What is context, never a flag

- **Internal load (sRPE), external load (GPS), and ACWR.** Load explains the
  "why"; it never sets availability status. The acute:chronic workload ratio in
  particular is a mathematically flawed metric with no evidence for load
  management — Impellizzeri FM, Tenan MS, Kempton T, Novak A, Coutts AJ.
  "Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls."
  Int J Sports Physiol Perform 2020;15(6):907-913.
  https://doi.org/10.1123/ijspp.2019-0864

## Method

Individual 28-day rolling baselines, z-scores against each athlete's own
noise, the smallest worthwhile change (0.2 × SD), and **convergence** — status
escalates when domains agree (two response domains at or under −1.2 z → REVIEW),
not on any single metric. Each stream is read on its own cadence (most recent
within a freshness window), so nothing requires a daily test in every domain.
All figures are computed by the deterministic engine; the AI only phrases them
and every number is verified against the engine. All data in this repo is
synthetic.

_Citations retrieved via PubMed._
