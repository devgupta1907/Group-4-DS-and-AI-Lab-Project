import type { CareerReport } from '../types';

import styles from './SummaryDashboard.module.css';

const readinessLabel = {
  ready_now: 'Ready now',
  near_term_stretch: 'Within reach',
  longer_term_transition: 'Longer-term option',
};

type Props = { report: CareerReport; onSelectSection: (index: number) => void };

/**
 * Landing view when a report opens — a five-second summary, not a fifth
 * section to read in full. Each card below links into the actual section
 * (CareerReportView owns the tab index), so this never duplicates content
 * that's already shown in full elsewhere — it previews and points, using
 * fields (narrative.executive_summary, strongest role, live-opportunity
 * count) that no other section currently surfaces at this level.
 */
export function SummaryDashboard({ report, onSelectSection }: Props) {
  const { content } = report;
  const { narrative } = content;
  const topRole = narrative.roles[0];

  // Same filter MarketEvidenceSection uses — a 0/100 fit signal is the
  // search-failure fallback (unmatched recent postings shown when live
  // discovery comes back empty), not a real opportunity. Counting it here
  // would show a number this dashboard can't back up when the user clicks
  // through to Market evidence and sees fewer cards than promised.
  const liveOpportunities = content.opportunities.filter((job) => job.interview_probability > 0);

  return (
    <div className={styles.dashboard}>
      {narrative.executive_summary.length > 0 && (
        <section className={styles.summary}>
          <h2>At a glance</h2>
          <ul>
            {narrative.executive_summary.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </section>
      )}

      <div className={styles.row}>
        {topRole && (
          <article className={styles.topRole}>
            <span className={styles.eyebrow}>Strongest direction</span>
            <h3>{topRole.title}</h3>
            <span className={styles.readiness}>{readinessLabel[topRole.readiness]}</span>
            <p>{topRole.rationale}</p>
            <button type="button" onClick={() => onSelectSection(2)}>
              See all {narrative.roles.length} direction{narrative.roles.length === 1 ? '' : 's'} →
            </button>
          </article>
        )}

        <article className={styles.stats}>
          <div><strong>{narrative.roles.length}</strong><span>Role directions assessed</span></div>
          <div><strong>{liveOpportunities.length}</strong><span>Live opportunities found</span></div>
        </article>
      </div>

      <div className={styles.cards}>
        <button type="button" className={styles.navCard} onClick={() => onSelectSection(1)}>
          <span className={styles.navLabel}>Your profile</span>
          <p>{content.profile_snapshot?.current_positioning
            || content.job_titles.join(' · ')
            || 'Profile overview'}</p>
        </button>

        <button type="button" className={styles.navCard} onClick={() => onSelectSection(2)}>
          <span className={styles.navLabel}>Career directions</span>
          <p>{narrative.roles.length} direction{narrative.roles.length === 1 ? '' : 's'}, ranked by
            evidence and readiness.</p>
        </button>

        <button type="button" className={styles.navCard} onClick={() => onSelectSection(3)}>
          <span className={styles.navLabel}>Market evidence</span>
          <p>{liveOpportunities.length
            ? `${liveOpportunities.length} live opportunit${liveOpportunities.length === 1 ? 'y' : 'ies'} matched to your profile.`
            : 'No reliable live opportunities survived this run.'}</p>
        </button>

        <button type="button" className={styles.navCard} onClick={() => onSelectSection(4)}>
          <span className={styles.navLabel}>Weekly plan</span>
          <p>{narrative.weekly_plan?.length
            ? `A ${narrative.weekly_plan.length}-week plan, starting with "${narrative.weekly_plan[0].theme}."`
            : 'Prioritized next actions.'}</p>
        </button>
      </div>
    </div>
  );
}
