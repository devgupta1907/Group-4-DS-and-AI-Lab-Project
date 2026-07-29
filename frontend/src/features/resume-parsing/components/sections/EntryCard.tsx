import type { ReactNode } from 'react';

import styles from './EntryCard.module.css';

type EntryCardProps = {
  /** The most identifying line — a job title, a degree, a project name. */
  heading: string | null;
  /** Organisation, institution, issuer. */
  subheading?: string | null;
  /** Dates, location, or anything else that qualifies the entry. */
  meta?: (string | null)[];
  badge?: ReactNode;
  body?: string | null;
  children?: ReactNode;
};

/**
 * One repeated entry in a profile section.
 *
 * Every list section renders through this, so an experience, an education and a
 * project all read the same way instead of each inventing a layout.
 */
export function EntryCard({
  heading,
  subheading,
  meta,
  badge,
  body,
  children,
}: EntryCardProps) {
  const metaParts = (meta ?? []).filter((part): part is string => Boolean(part?.trim()));

  return (
    <article className={styles.entry}>
      <div className={styles.head}>
        <h4 className={styles.heading}>{heading ?? 'Untitled'}</h4>
        {badge}
      </div>
      {subheading && <p className={styles.subheading}>{subheading}</p>}
      {metaParts.length > 0 && (
        <p className={styles.meta}>
          {metaParts.map((part, index) => (
            <span key={part}>
              {index > 0 && <span className={styles.dot}>·</span>}
              {part}
            </span>
          ))}
        </p>
      )}
      {body && <p className={styles.body}>{body}</p>}
      {children && <div className={styles.extra}>{children}</div>}
    </article>
  );
}
