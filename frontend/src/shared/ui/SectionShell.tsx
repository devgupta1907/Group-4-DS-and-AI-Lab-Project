import type { ReactNode } from 'react';

import { EmptyState } from './EmptyState';
import styles from './SectionShell.module.css';

type SectionShellProps = {
  title: string;
  count?: number;
  badge?: ReactNode;
  /** Rendered when the section has no content — never hidden outright. */
  emptyLabel: string;
  isEmpty: boolean;
  children: ReactNode;
};

/**
 * One titled block of a profile.
 *
 * An empty section renders an explicit "not present" state rather than
 * disappearing: a missing section is a fact about the resume, and hiding it
 * would read as the parser having nothing to say.
 */
export function SectionShell({
  title,
  count,
  badge,
  emptyLabel,
  isEmpty,
  children,
}: SectionShellProps) {
  return (
    <section className={styles.section}>
      <header className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        {count !== undefined && count > 0 && <span className={styles.count}>{count}</span>}
        {badge && <span className={styles.badge}>{badge}</span>}
      </header>
      {isEmpty ? <EmptyState size="compact" title={emptyLabel} /> : children}
    </section>
  );
}
