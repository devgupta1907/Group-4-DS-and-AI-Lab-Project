import type { ActionItem, CareerReport } from '../types';

import { SectionHeader } from './SectionHeader';
import styles from './WeeklyPlanSection.module.css';

export function WeeklyPlanSection({ report }: { report: CareerReport }) {
  const { narrative } = report.content;
  const weeks = narrative.weekly_plan?.length
    ? narrative.weekly_plan
    : legacyWeeks(narrative.actions);

  return (
    <section id="section-4">
      <SectionHeader
        number="04"
        title="Your first four weeks"
        description="A focused checklist you can work through at your own pace. Each task points back to evidence in this report."
      />
      <div className={styles.plan}>
        {weeks.map((week, index) => (
          <details open={index === 0} key={week.week}>
            <summary>
              <span>Week {week.week}</span>
              <div><strong>{week.theme}</strong><small>{week.outcome}</small></div>
              <i aria-hidden="true">+</i>
            </summary>
            <div className={styles.tasks}>
              {week.tasks.map((task) => (
                <label key={`${week.week}-${task.action}`}>
                  <input type="checkbox" />
                  <span><strong>{task.action}</strong><small>Because: {task.based_on}</small></span>
                </label>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function legacyWeeks(actions: ActionItem[]) {
  const themes = ['Position the profile', 'Strengthen the evidence', 'Search with focus', 'Apply and learn'];
  return themes.map((theme, index) => ({
    week: index + 1,
    theme,
    outcome: index === 3 ? 'A repeatable, evidence-led application process' : 'One concrete improvement completed',
    tasks: actions.filter((_, actionIndex) => actionIndex % 4 === index),
  })).filter((week) => week.tasks.length);
}
