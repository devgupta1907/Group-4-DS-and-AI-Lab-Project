/**
 * Pure derivations over a parsed profile.
 *
 * These live outside the components so a component stays a rendering of values
 * it was handed, rather than a place where values get computed (rule 3).
 */
import { joinPresent } from '@shared/utils/format';

import type { Experience } from './types/parsedProfile';

/** The role to lead with: the current one, else the first listed. */
export function describeMostRecentRole(experience: Experience[]): string | null {
  const current = experience.find((entry) => entry.current_role) ?? experience[0];
  return current ? joinPresent([current.job_title, current.company], ' at ') : null;
}
