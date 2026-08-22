import { useMemo, useState } from 'react';

import { Button } from '@shared/ui';

import type { RankedJob } from '../types';

import { JobCard } from './JobCard';
import styles from './JudgeConfirmationStep.module.css';

type JudgeConfirmationStepProps = {
  rankedJobs: RankedJob[];
  isSubmitting: boolean;
  /** `selectedJobUrls` is the subset the user checked — omitted/empty
      when everything is selected, so the server judges the full list
      exactly as before. */
  onConfirm: (proceed: boolean, selectedJobUrls?: string[]) => void;
};

/**
 * The second pause: hybrid ranking (BM25 + embedding similarity, zero LLM
 * calls) is done and already persisted server-side — these ARE the real
 * ranked jobs, not a preview. The user picks which of these to actually
 * spend the batched LLM judge call on (all are checked by default), then
 * either runs the judge over just that selection or stops here.
 *
 * Each job also gets its own "Judge only this job" button (see JobCard),
 * which calls `onConfirm` directly with that one job's URL — independent
 * of the checkbox `Set` below. That's deliberate: a job's title is just a
 * plain link (opens the posting in a new tab), so clicking it never
 * touches the selection state, and defaulting every checkbox to "checked"
 * means one job's checkbox alone doesn't isolate it either — you'd have to
 * deselect everything else first. The per-job button is the actual
 * single-job action; the checkboxes are for picking an arbitrary subset.
 */
export function JudgeConfirmationStep({ rankedJobs, isSubmitting, onConfirm }: JudgeConfirmationStepProps) {
  const jobKey = (ranked: RankedJob) => ranked.job.source_url || String(ranked.rank_position);

  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(rankedJobs.map(jobKey)),
  );

  const allSelected = selected.size === rankedJobs.length;
  const selectedUrls = useMemo(
    () =>
      rankedJobs
        .filter((ranked) => selected.has(jobKey(ranked)))
        .map((ranked) => ranked.job.source_url)
        .filter(Boolean),
    [rankedJobs, selected],
  );

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(rankedJobs.map(jobKey)));
  };

  const handleRunJudge = () => {
    // Sending undefined when everything is selected keeps the request
    // identical to "judge all" for a client that never touches the
    // checkboxes — the backend treats missing/empty the same way.
    onConfirm(true, allSelected ? undefined : selectedUrls);
  };

  const handleJudgeOnly = (url: string) => {
    onConfirm(true, [url]);
  };

  return (
    <div className={styles.step}>
      <p className="eyebrow">Step 2 of 2 · Hybrid-ranked results</p>
      <h2> {rankedJobs.length} job{rankedJobs.length === 1 ? '' : 's'} ranked by relevance.</h2>
      <p className={styles.hint}>
        Ranked by keyword and semantic match so far. Pick which ones to run the AI judge on for an
        interview-probability estimate and a strengths/gaps breakdown — or stop here with what you
        already have.
      </p>

      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => onConfirm(false)} disabled={isSubmitting}>
          Stop here
        </Button>
        <Button variant="primary" onClick={handleRunJudge} disabled={isSubmitting || selected.size === 0}>
          {isSubmitting
            ? 'Judging…'
            : `Run AI judge on ${selected.size} selected`}
        </Button>
      </div>

      <div className={styles.selectRow}>
        <button type="button" className={styles.selectAll} onClick={toggleAll} disabled={isSubmitting}>
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
        <span className={styles.selectedCount}>
          {selected.size} of {rankedJobs.length} selected
        </span>
      </div>

      {/* JobCard renders its own <li>, so this is a <div> list rather than
          <ul> — a checkbox needs to sit beside each card, not inside the
          list-item JobCard already owns. */}
      <div className={styles.list}>
        {rankedJobs.map((ranked) => {
          const key = jobKey(ranked);
          const url = ranked.job.source_url;
          return (
            <div key={key} className={styles.jobRow}>
              <input
                type="checkbox"
                className={styles.jobCheckbox}
                checked={selected.has(key)}
                onChange={() => toggle(key)}
                disabled={isSubmitting}
                aria-label={`Include ${ranked.job.title || 'this job'} in the AI judge run`}
              />
              <ul className={styles.jobCheckboxLabel}>
                <JobCard
                  ranked={ranked}
                  isSubmitting={isSubmitting}
                  onJudgeOnly={url ? () => handleJudgeOnly(url) : undefined}
                />
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}