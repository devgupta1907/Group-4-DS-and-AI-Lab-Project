import type { ReactNode } from 'react';

import styles from './Card.module.css';

type CardProps = {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** Removes the body padding when the child manages its own spacing. */
  flush?: boolean;
};

export function Card({ title, description, actions, children, flush }: CardProps) {
  const hasHeader = Boolean(title || description || actions);

  return (
    <section className={styles.card}>
      {hasHeader && (
        <header className={styles.header}>
          <div className={styles.heading}>
            {title && <h2 className={styles.title}>{title}</h2>}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      <div className={flush ? styles.bodyFlush : styles.body}>{children}</div>
    </section>
  );
}
