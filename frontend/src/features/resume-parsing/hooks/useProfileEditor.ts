import { useCallback, useState } from 'react';

import type {
  CandidateProfile,
  Certification,
  Contact,
  Education,
  Experience,
  Project,
} from '../types/parsedProfile';

export type ProfileEditor = {
  profile: CandidateProfile;
  setContact: (contact: Contact) => void;
  setSkills: (skills: string[]) => void;
  setJobTitles: (jobTitles: string[]) => void;
  setEducation: (education: Education[]) => void;
  setExperience: (experience: Experience[]) => void;
  setProjects: (projects: Project[]) => void;
  setCertifications: (certifications: Certification[]) => void;
  /** Discards in-progress edits and starts fresh from a given profile —
   *  used when the user cancels, and after a successful save. */
  reset: (profile: CandidateProfile) => void;
};

/**
 * Local, uncommitted edits to a parsed profile.
 *
 * Nothing here talks to the server. `EditProfileForm` owns the save call and
 * only reads `profile` back out of this hook when the user confirms, so a
 * cancelled edit never touches `useResumeUpload`'s record.
 */
export function useProfileEditor(initial: CandidateProfile): ProfileEditor {
  const [profile, setProfile] = useState<CandidateProfile>(initial);

  const setContact = useCallback((contact: Contact) => {
    setProfile((prev) => ({ ...prev, contact }));
  }, []);

  const setSkills = useCallback((skills: string[]) => {
    setProfile((prev) => ({ ...prev, skills }));
  }, []);

  const setJobTitles = useCallback((jobTitles: string[]) => {
    setProfile((prev) => ({ ...prev, job_titles: jobTitles }));
  }, []);

  const setEducation = useCallback((education: Education[]) => {
    setProfile((prev) => ({ ...prev, education }));
  }, []);

  const setExperience = useCallback((experience: Experience[]) => {
    setProfile((prev) => ({ ...prev, experience }));
  }, []);

  const setProjects = useCallback((projects: Project[]) => {
    setProfile((prev) => ({ ...prev, projects }));
  }, []);

  const setCertifications = useCallback((certifications: Certification[]) => {
    setProfile((prev) => ({ ...prev, certifications }));
  }, []);

  const reset = useCallback((next: CandidateProfile) => setProfile(next), []);

  return {
    profile,
    setContact,
    setSkills,
    setJobTitles,
    setEducation,
    setExperience,
    setProjects,
    setCertifications,
    reset,
  };
}
