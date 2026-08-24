/**
 * The parsed-profile contract, mirroring the backend's
 * `internal/prompts/parsed_resume_schema.json` and `schemas.py` exactly.
 *
 * There is deliberately no `email` and no `phone` here. They are excluded at
 * the schema level on the server, which means a profile carrying them would
 * have failed validation before it ever reached this app.
 */

export type Contact = {
  name: string | null;
  location: string | null;
  links: string[];
};

export type Education = {
  degree: string | null;
  field: string | null;
  institution: string | null;
  start_year: string | null;
  end_year: string | null;
};

export type Experience = {
  job_title: string | null;
  company: string | null;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  current_role: boolean | null;
  description: string | null;
};

export type Project = {
  name: string | null;
  description: string | null;
  technologies: string[];
};

export type Certification = {
  name: string | null;
  issuer: string | null;
  year: string | null;
};

export type CandidateProfile = {
  contact: Contact;
  skills: string[];
  education: Education[];
  experience: Experience[];
  projects: Project[];
  certifications: Certification[];
  job_titles: string[];
};

export type ParseRoute = 'text' | 'vision';

export type ProfileRecord = {
  id: string;
  filename: string;
  route: ParseRoute;
  page_count: number;
  is_valid: boolean;
  needs_review: string[];
  model_used: string;
  fallback_used: boolean;
  created_at: string;
  /** Set once a user edits the parsed profile; null if it's exactly what parsing produced. */
  edited_at: string | null;
  profile: CandidateProfile;
};

export type ProfileSummary = {
  id: string;
  filename: string;
  route: ParseRoute;
  page_count: number;
  is_valid: boolean;
  needs_review: string[];
  created_at: string;
};

// --- streamed events ------------------------------------------------------ //

/** Matches `ParseStage` in the backend's `schemas.py`. */
export type ParseStage =
  | 'received'
  | 'reading'
  | 'extracting'
  | 'refining'
  | 'persisting'
  | 'ready';

export type StageEvent = {
  type: 'stage';
  stage: ParseStage;
  label: string;
  detail: string | null;
};

export type ProfileEvent = {
  type: 'profile';
  record: ProfileRecord;
};

export type ErrorEvent = {
  type: 'error';
  code: string;
  message: string;
};

export type ParseEvent = StageEvent | ProfileEvent | ErrorEvent;
