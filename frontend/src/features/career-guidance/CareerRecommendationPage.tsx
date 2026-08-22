import { Badge, Button, Card, EmptyState } from '@shared/ui';

import type { CareerRecommendationStatus } from './useCareerRecommendation';
import styles from './CareerRecommendationPage.module.css';
import type { CareerRecommendation, CareerResult } from './types';

type CareerRecommendationPageProps = {
  status: CareerRecommendationStatus;
  result: CareerResult | null;
  error: string | null;
  /** occupation_uris of every recommendation the candidate has picked so
      far — a candidate can be open to more than one direction. */
  selectedUris: string[];
  onRetry: () => void;
  onBack: () => void;
  /** Toggles one recommendation's pick and persists the resulting set
      against this run (POST .../select) so Job Discovery can read it
      back and search on exactly those roles. */
  onToggleOccupation: (occupationUri: string) => void;
  /** Hands the picked occupation(s) forward as a starting point for Job
      Discovery, without re-running anything — query_generator already
      folds career_recommendation's saved selection (or, absent one, its
      top-2 titles) into its own prompt server-side (see backend/
      job_discovery_matching/service.py), so this is a navigation step,
      not a required one: the candidate can proceed without picking. */
  onFindJobs: () => void;
};

const CONFIDENCE_TONE = { high: 'success', medium: 'warning', low: 'neutral' } as const;

/**
 * Standalone career recommendation — retrieve/re-rank/explain against the
 * ESCO taxonomy, nothing else. Separate from the combined career report
 * flow (`ReportPage` in App.tsx): this page only ever calls
 * `POST /api/career/recommend` and shows exactly what it returns.
 */
export function CareerRecommendationPage({
  status,
  result,
  error,
  selectedUris,
  onRetry,
  onBack,
  onToggleOccupation,
  onFindJobs,
}: CareerRecommendationPageProps) {
  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">Career recommendation</p>
          <h1>Occupations matched to your profile.</h1>
          <p>Ranked against the ESCO taxonomy, with the evidence behind each match.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← Back to profile
        </Button>
      </header>

      {status === 'loading' && (
        <div className={styles.loading}>
          <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
          <p>Matching your profile against relevant occupations…</p>
        </div>
      )}

      {status === 'failed' && (
        <div className={styles.error}>
          <p>{error ?? 'Something went wrong generating recommendations.'}</p>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}

      {status === 'complete' && result && (
        <>
          {result.recommendations.length === 0 ? (
            <EmptyState
              title="No strong matches found"
              description={result.message || 'Try adding more detail to your resume and re-running.'}
            />
          ) : (
            <>
              <p className={styles.hint}>
                Pick every role you&rsquo;d want to pursue and we&rsquo;ll focus the job search on
                them — or skip ahead and we&rsquo;ll use the top matches instead.
              </p>
              <ul className={styles.list}>
                {result.recommendations.map((rec) => (
                  <RecommendationCard
                    key={rec.occupation_uri}
                    recommendation={rec}
                    selected={selectedUris.includes(rec.occupation_uri)}
                    onToggle={onToggleOccupation}
                  />
                ))}
              </ul>
            </>
          )}

          {error && <div className={styles.error}><p>{error}</p></div>}

          <footer className={styles.footer}>
            <Button variant="secondary" onClick={onRetry}>
              Re-run
            </Button>
            <Button variant="primary" onClick={onFindJobs}>
              {selectedUris.length > 0
                ? `Find jobs for ${selectedUris.length === 1 ? 'selected role' : `${selectedUris.length} selected roles`}`
                : 'Find jobs for these roles'}{' '}
              <span aria-hidden="true">→</span>
            </Button>
          </footer>
        </>
      )}
    </section>
  );
}

function RecommendationCard({
  recommendation,
  selected,
  onToggle,
}: {
  recommendation: CareerRecommendation;
  selected: boolean;
  onToggle: (occupationUri: string) => void;
}) {
  return (
    <li className={selected ? styles.selected : undefined}>
      <Card
        title={recommendation.occupation_title}
        actions={
          <div className={styles.cardActions}>
            <Badge tone={CONFIDENCE_TONE[recommendation.confidence]}>{recommendation.confidence} confidence</Badge>
            <Button
              variant={selected ? 'primary' : 'secondary'}
              size="sm"
              aria-pressed={selected}
              onClick={() => onToggle(recommendation.occupation_uri)}
            >
              {selected ? 'Selected ✓' : 'Select'}
            </Button>
          </div>
        }
      >
        <p className={styles.explanation}>{recommendation.explanation}</p>
        {recommendation.matched_evidence.length > 0 && (
          <ul className={styles.evidence}>
            {recommendation.matched_evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </Card>
    </li>
  );
}
