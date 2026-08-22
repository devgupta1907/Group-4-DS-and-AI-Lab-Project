import { useEffect, useRef, useState, type ReactNode } from 'react';

import { Button } from '@shared/ui';

import { JobCard } from './components/JobCard';
import { JudgeConfirmationStep } from './components/JudgeConfirmationStep';
import { PreferencesPanel } from './components/PreferencesPanel';
import { QuerySelectionStep } from './components/QuerySelectionStep';
import styles from './JobDiscoveryChat.module.css';
import type { JobDiscoveryResult, SearchPreferences } from './types';
import type { JobDiscoveryPhase } from './useJobDiscovery';

const DEFAULT_PREFERENCES: SearchPreferences = {
  target_location: null,
  remote_only: false,
  min_salary_lpa: null,
};

type ChatTurn = {
  id: string;
  role: 'assistant' | 'user';
  content: ReactNode;
};

type JobDiscoveryChatProps = {
  phase: JobDiscoveryPhase;
  result: JobDiscoveryResult | null;
  error: string | null;
  onStart: (preferences: SearchPreferences) => void;
  onSubmitQueries: (selectedQueries: string[]) => void;
  onSubmitJudgeConfirmation: (proceed: boolean, selectedJobUrls?: string[]) => void;
  onRetry: () => void;
  onBack: () => void;
};

let turnCounter = 0;
const nextTurnId = () => `turn-${++turnCounter}`;

const GREETING =
  "Let's find some live openings. Want to narrow it down by location, salary, or remote-only — or should I just search broadly?";

function summarizePreferences(prefs: SearchPreferences): string {
  const parts: string[] = [];
  if (prefs.target_location) parts.push(prefs.target_location);
  if (prefs.remote_only) parts.push('remote only');
  if (prefs.min_salary_lpa) parts.push(`≥ ${prefs.min_salary_lpa} LPA`);
  return parts.length > 0 ? parts.join(' · ') : 'No specific preferences — search broadly';
}

/**
 * Same state machine as `JobDiscoveryPage` — `useJobDiscovery` is used
 * completely unchanged, including its two server-side pauses
 * (query_selection_gate, judge_confirmation_gate). This just lays the
 * same steps out as a conversation instead of a wizard: each pause
 * becomes an assistant "question" bubble with the real interactive step
 * component (PreferencesPanel / QuerySelectionStep / JudgeConfirmationStep)
 * embedded live underneath it. Once answered, that turn collapses into a
 * one-line summary bubble and the transcript scrolls on to the next
 * question — exactly the same requests fire either way, only the framing
 * changes.
 */
