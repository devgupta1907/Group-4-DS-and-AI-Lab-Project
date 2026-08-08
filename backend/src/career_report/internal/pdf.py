"""Server-rendered PDF for a saved report snapshot."""

# ruff: noqa: E501 -- CSS is intentionally kept as a compact self-contained template.

from __future__ import annotations

import asyncio
import sys
import threading
from html import escape

from src.career_report.schemas import CareerReport


def _list(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def render_html(report: CareerReport) -> str:
    content = report.content
    narrative = content.narrative
    assessment = narrative.profile_assessment
    roles = "".join(
        f"""<article class="card"><span class="tag">{escape(role.readiness.replace("_", " "))}</span>
        <h3>{escape(role.title)}</h3><p>{escape(role.rationale)}</p>
        <strong>{escape(role.confidence)} confidence · {escape(role.effort)} effort</strong>
        <h4>Why this is credible</h4><ul>{_list(role.evidence)}</ul>
        <h4>Recommended test</h4><p>{escape(role.next_step)}</p></article>"""
        for role in narrative.roles
    )
    jobs = "".join(
        f"""<article class="job"><div><h3>{escape(job.title)}</h3>
        <p>{escape(job.company)} · {escape(job.location)}</p></div>
        <b>{job.interview_probability}%</b><p>{escape(job.reason)}</p>
        <a href="{escape(job.source_url)}">{escape(job.source_url)}</a></article>"""
        for job in content.opportunities
    )
    weeks = "".join(
        f"""<article class="week"><b>Week {week.week} · {escape(week.theme)}</b>
        <p>{escape(week.outcome)}</p><ul>{_list([task.action for task in week.tasks])}</ul></article>"""
        for week in narrative.weekly_plan
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size:A4; margin:14mm 13mm 15mm; @bottom-right {{content:"DiscoverMyRole · " counter(page); font-size:7.5pt; color:#7d939c}} }}
    *{{box-sizing:border-box}}
    body{{font-family:'DM Sans',Arial,sans-serif;color:#0f2a33;background:#fff;font-size:9pt;line-height:1.45;margin:0}}
    h1,h2,h3,h4{{margin:0 0 6px;letter-spacing:-.02em}}
    h1{{font-size:19pt;line-height:1.12}}
    h2{{font-size:12.5pt;margin:18px 0 8px;padding-bottom:4px;border-bottom:1.5px solid #114656;color:#114656}}
    h3{{font-size:10pt}} h4{{font-size:8pt;margin:7px 0 2px;color:#5d7480;text-transform:uppercase;letter-spacing:.06em}}
    p{{margin:0 0 5px}} ul{{margin:0;padding-left:14px}} li{{margin-bottom:2px}}
    a{{color:#1c6377;word-break:break-all;text-decoration:none}}
    .kicker,span.tag{{color:#4aa9b4;text-transform:uppercase;font-weight:700;letter-spacing:.09em;font-size:7pt}}
    /* Header is a document header, not a landing page: one band, no oversized type. */
    .hero{{background:#0f2a33;color:#f4f7f8;padding:16px 18px;border-radius:12px;border-left:5px solid #71c4cc}}
    .hero p:last-child{{margin:6px 0 0;color:#cfe0e4;font-size:8.5pt}}
    /* Two columns, not three: three forced 4-5 words per line on A4. */
    .summary{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    .summary p,.card,.job,.week,.assessment{{border:1px solid #d3e0e3;border-radius:9px;padding:9px 11px;break-inside:avoid}}
    .card h3{{margin:3px 0 4px;color:#114656}} .card strong{{color:#4aa9b4;font-size:8pt}}
    .assessment{{border-left:4px solid #114656;background:#f4f7f8}}
    .job{{display:grid;grid-template-columns:1fr auto;gap:3px 10px;margin-bottom:6px;align-items:start}}
    .job h3{{margin:0;color:#114656}} .job p,.job a{{grid-column:1/-1;margin:0;font-size:8pt}}
    .job b{{font-size:14pt;color:#114656;line-height:1}}
    .funnel{{display:flex;gap:8px}}
    .funnel div{{flex:1;padding:9px;background:#e3f2f4;border-radius:9px;text-align:center;font-size:8pt;color:#5d7480}}
    .funnel b{{display:block;font-size:16pt;color:#114656;line-height:1.1}}
    .weeks{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    .week b{{color:#114656}} .week p{{color:#5d7480;font-size:8pt}}
    small{{color:#7d939c}}
    </style></head><body>
    <section class="hero"><p class="kicker">Career Guidance Report</p>
    <h1>{escape(narrative.headline)}</h1>
    <p>{escape(content.candidate_name or "Candidate")} ·
    {escape(content.candidate_location or "Location not supplied")}</p></section>
    <h2>Executive guidance</h2><section class="summary">
    {"".join(f"<p>{escape(item)}</p>" for item in narrative.executive_summary)}</section>
    <h2>Your professional profile today</h2>
    <section class="assessment"><h3>{escape(assessment.seniority_signal)}</h3>
    <p>{escape(assessment.market_position)}</p>
    <p><strong>Evidence depth:</strong> {escape(assessment.evidence_depth)}</p>
    <p><strong>Strongest lane:</strong> {escape(assessment.strongest_lane)}</p>
    <h4>What supports this assessment</h4><ul>{_list(assessment.evidence_summary)}</ul>
    <h4>Differentiators</h4><ul>{_list(assessment.differentiators)}</ul>
    <h4>Signals to strengthen</h4><ul>{_list(assessment.watchouts)}</ul></section>
    <h2>Career directions</h2><section class="grid">{roles}</section>
    <h2>Job-market funnel</h2><section class="funnel">
    <div><b>{content.funnel.discovered}</b>discovered</div>
    <div><b>{content.funnel.filtered}</b>filtered</div>
    <div><b>{content.funnel.shortlisted}</b>shortlisted</div></section>
    <h2>Relevant opportunities</h2>{jobs}
    <h2>Your first four weeks</h2><section class="weeks">{weeks}</section>
    <h2>Methodology &amp; limitations</h2><ul>{_list(content.methodology + narrative.limitations)}</ul>
    </body></html>"""


# --- Private browser event loop ---------------------------------------
# Playwright starts Chromium with asyncio.create_subprocess_exec(), which only
# the Proactor loop implements on Windows. uvicorn chooses the server's loop
# itself and can install the Selector policy, which surfaces here as a bare
# NotImplementedError with an empty message. Rather than constrain how the app
# is launched, the browser runs on a Proactor loop owned by this module on its
# own daemon thread. Callers still `await render_pdf()` as normal.
#
# job_discovery_matching/internal/services/crawler_service.py carries the same
# machinery for the same reason; if a third module ever needs a browser, this
# belongs in src/core/ rather than being copied again.
_pdf_loop: asyncio.AbstractEventLoop | None = None
_pdf_loop_lock = threading.Lock()


def _ensure_pdf_loop() -> asyncio.AbstractEventLoop:
    global _pdf_loop
    with _pdf_loop_lock:
        if _pdf_loop is not None and _pdf_loop.is_running():
            return _pdf_loop
        _pdf_loop = (
            asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        )
        threading.Thread(target=_pdf_loop.run_forever, name="pdf-loop", daemon=True).start()
        return _pdf_loop


async def render_pdf(report: CareerReport) -> bytes:
    """Render the report to PDF bytes.

    Thin wrapper: the actual browser work is handed to the private Proactor
    loop above, then awaited from whatever loop the caller is running on.
    """
    return await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(_render_pdf_inner(report), _ensure_pdf_loop())
    )


async def _render_pdf_inner(report: CareerReport) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(render_html(report), wait_until="load")
        result = await page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=False,
            margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
        )
        await browser.close()
        return result
