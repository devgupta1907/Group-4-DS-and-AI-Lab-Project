import type { CareerReport } from '../types';

import styles from './CandidateProfileSection.module.css';
import { SectionHeader } from './SectionHeader';

type Props = { report: CareerReport };

export function CandidateProfileSection({ report }: Props) {
  const { content } = report;
  const assessment = profileView(content);

  return (
    <section id="section-1">
      <SectionHeader
        number="01"
        title="How your profile is positioned today"
        description="An interpretation of your current market signal—not a repetition of your resume."
      />
      <article className={styles.positioning}>
        <span>Current market position</span>
        <h3>{assessment.seniority}</h3>
        <p>{assessment.position}</p>
      </article>
      <div className={styles.signals}>
        <Signal label="Evidence depth" value={assessment.depth} />
        <Signal label="Strongest market lane" value={assessment.lane} />
        <Signal label="Development focus" value={content.narrative.development_priority} />
      </div>
      <EvidenceList
        title="Signals to strengthen or verify"
        items={[...assessment.watchouts, ...assessment.limitations]}
        muted
      />
    </section>
  );
}

function profileView(content: CareerReport['content']) {
  const assessment = content.narrative.profile_assessment ?? defaultAssessment(content);
  const snapshot = content.profile_snapshot;
  return {
    seniority: assessment.seniority_signal,
    position: assessment.market_position,
    depth: assessment.evidence_depth,
    lane: assessment.strongest_lane,
    watchouts: assessment.watchouts,
    limitations: snapshot?.data_limitations ?? [],
  };
}

function defaultAssessment(content: CareerReport['content']) {
  return {
    seniority_signal: content.profile_snapshot?.current_positioning ?? content.job_titles[0] ?? 'Open profile',
    market_position: content.narrative.executive_summary[0] ?? '',
    evidence_depth: 'Limited',
    strongest_lane: content.narrative.strongest_direction,
    watchouts: [] as string[],
  };
}

function Signal({ label, value }: { label: string; value: string }) {
  return <article><span>{label}</span><strong>{value}</strong></article>;
}

function EvidenceList({ title, items, muted = false }: { title: string; items: string[]; muted?: boolean }) {
  if (!items.length) return null;
  return (
    <article className={muted ? styles.watchouts : styles.evidence}>
      <h3>{title}</h3>
      <ol>{items.map((item) => <li key={item}>{item}</li>)}</ol>
    </article>
  );
}
