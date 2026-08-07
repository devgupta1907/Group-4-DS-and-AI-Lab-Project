import type { CareerReport } from './types';

type Props = { report: CareerReport };

const readinessLabel = {
  ready_now: 'Ready now',
  near_term_stretch: 'Within reach',
  longer_term_transition: 'Longer-term move',
};

export function CareerReportView({ report }: Props) {
  const { content } = report;
  const maxFunnel = Math.max(content.funnel.discovered, 1);

  return (
    <article className="report">
      <header className="report-hero">
        <div>
          <p className="eyebrow">Your career intelligence report</p>
          <h1>{content.narrative.headline}</h1>
          <p>{content.candidate_name ?? 'Candidate'} · {content.candidate_location ?? 'Location open'}</p>
        </div>
        <a className="download" href={`/api/career-reports/${report.id}/pdf`}>
          Download PDF ↓
        </a>
      </header>

      <section className="summary-strip">
        {content.narrative.executive_summary.map((item, index) => (
          <div key={item}><span>0{index + 1}</span><p>{item}</p></div>
        ))}
      </section>

      <ReportHeading number="01" title="Directions worth exploring" />
      <section className="role-grid">
        {content.narrative.roles.map((role) => (
          <article className="role-card" key={role.title}>
            <div className="role-meta">
              <span>{readinessLabel[role.readiness]}</span>
              <span>{role.confidence} confidence</span>
            </div>
            <h3>{role.title}</h3>
            <p>{role.rationale}</p>
            <div className="chips">
              {role.evidence.map((item) => <span key={item}>{item}</span>)}
            </div>
            <strong>Next move</strong><p>{role.next_step}</p>
          </article>
        ))}
      </section>

      <ReportHeading number="02" title="What the market returned" />
      <section className="data-grid">
        <article className="chart-card">
          <h3>Search funnel</h3>
          {Object.entries(content.funnel).map(([label, value]) => (
            <div className="funnel-row" key={label}>
              <span>{label}</span>
              <div><i style={{ width: `${Math.max((value / maxFunnel) * 100, 4)}%` }} /></div>
              <b>{value}</b>
            </div>
          ))}
        </article>
        <article className="chart-card">
          <h3>Skill unlocks</h3>
          {content.skill_unlocks.length ? content.skill_unlocks.map((skill) => (
            <div className="skill-row" key={skill.skill}>
              <div><b>{skill.skill}</b><small>{skill.category.replace('_', ' ')}</small></div>
              <span>{skill.evidence_count}× recurring</span>
            </div>
          )) : <p className="muted">No skill gap repeated across multiple jobs.</p>}
        </article>
      </section>

      <ReportHeading number="03" title="Live opportunities" />
      <OpportunityList opportunities={content.opportunities} />

      <ReportHeading number="04" title="Your next 90 days" />
      <section className="action-grid">
        {content.narrative.actions.map((action) => (
          <article key={action.horizon}><span>{action.horizon.replace('_', ' ')}</span>
            <h3>{action.action}</h3><p>{action.based_on}</p></article>
        ))}
      </section>
    </article>
  );
}

function ReportHeading({ number, title }: { number: string; title: string }) {
  return <div className="report-heading"><span>{number}</span><h2>{title}</h2></div>;
}

function OpportunityList({ opportunities }: { opportunities: CareerReport['content']['opportunities'] }) {
  return <section className="job-list">{opportunities.map((job) => (
    <article className="job-card" key={job.source_url}>
      <div><span>{job.recommendation}</span><h3>{job.title}</h3>
        <p>{job.company} · {job.location}</p></div>
      <div className="probability"><b>{job.interview_probability}%</b>
        <small>guidance signal</small></div>
      <p>{job.reason}</p>
      <a href={job.source_url} target="_blank" rel="noreferrer">View opportunity ↗</a>
    </article>
  ))}</section>;
}