export function JobDiscoveryChat({
  phase,
  result,
  error,
  onStart,
  onSubmitQueries,
  onSubmitJudgeConfirmation,
  onRetry,
  onBack,
}: JobDiscoveryChatProps) {
  const [preferences, setPreferences] = useState<SearchPreferences>(DEFAULT_PREFERENCES);
  const [turns, setTurns] = useState<ChatTurn[]>(() => [
    { id: nextTurnId(), role: 'assistant', content: GREETING },
  ]);
  // Which phase the transcript has already announced — a ref, not state,
  // because appending to it must not itself trigger the effect that reads
  // it. Guards against announcing the same phase twice across re-renders.
  const announcedPhase = useRef<JobDiscoveryPhase>('idle');
  const bottomRef = useRef<HTMLDivElement>(null);

  const pushTurn = (role: ChatTurn['role'], content: ReactNode) => {
    setTurns((prev) => [...prev, { id: nextTurnId(), role, content }]);
  };

  useEffect(() => {
    if (announcedPhase.current === phase) return;
    announcedPhase.current = phase;

    if (phase === 'query_selection' && result?.generated_queries) {
      pushTurn(
        'assistant',
        `Here's what I'd search for — ${result.generated_queries.length} ${
          result.generated_queries.length === 1 ? 'query' : 'queries'
        }. Uncheck anything that doesn't look useful.`,
      );
    } else if (phase === 'judge_confirmation' && result) {
      pushTurn(
        'assistant',
        `Found ${result.top_jobs.length} ranked job${
          result.top_jobs.length === 1 ? '' : 's'
        }. Want me to score interview probability for any of them?`,
      );
    } else if (phase === 'failed') {
      pushTurn('assistant', error ?? result?.message ?? 'Something went wrong on that step.');
    } else if (phase === 'done' && result) {
      if (result.status === 'no_jobs' || result.status === 'no_candidates') {
        pushTurn('assistant', result.message || 'No jobs turned up this run — want to try different terms?');
      } else {
        pushTurn('assistant', <DoneSummary result={result} />);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pushTurn is stable in effect, intentionally excluded
  }, [phase, result, error]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns, phase]);

  const handleStart = () => {
    pushTurn('user', summarizePreferences(preferences));
    onStart(preferences);
  };

  const handleSubmitQueries = (selected: string[]) => {
    pushTurn('user', selected.length > 0 ? `Search with: ${selected.join(', ')}` : 'No queries selected');
    onSubmitQueries(selected);
  };

  const handleJudgeConfirmation = (proceed: boolean, selectedJobUrls?: string[]) => {
    pushTurn(
      'user',
      proceed
        ? selectedJobUrls?.length
          ? `Judge ${selectedJobUrls.length} selected job${selectedJobUrls.length === 1 ? '' : 's'}`
          : 'Judge all of them'
        : 'Stop here — skip the AI judge',
    );
    onSubmitJudgeConfirmation(proceed, selectedJobUrls);
  };

  const handleRetry = () => {
    setTurns([{ id: nextTurnId(), role: 'assistant', content: GREETING }]);
    announcedPhase.current = 'idle';
    onRetry();
  };

  const isBusy = phase === 'starting' || phase === 'selecting' || phase === 'confirming';
  const isDoneWithResults =
    phase === 'done' && result && result.status !== 'no_jobs' && result.status !== 'no_candidates';

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">Job discovery</p>
          <h1>Chat your way to live opportunities.</h1>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← Back to profile
        </Button>
      </header>

      <div className={styles.transcript}>
        {turns.map((turn) => (
          <div key={turn.id} className={turn.role === 'assistant' ? styles.assistantBubble : styles.userBubble}>
            {turn.content}
          </div>
        ))}

        {phase === 'idle' && (
          <div className={styles.liveBubble}>
            <PreferencesPanel
              value={preferences}
              onChange={setPreferences}
              onRun={handleStart}
              actionLabel="Search"
            />
          </div>
        )}

        {phase === 'query_selection' && result?.generated_queries && (
          <div className={styles.liveBubble}>
            <QuerySelectionStep
              generatedQueries={result.generated_queries}
              isSubmitting={false}
              onSubmit={handleSubmitQueries}
            />
          </div>
        )}

        {phase === 'judge_confirmation' && result && (
          <div className={styles.liveBubble}>
            <JudgeConfirmationStep
              rankedJobs={result.top_jobs}
              isSubmitting={false}
              onConfirm={handleJudgeConfirmation}
            />
          </div>
        )}

        {isBusy && (
          <div className={styles.assistantBubble}>
            <span className={styles.typing} aria-hidden="true"><i /><i /><i /></span>
          </div>
        )}

        {phase === 'failed' && (
          <div className={styles.liveBubble}>
            <Button variant="secondary" size="sm" onClick={handleRetry}>
              Start over
            </Button>
          </div>
        )}

        {isDoneWithResults && (
          <div className={styles.liveBubble}>
            <Button variant="secondary" size="sm" onClick={handleRetry}>
              Search again
            </Button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </section>
  );
}

function DoneSummary({ result }: { result: JobDiscoveryResult }) {
  return (
    <div>
      {result.status === 'hybrid_only' && (
        <p className={styles.statusNote}>Ranked by hybrid score only — you chose to skip the AI judge stage.</p>
      )}
      {result.status === 'degraded_no_llm' && (
        <p className={styles.statusNote}>The AI judge was unavailable this run — ranked by hybrid score only.</p>
      )}
      <p>Here&rsquo;s what I found, ranked for you:</p>
      <ul className={styles.list}>
        {result.top_jobs.map((ranked) => (
          <JobCard key={ranked.job.source_url || ranked.rank_position} ranked={ranked} />
        ))}
      </ul>
    </div>
  );
}