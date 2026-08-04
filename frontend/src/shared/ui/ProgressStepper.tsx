import styles from './ProgressStepper.module.css';

export type Step = {
  id: string;
  label: string;
};

export type StepState = 'pending' | 'active' | 'done' | 'failed';

type ProgressStepperProps = {
  steps: readonly Step[];
  /** Resolves each step's visual state. Kept out of here so the feature owns it. */
  stateOf: (step: Step) => StepState;
  detail?: string;
};

export function ProgressStepper({ steps, stateOf, detail }: ProgressStepperProps) {
  return (
    <div>
      <ol className={styles.list}>
        {steps.map((step) => {
          const state = stateOf(step);
          return (
            <li key={step.id} className={`${styles.step} ${styles[state]}`}>
              <span className={styles.marker} aria-hidden="true">
                {state === 'done' ? '✓' : state === 'failed' ? '!' : ''}
              </span>
              <span className={styles.label}>{step.label}</span>
            </li>
          );
        })}
      </ol>
      {detail && <p className={styles.detail}>{detail}</p>}
    </div>
  );
}
