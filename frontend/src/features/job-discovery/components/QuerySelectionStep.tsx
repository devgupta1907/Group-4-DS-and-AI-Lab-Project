import { useState } from 'react';

import { Button } from '@shared/ui';

import styles from './QuerySelectionStep.module.css';

type QuerySelectionStepProps = {
  generatedQueries: string[];
  isSubmitting: boolean;
  onSubmit: (selectedQueries: string[]) => void;
};

/**
 * The first pause: query_generator produced these queries, but nothing has
 * been searched yet — no Adzuna call, no SearXNG call, no crawl4ai fetch.
 * All queries start checked (the default is "search everything generated"),
 * the candidate can uncheck any they don't want spent on.
 */
export function QuerySelectionStep({ generatedQueries, isSubmitting, onSubmit }: QuerySelectionStepProps) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(generatedQueries));

  const toggle = (query: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(query)) next.delete(query);
      else next.add(query);
      return next;
    });
  };

  return (
    <div className={styles.step}>
      <p className="eyebrow">Step 1 of 2 · Choose what to search</p>
      <h2>These are the searches we&rsquo;d run for you.</h2>
      <p className={styles.hint}>
        Uncheck anything that doesn&rsquo;t look useful — nothing is searched until you confirm.
      </p>

      <ul className={styles.list}>
        {generatedQueries.map((query) => (
          <li key={query}>
            <label className={styles.option}>
              <input
                type="checkbox"
                checked={selected.has(query)}
                onChange={() => toggle(query)}
              />
              <span>{query}</span>
            </label>
          </li>
        ))}
      </ul>

      <Button
        variant="primary"
        onClick={() => onSubmit([...selected])}
        disabled={isSubmitting || selected.size === 0}
      >
        {isSubmitting ? 'Searching…' : `Search with ${selected.size} ${selected.size === 1 ? 'query' : 'queries'}`}
      </Button>
    </div>
  );
}
