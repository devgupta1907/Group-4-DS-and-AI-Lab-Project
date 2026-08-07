import type { CareerReport, RoleGuidance } from '../types';

import styles from './CareerDirectionsSection.module.css';
import { SectionHeader } from './SectionHeader';

const readiness = {
  ready_now: 'Ready now',
  near_term_stretch: 'Near-term stretch',
  longer_term_transition: 'Longer-term transition',
};

export function CareerDirectionsSection({ report }: { report: CareerReport }) {
  const { narrative } = report.content;
  return (
    <section id="section-2">
      <SectionHeader
        number="02"
        title="Where your profile can go"
        description="Start with roles supported by current evidence, then compare realistic adjacent and longer-term options."
      />
      <div className={styles.compass}>
        <Direction label="Strongest immediate direction" value={narrative.strongest_direction} />
        <Direction label="Promising adjacent direction" value={narrative.adjacent_direction} />
        <Direction label="Highest-value development area" value={narrative.development_priority} />
      </div>
      <div className={styles.roles}>
        {narrative.roles.map((role) => <RoleCard role={role} key={role.title} />)}
      </div>
      <h3 className={styles.pathTitle}>Three evidence-backed pathways</h3>
      <div className={styles.pathways}>
        {narrative.pathways.map((path) => (
          <article key={path.kind}>
            <span>{path.kind}</span><h4>{path.title}</h4>
            <p><strong>Target:</strong> {path.target_roles.join(', ')}</p>
            <p><strong>Evidence:</strong> {path.evidence.join(', ') || 'Limited evidence'}</p>
            <p><strong>Build next:</strong> {path.learning_priorities.join(', ') || 'No major gap identified'}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Direction({ label, value }: { label: string; value: string }) {
  return <article><span>{label}</span><strong>{value}</strong></article>;
}

function RoleCard({ role }: { role: RoleGuidance }) {
  return (
    <article className={styles.role}>
      <header><span>{readiness[role.readiness]}</span><span>{role.confidence} confidence</span></header>
      <h3>{role.title}</h3><p>{role.rationale}</p>
      <dl>
        <div><dt>Evidence already present</dt><dd>{role.evidence.join(', ') || 'General profile alignment'}</dd></div>
        <div><dt>Skills to strengthen</dt><dd>{role.skills_to_learn.join(', ') || 'No repeated gap identified'}</dd></div>
        <div><dt>Transition effort</dt><dd>{role.effort}</dd></div>
      </dl>
      <footer><strong>Recommended next move</strong><p>{role.next_step}</p></footer>
    </article>
  );
}
