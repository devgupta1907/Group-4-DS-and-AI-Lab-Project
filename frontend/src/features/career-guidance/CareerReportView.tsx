import styles from './CareerReportView.module.css';
import { CandidateProfileSection } from './components/CandidateProfileSection';
import { CareerDirectionsSection } from './components/CareerDirectionsSection';
import { MarketEvidenceSection } from './components/MarketEvidenceSection';
import { WeeklyPlanSection } from './components/WeeklyPlanSection';
import type { CareerReport } from './types';

type Props = { report: CareerReport };

export function CareerReportView({ report }: Props) {
  const { content } = report;

  return (
    <article className={styles.report}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>Career guidance report</p>
          <h1>{content.candidate_name ?? 'Your career profile'}</h1>
          <p className={styles.positioning}>
            {content.profile_snapshot?.current_positioning
              || content.job_titles.join(' · ')
              || 'Professional profile'}
          </p>
          <p className={styles.intro}>{content.narrative.headline}</p>
        </div>
        <div className={styles.heroActions}>
          <span>Generated {new Date(report.created_at).toLocaleDateString()}</span>
          <a href={`/api/career-reports/${report.id}/pdf`}>Download report</a>
        </div>
      </header>

      <nav className={styles.contents} aria-label="Report contents">
        {['Your profile', 'Career directions', 'Market evidence', 'Weekly plan'].map(
          (label, index) => <a href={`#section-${index + 1}`} key={label}>{label}</a>,
        )}
      </nav>

      <CandidateProfileSection report={report} />
      <CareerDirectionsSection report={report} />
      <MarketEvidenceSection report={report} />
      <WeeklyPlanSection report={report} />
    </article>
  );
}
