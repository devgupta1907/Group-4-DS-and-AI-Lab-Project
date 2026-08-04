import type { ReactNode } from 'react';

import styles from './DefinitionList.module.css';

export type Definition = {
  term: string;
  value: ReactNode;
};

type DefinitionListProps = {
  items: readonly Definition[];
  /** Renders terms above values instead of beside them. */
  stacked?: boolean;
};

/**
 * Field/value pairs. Entries with an empty value are dropped by the caller, not
 * here — whether an absent field is worth showing is a decision for the feature.
 */
export function DefinitionList({ items, stacked }: DefinitionListProps) {
  if (items.length === 0) return null;

  return (
    <dl className={stacked ? styles.stacked : styles.inline}>
      {items.map(({ term, value }) => (
        <div className={styles.row} key={term}>
          <dt className={styles.term}>{term}</dt>
          <dd className={styles.value}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
