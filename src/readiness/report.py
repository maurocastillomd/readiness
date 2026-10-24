"""Assemble and render the weekly report.

rollup -> anonymize -> narrate summary + per-flagged notes -> verify ->
deanonymize -> one self-contained HTML string (print-to-PDF ready).

Real names re-attach here, after narration. The HTML carries no numbers the
engine did not compute, and no injury/prediction language.
"""

from __future__ import annotations

from datetime import date, timedelta

from .anonymize import Roster
from .models import AthleteWeek, Status, WeeklyReport
from .narrate import DEFAULT_MODEL, narrate_note, narrate_weekly_summary
from .weekly import WEEK_DAYS, rollup_squad

_STATUS_COLOR = {Status.REVIEW: "alert", Status.MONITOR: "warn", Status.CLEARED: "ok"}
_STATUS_LABEL = {Status.REVIEW: "REVIEW", Status.MONITOR: "MONITOR", Status.CLEARED: "CLEARED"}


def build_weekly_report(readings, end: date,
                        model: str = DEFAULT_MODEL) -> WeeklyReport:
    rows = rollup_squad(readings, end)
    roster = Roster(sorted((w.worst_day for w in rows), key=lambda a: a.athlete_id))
    week_start = end - timedelta(days=WEEK_DAYS - 1)
    summary = roster.deanonymize(
        narrate_weekly_summary(rows, roster, week_start, end, model=model))
    for w in rows:
        if w.week_status is not Status.CLEARED:
            w.note = roster.deanonymize(narrate_note(w.worst_day, roster, model=model))
    return WeeklyReport(week_start=week_start, week_end=end, summary=summary,
                        athletes=rows, total=len(rows))


def _sparkline(w: AthleteWeek) -> str:
    pts = w.daily_z
    if not pts:
        return ""
    W, H = 120.0, 36.0
    zmin, zmax = -3.0, 1.0

    def y(z):
        z = max(zmin, min(zmax, z))
        return round(H - (z - zmin) / (zmax - zmin) * H, 1)

    n = len(pts)
    coords = [(round(i / (n - 1) * W, 1) if n > 1 else W / 2, y(p.z))
              for i, p in enumerate(pts)]
    line = " ".join(f"{x},{yy}" for x, yy in coords)
    zero = y(0.0)
    dots = "".join(f'<circle cx="{x}" cy="{yy}" r="1.6" fill="currentColor"/>'
                   for x, yy in coords)
    return (f'<svg class="spark" viewBox="0 0 {W:.0f} {H:.0f}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<line x1="0" y1="{zero}" x2="{W:.0f}" y2="{zero}" class="spark-zero"/>'
            f'<polyline points="{line}" fill="none" stroke="currentColor" '
            f'stroke-width="1.5"/>{dots}</svg>')


def _pct(v):
    return "—" if v is None else f"{v:+.2f}"


def _card(w: AthleteWeek) -> str:
    color = _STATUS_COLOR[w.week_status]
    chips = "".join(f'<span class="chip">{d.value}</span>' for d in w.drivers)
    acwr = "—" if w.acwr_end is None else f"{w.acwr_end:.2f}"
    spike = ' · load spike' if w.load_spike else ""
    return f"""
    <article class="card card--{color}">
      <div class="card-head">
        <div><h3>{w.name}</h3><span class="pos">{w.pos}</span></div>
        <span class="pill pill--{color}">{_STATUS_LABEL[w.week_status]}</span>
      </div>
      <div class="chips">{chips}</div>
      <div class="stats">
        <div><b>{w.days_flagged}</b><span>days flagged</span></div>
        <div><b>{w.week_mean_z:+.2f}</b><span>week readiness z</span></div>
        <div><b>{_pct(w.delta_z)}</b><span>Δ vs last week</span></div>
        <div class="spark-wrap {color}">{_sparkline(w)}</div>
      </div>
      <p class="note">{w.note}</p>
      <p class="ctx">Workload context: ACWR {acwr}{spike}. Context only — never a flag.</p>
    </article>"""


def _watch_row(w: AthleteWeek) -> str:
    return (f'<tr><td>{w.name}</td><td class="pos">{w.pos}</td>'
            f'<td class="num">{w.week_mean_z:+.2f}</td>'
            f'<td class="num">{_pct(w.delta_z)}</td>'
            f'<td>cleared all week, trending down</td></tr>')


def _squad_row(w: AthleteWeek) -> str:
    color = _STATUS_COLOR[w.week_status]
    drivers = ", ".join(d.value for d in w.drivers) or "—"
    acwr = "—" if w.acwr_end is None else f"{w.acwr_end:.2f}"
    return (f'<tr><td>{w.name}</td><td class="pos">{w.pos}</td>'
            f'<td class="num">{w.days_tested}</td><td class="num">{w.days_flagged}</td>'
            f'<td class="num">{w.week_mean_z:+.2f}</td><td class="num">{_pct(w.delta_z)}</td>'
            f'<td>{drivers}</td><td class="num">{acwr}</td>'
            f'<td><span class="pill pill--{color} pill--sm">{_STATUS_LABEL[w.week_status]}</span></td></tr>')


def render_report_html(report: WeeklyReport, generated: date) -> str:
    rng = f"{report.week_start.strftime('%b %-d')} – {report.week_end.strftime('%b %-d, %Y')}"
    cards = "".join(_card(w) for w in report.flagged) or \
        '<p class="empty">No athletes flagged this week.</p>'
    watch = report.watch
    watch_block = ""
    if watch:
        rows = "".join(_watch_row(w) for w in watch)
        watch_block = f"""
      <section><h2>Watch list</h2>
        <table class="watch"><thead><tr><th>Athlete</th><th>Pos</th>
        <th class="num">Week z</th><th class="num">Δ</th><th>Why</th></tr></thead>
        <tbody>{rows}</tbody></table></section>"""
    squad = "".join(_squad_row(w) for w in report.athletes)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Readiness — Weekly Report — {rng}</title>
