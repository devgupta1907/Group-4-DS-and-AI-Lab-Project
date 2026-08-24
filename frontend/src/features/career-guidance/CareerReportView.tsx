import { useState } from 'react';

import styles from './CareerReportView.module.css';
import { CandidateProfileSection } from './components/CandidateProfileSection';
import { CareerDirectionsSection } from './components/CareerDirectionsSection';
import { MarketEvidenceSection } from './components/MarketEvidenceSection';
import { SummaryDashboard } from './components/SummaryDashboard';
import { WeeklyPlanSection } from './components/WeeklyPlanSection';
import type { CareerReport } from './types';

type Props = { report: CareerReport };

const TABS = ['Overview', 'Your profile', 'Career directions', 'Market evidence', 'Weekly plan'];

export function CareerReportView({ report }: Props) {
  const { content } = report;
  const [activeTab, setActiveTab] = useState(0);

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
        </div>
        <div className={styles.heroActions}>
          <span>Generated {new Date(report.created_at).toLocaleDateString()}</span>
          <a href={`/api/career-reports/${report.id}/pdf`}>Download report</a>
        </div>
      </header>

      {/* Real tab state now, not anchor links — clicking a tab shows only
          that section instead of scrolling the page to it. The dashboard
          (index 0) is the landing view; the other four are the same
          section components as before, unchanged, just rendered one at a
          time instead of all four stacked on one continuous scroll. */}
      <nav className={styles.contents} aria-label="Report sections">
        {TABS.map((label, index) => (
          <button
            type="button"
            key={label}
            className={index === activeTab ? styles.tabActive : styles.tab}
            aria-current={index === activeTab ? 'page' : undefined}
            onClick={() => setActiveTab(index)}
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === 0 && <SummaryDashboard report={report} onSelectSection={setActiveTab} />}
      {activeTab === 1 && <CandidateProfileSection report={report} />}
      {activeTab === 2 && <CareerDirectionsSection report={report} />}
      {activeTab === 3 && <MarketEvidenceSection report={report} />}
      {activeTab === 4 && <WeeklyPlanSection report={report} />}
    </article>
  );
}
