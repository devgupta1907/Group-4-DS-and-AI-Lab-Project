import { useState } from 'react';

import { Button, EmptyState } from '@shared/ui';

import { JobCard } from './components/JobCard';
import { JudgeConfirmationStep } from './components/JudgeConfirmationStep';
import { PreferencesPanel } from './components/PreferencesPanel';
import { QuerySelectionStep } from './components/QuerySelectionStep';
import styles from './JobDiscoveryPage.module.css';
import type { JobDiscoveryResult, SearchPreferences } from './types';
import type { JobDiscoveryPhase } from './useJobDiscovery';

const DEFAULT_PREFERENCES: SearchPreferences = {
  target_location: null,
  remote_only: false,
  min_salary_lpa: null,
};

type JobDiscoveryPageProps = {
  phase: JobDiscoveryPhase;
  result: JobDiscoveryResult | null;
  error: string | null;
  onStart: (preferences: SearchPreferences) => void;
  onSubmitQueries: (selectedQueries: string[]) => void;
  onSubmitJudgeConfirmation: (proceed: boolean, selectedJobUrls?: string[]) => void;
  onRetry: () => void;
  onBack: () => void;
};

/**
 * Job discovery, standalone — separate from the combined career report
 * flow. Walks the two server-side pauses in `useJobDiscovery` as distinct
 * steps: preferences -> pick which generated queries to run -> see
 * hybrid-ranked results and decide whether to spend the LLM judge call ->
 * final results.
 */
export function JobDiscoveryPage({
  phase,
  result,
  error,
  onStart,
  onSubmitQueries,
  onSubmitJudgeConfirmation,
  onRetry,
  onBack,
}: JobDiscoveryPageProps) {
  const [preferences, setPreferences] = useState<SearchPreferences>(DEFAULT_PREFERENCES);

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">Job discovery</p>
          <h1>Find live opportunities that match your profile.</h1>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← Back to profile
        </Button>
      </header>

      {phase === 'idle' && (
        <PreferencesPanel
          value={preferences}
          onChange={setPreferences}
          onRun={() => onStart(preferences)}
          actionLabel="Search for jobs"
        />
      )}

      {phase === 'starting' && (
        <div className={styles.loading}>
          <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
          <p>Working out what to search for…</p>
        </div>
      )}

      {phase === 'query_selection' && result?.generated_queries && (
        <QuerySelectionStep
          generatedQueries={result.generated_queries}
          isSubmitting={false}
          onSubmit={onSubmitQueries}
        />
      )}

      {phase === 'selecting' && (
        <div className={styles.loading}>
          <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
          <p>Searching, crawling and ranking matches…</p>
        </div>
      )}

      {phase === 'judge_confirmation' && result && (
        <JudgeConfirmationStep
          rankedJobs={result.top_jobs}
          isSubmitting={false}
          onConfirm={onSubmitJudgeConfirmation}
        />
      )}

      {phase === 'confirming' && (
        <div className={styles.loading}>
          <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
          <p>Scoring interview probability for each role…</p>
        </div>
      )}

      {phase === 'failed' && (
        <div className={styles.error}>
          <p>{error ?? result?.message ?? 'Something went wrong.'}</p>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Start over
          </Button>
        </div>
      )}

      {phase === 'done' && result && <DoneView result={result} onRetry={onRetry} />}
    </section>
  );
}

function DoneView({ result, onRetry }: { result: JobDiscoveryResult; onRetry: () => void }) {
  if (result.status === 'no_jobs' || result.status === 'no_candidates') {
    return (
      <EmptyState
        title="No jobs found this run"
        description={result.message || 'Try different search terms or a broader location.'}
      />
    );
  }

  return (
    <>
      {result.status === 'hybrid_only' && (
        <p className={styles.statusNote}>Ranked by hybrid score only — you chose to skip the AI judge stage.</p>
      )}
      {result.status === 'degraded_no_llm' && (
        <p className={styles.statusNote}>The AI judge was unavailable this run — ranked by hybrid score only.</p>
      )}
      <ul className={styles.list}>
        {result.top_jobs.map((ranked) => (
          <JobCard key={ranked.job.source_url || ranked.rank_position} ranked={ranked} />
        ))}
      </ul>
      <div className={styles.footer}>
        <Button variant="secondary" onClick={onRetry}>
          Search again
        </Button>
      </div>
    </>
  );
}