<style>{_CSS}</style></head><body><main class="wrap">
  <header class="rpt-head">
    <span class="eyebrow">Readiness · Weekly Report</span>
    <h1>Week of {rng}</h1>
    <p class="byline">Mauro Castillo — MD, MS, CSCS</p>
  </header>
  <section class="counts">
    <div><b>{report.total}</b><span>tested</span></div>
    <div class="alert"><b>{len(report.flagged)}</b><span>flagged</span></div>
    <div class="accent"><b>{len(watch)}</b><span>to watch</span></div>
    <div class="ok"><b>{report.cleared_count}</b><span>within range</span></div>
  </section>
  <section class="summary"><h2>This week</h2><p>{report.summary}</p></section>
  <section><h2>Flagged</h2><div class="cards">{cards}</div></section>
  {watch_block}
  <section><h2>Full squad</h2>
    <table class="squad"><thead><tr><th>Athlete</th><th>Pos</th>
    <th class="num">Days</th><th class="num">Flagged</th><th class="num">Week z</th>
    <th class="num">Δ</th><th>Drivers</th><th class="num">ACWR</th><th>Status</th>
    </tr></thead><tbody>{squad}</tbody></table></section>
  <footer class="rpt-foot">
    <p>All athletes synthetic — concept demo. Every number computed by the
    deterministic engine. The AI never writes a number.</p>
    <p>Generated {generated.strftime('%B %-d, %Y')} · maurocastillomd.com/readiness</p>
  </footer>
</main></body></html>"""


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..900&family=Hanken+Grotesk:wght@300..700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--bg:#FAFAF9;--card:#FFFFFF;--ink:#0B0B0C;--dim:#52525B;--faint:#8A8A93;
--accent:#2039C4;--accent-wash:rgba(32,57,196,.06);--ok:#2F7D5B;--warn:#B0791F;
--alert:#C0503F;--line:rgba(11,11,12,.08);--display:'Fraunces',Georgia,serif;
--sans:'Hanken Grotesk',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,monospace;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:var(--sans);line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:48px 32px 72px}
.eyebrow{font-family:var(--mono);text-transform:uppercase;letter-spacing:.18em;
font-size:11px;color:var(--accent)}
h1{font-family:var(--display);font-weight:600;font-size:40px;margin:.2em 0 .1em;letter-spacing:-.02em}
h2{font-family:var(--display);font-weight:600;font-size:22px;margin:40px 0 16px}
h3{font-family:var(--display);font-weight:600;font-size:20px;margin:0}
.byline{color:var(--dim);margin:.2em 0 0}
.counts{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}
.counts>div{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:18px}.counts b{font-family:var(--display);font-size:34px;display:block;line-height:1}
.counts span{font-family:var(--mono);font-size:10px;text-transform:uppercase;
letter-spacing:.14em;color:var(--faint)}
.counts .alert b{color:var(--alert)}.counts .accent b{color:var(--accent)}.counts .ok b{color:var(--ok)}
.summary p{font-size:18px;color:var(--ink);background:var(--accent-wash);
border-left:3px solid var(--accent);border-radius:0 12px 12px 0;padding:16px 20px;margin:0}
.cards{display:grid;grid-template-columns:1fr;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:22px;border-left-width:4px}
.card--alert{border-left-color:var(--alert)}.card--warn{border-left-color:var(--warn)}
.card--ok{border-left-color:var(--ok)}
.card-head{display:flex;justify-content:space-between;align-items:flex-start}
.pos{font-family:var(--mono);font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.1em}
.pill{font-family:var(--mono);font-size:11px;letter-spacing:.12em;padding:4px 10px;
border-radius:999px;color:#fff}.pill--sm{font-size:10px;padding:3px 8px}
.pill--alert{background:var(--alert)}.pill--warn{background:var(--warn)}.pill--ok{background:var(--ok)}
.chips{margin:12px 0 4px}.chip{display:inline-block;font-family:var(--mono);font-size:11px;
text-transform:uppercase;letter-spacing:.08em;color:var(--accent);background:var(--accent-wash);
border-radius:6px;padding:3px 8px;margin-right:6px}
.stats{display:grid;grid-template-columns:repeat(3,auto) 1fr;gap:18px;align-items:center;
margin:14px 0}.stats b{font-family:var(--display);font-size:22px;display:block;line-height:1.1}
.stats span{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:.12em;color:var(--faint)}
.spark-wrap{height:36px}.spark-wrap.alert{color:var(--alert)}.spark-wrap.warn{color:var(--warn)}
.spark-wrap.ok{color:var(--ok)}.spark{width:100%;height:36px;overflow:visible}
.spark-zero{stroke:var(--line);stroke-width:1;stroke-dasharray:2 2}
.note{margin:8px 0 6px;font-size:15px}.ctx{margin:0;font-size:12px;color:var(--faint);font-family:var(--mono)}
table{width:100%;border-collapse:collapse;font-size:14px}
th{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em;
color:var(--faint);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:9px 10px;border-bottom:1px solid var(--line)}.num{text-align:right;font-variant-numeric:tabular-nums}
.empty{color:var(--faint)}
.rpt-foot{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);
color:var(--faint);font-size:12px}.rpt-foot p{margin:2px 0}
@media print{body{background:#fff}.wrap{padding:0}.card,.counts>div{box-shadow:none}
.card,section{break-inside:avoid}@page{margin:14mm}}
"""
