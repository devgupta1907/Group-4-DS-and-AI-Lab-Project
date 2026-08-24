import type { CareerReport, JobOpportunity } from '../types';

import styles from './MarketEvidenceSection.module.css';
import { SectionHeader } from './SectionHeader';

export function MarketEvidenceSection({ report }: { report: CareerReport }) {
  const { content } = report;
  const degraded = content.source_status?.job_status !== 'ok';

  // A 0/100 fit signal isn't "a weak match," it's the search-failure fallback
  // (unmatched recent postings shown when live discovery comes back empty) —
  // see job_discovery_matching/service.py:find_recent_postings. Surfacing it
  // as a career-relevant opportunity reads as a bug, not a low score, so it's
  // filtered here rather than in the pipeline: funnel counts (discovered /
  // filtered / shortlisted) stay the honest, unfiltered numbers from the run.
  const opportunities = content.opportunities.filter((job) => job.interview_probability > 0);

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
      <h3 className={styles.opportunityTitle}>Relevant live opportunities</h3>
      {opportunities.length
        ? <div className={styles.jobs}>{opportunities.map(
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
