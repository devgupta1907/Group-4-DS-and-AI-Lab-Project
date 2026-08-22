import { Badge } from '@shared/ui';
import { joinPresent } from '@shared/utils/format';

import { describeMostRecentRole } from '../selectors';
import type { ProfileRecord } from '../types/parsedProfile';

import styles from './ProfileSummaryHeader.module.css';

type ProfileSummaryHeaderProps = {
  record: ProfileRecord;
};

export function ProfileSummaryHeader({ record }: ProfileSummaryHeaderProps) {
  const { profile } = record;
  const subtitle = joinPresent([
    describeMostRecentRole(profile.experience),
    profile.contact.location,
  ]);

  return (
    <header className={styles.header}>
      <div className={styles.identity}>
        <h2 className={styles.name}>{profile.contact.name ?? 'Unnamed candidate'}</h2>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>

      <dl className={styles.stats}>
        <Stat label="Skills" value={profile.skills.length} />
        <Stat label="Roles" value={profile.experience.length} />
        <Stat label="Degrees" value={profile.education.length} />
      </dl>

      <div className={styles.provenance}>
        {record.route === 'manual' ? (
          <Badge tone="neutral">Entered manually</Badge>
        ) : (
          <>
            <Badge tone="neutral">{record.route === 'vision' ? 'Vision path' : 'Text path'}</Badge>
            <Badge tone="neutral">
              {record.page_count} {record.page_count === 1 ? 'page' : 'pages'}
            </Badge>
            <Badge tone={record.fallback_used ? 'warning' : 'accent'}>
              {record.model_used}
            </Badge>
            {record.fallback_used && <Badge tone="warning">Repaired</Badge>}
          </>
        )}
      </div>
    </header>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.stat}>
      <dt className={styles.statLabel}>{label}</dt>
      <dd className={styles.statValue}>{value}</dd>
    </div>
  );
}
