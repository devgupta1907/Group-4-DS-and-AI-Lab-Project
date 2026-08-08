"""Server-rendered PDF for a saved report snapshot."""

# ruff: noqa: E501 -- CSS is intentionally kept as a compact self-contained template.

from __future__ import annotations

from html import escape

from src.career_report.schemas import CareerReport


def _list(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def render_html(report: CareerReport) -> str:
    content = report.content
    narrative = content.narrative
    assessment = narrative.profile_assessment
    roles = "".join(
        f"""<article class="card"><span>{escape(role.readiness.replace("_", " "))}</span>
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
    @page {{ size:A4; margin:16mm; @bottom-right {{content:"Career Guidance · " counter(page)}} }}
    *{{box-sizing:border-box}} body{{font-family:Arial,sans-serif;color:#111428;background:#fff;font-size:10pt;line-height:1.45}}
    h1,h2,h3{{margin:0 0 8px}} h1{{font-size:30pt;line-height:1.05}} h2{{font-size:18pt;margin-top:24px}}
    .hero{{background:#111428;color:#f7f3e9;padding:28px;border-radius:18px;border-bottom:8px solid #c8ff61}}
    .kicker,span{{color:#7259ff;text-transform:uppercase;font-weight:bold;letter-spacing:.08em;font-size:8pt}}
    .summary,.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
    .summary p,.card,.job,.week,.assessment{{border:1px solid #d9d6e2;border-radius:12px;padding:12px;break-inside:avoid}}
    .card strong{{color:#7259ff}} .job{{display:grid;grid-template-columns:1fr auto;gap:5px;margin-bottom:8px}}
    .job p,.job a{{grid-column:1/-1;margin:0}} .job b{{font-size:17pt;color:#7259ff}}
    a{{color:#4933c8;word-break:break-all}} ul{{padding-left:16px}} small{{color:#62657a}}
    .funnel{{display:flex;gap:8px}} .funnel div{{flex:1;padding:12px;background:#f3f0ff;border-radius:10px;text-align:center}}
    .funnel b{{display:block;font-size:20pt}} .weeks{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
    .assessment{{border-left:5px solid #7259ff}} h4{{margin:10px 0 3px}}
    </style></head><body>
    <section class="hero"><p class="kicker">Career Intelligence Report</p>
    <h1>{escape(narrative.headline)}</h1><p>{escape(content.candidate_name or "Candidate")} ·
    {escape(content.candidate_location or "Location not supplied")}</p></section>
    <h2>Executive guidance</h2><section class="summary">
    {"".join(f"<p>{escape(item)}</p>" for item in narrative.executive_summary)}</section>
    <h2>Your professional profile today</h2>
    <section class="assessment"><h3>{escape(assessment.seniority_signal)}</h3>
    <p>{escape(assessment.market_position)}</p><p><strong>Evidence depth:</strong> {escape(assessment.evidence_depth)}</p>
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
    <h2>Methodology & limitations</h2><ul>{_list(content.methodology + narrative.limitations)}</ul>
    </body></html>"""


async def render_pdf(report: CareerReport) -> bytes:
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
