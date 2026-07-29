import type { ReactNode } from 'react';

import styles from './Alert.module.css';

type AlertProps = {
  tone?: 'info' | 'warning' | 'danger';
  title: string;
  children?: ReactNode;
  action?: ReactNode;
};

export function Alert({ tone = 'info', title, children, action }: AlertProps) {
  return (
    <div className={`${styles.alert} ${styles[tone]}`} role="alert">
      <div className={styles.content}>
        <p className={styles.title}>{title}</p>
        {children && <div className={styles.body}>{children}</div>}
      </div>
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
