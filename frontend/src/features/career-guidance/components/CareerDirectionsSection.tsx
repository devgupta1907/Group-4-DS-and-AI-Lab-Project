import type { CareerReport, RoleGuidance } from '../types';

import styles from './CareerDirectionsSection.module.css';
import { SectionHeader } from './SectionHeader';

const readiness = {
  ready_now: 'Ready now',
  near_term_stretch: 'Within reach',
  longer_term_transition: 'Longer-term option',
};

export function CareerDirectionsSection({ report }: { report: CareerReport }) {
  const { narrative } = report.content;
  return (
    <section id="section-2">
      <SectionHeader
        number="02"
        title="Career directions, examined properly"
        description="Each direction is assessed from several evidence signals, the remaining gap, and a concrete way to test the fit."
      />
      <div className={styles.compass}>
        <Direction index="01" label="Best current fit" value={narrative.strongest_direction} />
        <Direction index="02" label="Best adjacent move" value={narrative.adjacent_direction} />
        <Direction index="03" label="Highest-leverage improvement" value={narrative.development_priority} />
      </div>
      <div className={styles.roles}>
        {narrative.roles.map((role, index) => <RoleCard role={role} rank={index + 1} key={role.title} />)}
      </div>
      <Pathways pathways={narrative.pathways} />
    </section>
  );
}

function Direction({ index, label, value }: { index: string; label: string; value: string }) {
  return <article><i>{index}</i><span>{label}</span><strong>{value}</strong></article>;
}

function RoleCard({ role, rank }: { role: RoleGuidance; rank: number }) {
  return (
    <article className={styles.role}>
      <header>
        <div><i>{String(rank).padStart(2, '0')}</i><span>{readiness[role.readiness]}</span></div>
        <span>{role.confidence} confidence · {role.effort} effort</span>
      </header>
      <div className={styles.roleIntro}><h3>{role.title}</h3><p>{role.rationale}</p></div>
      <div className={styles.roleAnalysis}>
        <section>
          <h4>Why this direction is credible</h4>
          <ol>{role.evidence.map((item) => <li key={item}>{item}</li>)}</ol>
        </section>
        <section>
          <h4>What would make the case stronger</h4>
          {role.skills_to_learn.length
            ? <ul>{role.skills_to_learn.map((skill) => <li key={skill}>{skill}</li>)}</ul>
            : <p>No gap repeated across multiple shortlisted jobs. Validate against a larger sample before investing in new training.</p>}
        </section>
      </div>
      <footer><span>Recommended test</span><strong>{role.next_step}</strong></footer>
    </article>
  );
}

function Pathways({ pathways }: { pathways: CareerReport['content']['narrative']['pathways'] }) {
  return (
    <div className={styles.pathSection}>
      <div><span>Decision map</span><h3>Three ways to use this evidence</h3></div>
      <div className={styles.pathways}>{pathways.map((path) => (
        <article key={path.kind}>
          <span>{path.kind}</span><h4>{path.title}</h4>
          <dl>
            <div><dt>Targets</dt><dd>{path.target_roles.join(', ')}</dd></div>
            <div><dt>Why plausible</dt><dd>{path.evidence.join(', ') || 'Evidence remains limited'}</dd></div>
            <div><dt>Build next</dt><dd>{path.learning_priorities.join(', ') || 'Strengthen proof rather than adding unrelated skills'}</dd></div>
          </dl>
        </article>
      ))}</div>
    </div>
  );
}
