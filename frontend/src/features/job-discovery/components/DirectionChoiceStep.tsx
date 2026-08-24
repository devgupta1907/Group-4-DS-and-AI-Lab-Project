import { useState } from 'react';

import type { CareerRecommendation, CareerResult } from '../careerApi';

import styles from './DirectionChoiceStep.module.css';

type Props = {
  result: CareerResult;
  onConfirm: (selectedUris: string[]) => void;
  onBack: () => void;
};

/**
 * Rapid Search step 1: the user confirms which recommended directions to
 * actually search for.
 *
 * Everything here is model output — the user filters the system's
 * evidence-based recommendations rather than typing a role of their own.
 * That is deliberate: job search stays anchored to what the profile
 * actually supports.
 *
 * All directions start selected, so proceeding untouched is the fast path
 * and nobody is forced to choose.
 */
export function DirectionChoiceStep({ result, onConfirm, onBack }: Props) {
  const recommendations = result.recommendations ?? [];
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(recommendations.map((r) => r.occupation_uri)),
  );

  const toggle = (uri: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  return (
    <section className={styles.step}>
      <header className={styles.header}>
        <p className="eyebrow">Rapid search · Step 01</p>
        <h2>Which directions should we search for?</h2>
        <p className={styles.lede}>
          Matched from your profile — skills, experience and projects against occupation
          data. Uncheck anything you&apos;re not interested in.
        </p>
      </header>

      <ul className={styles.list}>
        {recommendations.map((rec) => (
          <DirectionCard
            key={rec.occupation_uri}
            rec={rec}
            checked={selected.has(rec.occupation_uri)}
            onToggle={() => toggle(rec.occupation_uri)}
          />
        ))}
      </ul>

      <footer className={styles.actions}>
        <span className={styles.count}>
          {selected.size === 0
            ? 'Nothing selected \u2014 we\u2019ll use your top 2 matches.'
            : `${selected.size} of ${recommendations.length} selected`}
        </span>
        <span className={styles.buttons}>
          <button type="button" className={styles.secondary} onClick={onBack}>
            Back
          </button>
          <button
            type="button"
            className="primary-action"
            onClick={() => onConfirm([...selected])}
          >
            Search these <span aria-hidden="true">→</span>
          </button>
        </span>
      </footer>
    </section>
  );
}

function DirectionCard({
  rec, checked, onToggle,
}: { rec: CareerRecommendation; checked: boolean; onToggle: () => void }) {
  return (
    <li className={checked ? styles.cardOn : styles.card}>
      <label className={styles.cardLabel}>
        <input type="checkbox" checked={checked} onChange={onToggle} />
        <span className={styles.cardBody}>
          {/* The model's own confidence band is deliberately not shown.
              "low confidence" describes how sure the retrieval step is,
              not how suitable the direction is for the user — and reading
              it as the latter would discourage people from perfectly
              reasonable options. The evidence chips below say more, and
              say it in the user's terms. */}
          <span className={styles.cardTop}>
            <b>{rec.occupation_title}</b>
          </span>
          <span className={styles.explanation}>{rec.explanation}</span>
          {rec.matched_evidence.length > 0 && (
            <span className={styles.evidence}>
              {rec.matched_evidence.slice(0, 4).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </span>
          )}
        </span>
      </label>
    </li>
  );
}
