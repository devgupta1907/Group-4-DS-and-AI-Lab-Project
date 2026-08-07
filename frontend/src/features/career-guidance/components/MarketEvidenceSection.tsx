import type { CareerReport, JobOpportunity } from '../types';

import styles from './MarketEvidenceSection.module.css';
import { SectionHeader } from './SectionHeader';

export function MarketEvidenceSection({ report }: { report: CareerReport }) {
  const { content } = report;
  const max = Math.max(content.funnel.discovered, 1);
  const degraded = content.source_status?.job_status !== 'ok';

  return (
    <section id="section-3">
      <SectionHeader
        number="03"
        title="What the current market returned"
        description="Live search evidence is kept separate from career guidance so limited job-board access never masquerades as a weak profile."
      />
      {degraded && (
        <div className={styles.notice}>
          <strong>Partial market coverage</strong>
          <p>{content.source_status?.job_message || 'The live search returned limited usable job pages.'}</p>
        </div>
      )}
      <div className={styles.marketGrid}>
        <article className={styles.funnel}>
          <h3>Search funnel</h3>
          {Object.entries(content.funnel).map(([label, value]) => (
            <div key={label}>
              <header><span>{label}</span><strong>{value}</strong></header>
              <i><b style={{ width: `${(value / max) * 100}%` }} /></i>
            </div>
          ))}
        </article>
        <article className={styles.unlocks}>
          <h3>Repeated skill signals</h3>
          {content.skill_unlocks.length ? content.skill_unlocks.map((skill) => (
            <div key={skill.skill}>
              <strong>{skill.skill}</strong>
              <span>{skill.evidence_count} jobs · {skill.category.replace('_', ' ')}</span>
              <small>May unlock: {skill.unlocks.join(', ')}</small>
            </div>
          )) : <p>No skill gap appeared across multiple shortlisted jobs. This is not evidence that no gaps exist.</p>}
        </article>
      </div>
      <h3 className={styles.opportunityTitle}>Relevant live opportunities</h3>
      {content.opportunities.length
        ? <div className={styles.jobs}>{content.opportunities.map(
          (job) => <OpportunityCard job={job} key={job.source_url} />,
        )}</div>
        : <div className={styles.empty}>
          <strong>No reliable live opportunities survived this run.</strong>
          <p>Career directions above remain valid; rerun discovery later or use the recommended role titles in a targeted search.</p>
        </div>}
    </section>
  );
}

function OpportunityCard({ job }: { job: JobOpportunity }) {
  return (
    <article className={styles.job}>
      <header>
        <div><span>{job.recommendation}</span><h4>{job.title}</h4>
          <p>{[job.company, job.location].filter(Boolean).join(' · ')}</p></div>
        <strong>{job.interview_probability}<small>/100 fit signal</small></strong>
      </header>
      <p>{job.reason}</p>
      <div><b>Strengths:</b> {job.strengths.join(', ') || 'Not identified'}
        <br /><b>Gaps:</b> {job.gaps.join(', ') || 'No repeated gap identified'}</div>
      <a href={job.source_url} target="_blank" rel="noreferrer">Open original posting ↗</a>
    </article>
  );
}
