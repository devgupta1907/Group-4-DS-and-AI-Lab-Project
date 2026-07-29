import type { ReactNode } from 'react';

import styles from './EmptyState.module.css';

type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description?: string;
  children?: ReactNode;
  /** Compact fits inside a profile section; roomy fills a whole panel. */
  size?: 'compact' | 'roomy';
};

export function EmptyState({
  icon,
  title,
  description,
  children,
  size = 'roomy',
}: EmptyStateProps) {
  return (
    <div className={`${styles.empty} ${styles[size]}`}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <p className={styles.title}>{title}</p>
      {description && <p className={styles.description}>{description}</p>}
      {children && <div className={styles.extra}>{children}</div>}
    </div>
  );
}
