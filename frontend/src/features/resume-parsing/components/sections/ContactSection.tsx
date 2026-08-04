import { DefinitionList, SectionShell } from '@shared/ui';
import type { Definition } from '@shared/ui';

import type { Contact } from '../../types/parsedProfile';

import styles from './ContactSection.module.css';

type ContactSectionProps = {
  contact: Contact;
};

export function ContactSection({ contact }: ContactSectionProps) {
  const items: Definition[] = [];

  if (contact.name) items.push({ term: 'Name', value: contact.name });
  if (contact.location) items.push({ term: 'Location', value: contact.location });
  if (contact.links.length > 0) {
    items.push({
      term: contact.links.length === 1 ? 'Link' : 'Links',
      value: (
        <ul className={styles.links}>
          {contact.links.map((link) => (
            <li key={link}>
              <a href={link} target="_blank" rel="noreferrer noopener">
                {link}
              </a>
            </li>
          ))}
        </ul>
      ),
    });
  }

  return (
    <SectionShell
      title="Contact"
      emptyLabel="No contact details found on this resume"
      isEmpty={items.length === 0}
    >
      <DefinitionList items={items} />
      <p className={styles.note}>
        Email addresses and phone numbers are excluded by design and are never stored.
      </p>
    </SectionShell>
  );
}
