import type { CareerReport } from '../types';

import styles from './CandidateProfileSection.module.css';
import { SectionHeader } from './SectionHeader';

type Props = { report: CareerReport };

export function CandidateProfileSection({ report }: Props) {
  const { content } = report;

  return (
    <section id="section-1">
      <SectionHeader
        number="01"
        title="Your professional profile today"
        description="A grounded reading of the experience, capabilities, and credentials already present in your resume."
      />
      <ProfileSummary content={content} />
      <ProfileDetails snapshot={content.profile_snapshot} />
      <Limitations items={content.profile_snapshot?.data_limitations || []} />
    </section>
  );
}

function ProfileSummary({ content }: { content: CareerReport['content'] }) {
  const positioning = content.profile_snapshot?.current_positioning
    || content.job_titles[0]
    || 'Open profile';
  const strengths = content.profile_snapshot?.demonstrated_strengths || content.profile_skills;
  return (
    <div className={styles.summary}>
      <article className={styles.position}>
        <span>Current positioning</span><h3>{positioning}</h3>
        <p>{content.narrative.executive_summary[0]}</p>
      </article>
      <article className={styles.strengths}>
        <span>Demonstrated capabilities</span>
        <div>{strengths.map((skill) => <strong key={skill}>{skill}</strong>)}</div>
      </article>
    </div>
  );
}

function ProfileDetails({ snapshot }: { snapshot: CareerReport['content']['profile_snapshot'] }) {
  const education = snapshot?.education.map(formatEducation) || [];
  const projects = snapshot?.projects.map(formatProject) || [];
  return (
    <div className={styles.profileGrid}>
      <article><h3>Experience</h3><ExperienceList items={snapshot?.experience || []} /></article>
      <aside>
        <ProfileList title="Education" items={education} />
        <ProfileList title="Projects" items={projects} />
        <ProfileList title="Certifications" items={snapshot?.certifications || []} />
      </aside>
    </div>
  );
}

function formatEducation(item: { qualification: string; institution: string; period: string }) {
  return `${item.qualification} · ${item.institution} ${item.period}`;
}

function formatProject(item: { name: string; description: string }) {
  return item.description ? `${item.name} — ${item.description}` : item.name;
}

function ExperienceList({
  items,
}: {
  items: NonNullable<CareerReport['content']['profile_snapshot']>['experience'];
}) {
  if (!items.length) return <p className={styles.empty}>No experience entries were identified.</p>;
  return items.map((item) => (
    <div className={styles.entry} key={`${item.role}-${item.company}-${item.period}`}>
      <div><strong>{item.role}</strong><span>{item.period}</span></div>
      <p>{[item.company, item.location].filter(Boolean).join(' · ')}</p>
      {item.evidence && <small>{item.evidence}</small>}
    </div>
  ));
}

function ProfileList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className={styles.list}>
      <h3>{title}</h3>
      {items.length
        ? items.map((item) => <p key={item}>{item}</p>)
        : <p className={styles.empty}>Not identified in this resume.</p>}
    </section>
  );
}

function Limitations({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className={styles.limitations}>
      <strong>Profile details to review</strong>
      {items.map((item) => <p key={item}>{item}</p>)}
    </div>
  );
}
