import { useCallback, useEffect, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { recommendOccupations, selectOccupations, type CareerResult } from './careerApi';
import { DirectionChoiceStep } from './components/DirectionChoiceStep';
import { JobDiscoveryChat } from './JobDiscoveryChat';
import styles from './RapidSearchFlow.module.css';
import type { SearchPreferences } from './types';
import { useJobDiscovery } from './useJobDiscovery';

type Props = {
  profileId: string;
  onBack: () => void;
};

type Stage = 'recommending' | 'choosing' | 'searching' | 'failed';

/**
 * Rapid Search, end to end: recommend directions -> user selects -> chat
 * job discovery.
 *
 * The selection is persisted server-side (POST
 * /career/recommendations/{run_id}/select) rather than passed to the
 * search call, because job discovery reads it off the recommendation run
 * itself when seeding `target_roles` — see
 * job_discovery_matching/service.py. That is also why the order matters:
 * the selection must be saved before `searchJobs` is called.
 *
 * This uses the same pipeline, gates and nodes as the report flow. The
 * difference is only that the report auto-resumes through the pipeline's
 * two interrupts silently, while this exposes them to the user.
 */
export function RapidSearchFlow({ profileId, onBack }: Props) {
  const [stage, setStage] = useState<Stage>('recommending');
  const [recommendations, setRecommendations] = useState<CareerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const jobs = useJobDiscovery();

  const loadRecommendations = useCallback(async () => {
    setStage('recommending');
    setError(null);
    try {
      setRecommendations(await recommendOccupations(profileId));
      setStage('choosing');
    } catch (cause) {
      setError(toApiError(cause).message);
      setStage('failed');
    }
  }, [profileId]);

  useEffect(() => {
    void loadRecommendations();
  }, [loadRecommendations]);

  const confirmDirections = useCallback(
    async (selectedUris: string[]) => {
      // Move on even if saving the selection fails: discovery still works
      // without it (it falls back to the top 2 recommendations), and
      // blocking the whole search on a non-essential write would be worse
      // than searching slightly broader than asked.
      try {
        if (recommendations?.run_id) {
          await selectOccupations(recommendations.run_id, selectedUris);
        }
      } catch {
        // Intentionally swallowed — see above.
      }
      setStage('searching');
    },
    [recommendations],
  );

  const startSearch = useCallback(
    (preferences: SearchPreferences) => {
      void jobs.start(profileId, preferences);
    },
    [jobs, profileId],
  );

  const retrySearch = useCallback(() => {
    void jobs.start(profileId, {
      target_locations: [],
      remote_only: false,
      min_salary_lpa: null,
    });
  }, [jobs, profileId]);

  if (stage === 'recommending') {
    return (
      <section className={styles.loading}>
        <p className="eyebrow">Rapid search</p>
        <h2>Matching your profile to career directions…</h2>
        <p>This only takes a moment.</p>
      </section>
    );
  }

  if (stage === 'failed') {
    return (
      <section className={styles.loading}>
        <p className="eyebrow">Rapid search</p>
        <h2>Couldn&apos;t load career directions</h2>
        <p>{error}</p>
        <div className={styles.failedActions}>
          <button type="button" className={styles.secondary} onClick={onBack}>Back</button>
          <button type="button" className="primary-action" onClick={() => void loadRecommendations()}>
            Try again
          </button>
        </div>
      </section>
    );
  }

  if (stage === 'choosing' && recommendations) {
    return (
      <DirectionChoiceStep
        result={recommendations}
        onConfirm={(uris) => void confirmDirections(uris)}
        onBack={onBack}
      />
    );
  }

  return (
    <JobDiscoveryChat
      phase={jobs.phase}
      result={jobs.result}
      error={jobs.error}
      onStart={startSearch}
      onSubmitQueries={jobs.submitQueries}
      onSubmitJudgeConfirmation={jobs.submitJudgeConfirmation}
      onRetry={retrySearch}
      onBack={onBack}
    />
  );
}
