import { SectionShell } from '@shared/ui';

import type { Contact } from '../../../types/parsedProfile';

import { Field, TagEditor } from './EditFields';
import styles from './RepeatableEdit.module.css';

type ContactEditProps = {
  contact: Contact;
  onChange: (contact: Contact) => void;
};

export function ContactEdit({ contact, onChange }: ContactEditProps) {
  return (
    <SectionShell title="Contact" emptyLabel="" isEmpty={false}>
      <div className={styles.grid2}>
        <Field
          label="Name"
          value={contact.name ?? ''}
          onChange={(name) => onChange({ ...contact, name: name || null })}
        />
        <Field
          label="Location"
          value={contact.location ?? ''}
          placeholder="City, Country"
          onChange={(location) => onChange({ ...contact, location: location || null })}
        />
      </div>
      <p className={styles.note}>
        Email addresses and phone numbers are excluded by design and are never stored — this
        form will not accept them either.
      </p>
      <TagEditor
        items={contact.links}
        onChange={(links) => onChange({ ...contact, links })}
        placeholder="Add a link (portfolio, GitHub, LinkedIn…)"
        ariaLabel="Links"
      />
    </SectionShell>
  );
}
