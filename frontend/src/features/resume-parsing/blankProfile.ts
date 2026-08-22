import type { CandidateProfile } from './types/parsedProfile';

/**
 * Starting point for manual entry — same shape `EditableProfileView`
 * already knows how to render and mutate, just with every field empty
 * instead of populated from a parsed resume.
 */
export function blankProfile(): CandidateProfile {
  return {
    contact: { name: null, location: null, links: [] },
    skills: [],
    education: [],
    experience: [],
    projects: [],
    certifications: [],
    job_titles: [],
  };
}
