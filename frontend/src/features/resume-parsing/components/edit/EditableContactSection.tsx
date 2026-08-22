import type { Contact } from '../../types/parsedProfile';

import { EditableField } from './EditableField';
import { EditableTagList } from './EditableTagList';
import styles from './EditableContactSection.module.css';

type EditableContactSectionProps = {
  contact: Contact;
  onChange: (contact: Contact) => void;
};

/**
 * `name`/`location` round-trip through '' while editing (the schema uses
 * `null` for "not present") — converted back to `null` on save if left
 * blank, in `EditableProfileView`'s save step, not here.
 */
export function EditableContactSection({ contact, onChange }: EditableContactSectionProps) {
  return (
    <div className={styles.grid}>
      <EditableField
        label="Name"
        value={contact.name ?? ''}
        onChange={(value) => onChange({ ...contact, name: value })}
        placeholder="Full name"
      />
      <EditableField
        label="Location"
        value={contact.location ?? ''}
        onChange={(value) => onChange({ ...contact, location: value })}
        placeholder="City, Country"
      />
      <div className={styles.linksField}>
        <EditableTagList
          label="Links"
          items={contact.links}
          onChange={(links) => onChange({ ...contact, links })}
          placeholder="https://..."
        />
      </div>
    </div>
  );
}
