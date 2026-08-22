import { Badge, Button, Card } from '@shared/ui';

import type { RankedJob } from '../types';
import styles from './JobCard.module.css';

type JobCardProps = {
  ranked: RankedJob;
  /** Only relevant pre-judge (`ranked.judge === null`). When given, shows
      a one-click "Judge only this job" action that runs the AI judge on
      just this job, regardless of the checkbox selection state above it —
      see JudgeConfirmationStep.tsx for why that indirection exists. */
  onJudgeOnly?: () => void;
  isSubmitting?: boolean;
};

const RECOMMENDATION_TONE = {
  'Apply Immediately': 'success',
  Apply: 'accent',
  Skip: 'neutral',
} as const;

/**
 * Renders one ranked job either way: `ranked.judge === null` (hybrid-only,
 * before or in place of the judge stage) shows just the hybrid score;
 * once judged, the interview-probability/strengths/gaps/recommendation
 * replace it. Same card either way so switching from the
 * judge_confirmation preview to the final result doesn't re-layout.
 */
export function JobCard({ ranked, onJudgeOnly, isSubmitting }: JobCardProps) {
  const { job, judge } = ranked;

  return (
    <li>
      <Card
        title={
          <a href={job.source_url} target="_blank" rel="noreferrer noopener">
            {job.title || 'Untitled role'}
          </a>
        }
        description={[job.company, job.location].filter(Boolean).join(' · ')}
        actions={
          judge ? (
            <Badge tone={RECOMMENDATION_TONE[judge.recommendation]}>{judge.recommendation}</Badge>
          ) : (
            <Badge tone="neutral">Hybrid score {Math.round(ranked.hybrid_score * 100)}%</Badge>
          )
        }
      >
        {!judge && onJudgeOnly && (
          <Button
            variant="ghost"
            size="sm"
            className={styles.judgeOnlyButton}
            onClick={onJudgeOnly}
            disabled={isSubmitting}
          >
            Judge only this job
          </Button>
        )}
        {judge ? (
          <>
            <p className={styles.reason}>{judge.one_line_reason}</p>
            <p className={styles.probability}>
              Estimated interview probability: <b>{judge.interview_probability}%</b>
            </p>
            {judge.strengths.length > 0 && (
              <div className={styles.column}>
                <span className={styles.columnLabel}>Strengths</span>
                <ul>{judge.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {judge.gaps.length > 0 && (
              <div className={styles.column}>
                <span className={styles.columnLabel}>Gaps</span>
                <ul>{judge.gaps.map((g) => <li key={g}>{g}</li>)}</ul>
              </div>
            )}
            {!judge.used_llm_judge && (
              <p className={styles.degradedNote}>LLM judge was unavailable — ranked by hybrid score only.</p>
            )}
          </>
        ) : (
          <p className={styles.hybridNote}>
            Ranked by keyword and semantic match to your profile. Run the AI judge for an
            interview-probability estimate and a strengths/gaps breakdown.
          </p>
        )}
      </Card>
    </li>
  );
}