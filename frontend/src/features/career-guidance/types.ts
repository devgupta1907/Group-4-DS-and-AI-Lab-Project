export type SearchPreferences = {
  target_location: string | null;
  remote_only: boolean;
  min_salary_lpa: number | null;
};

export type CareerRecommendation = {
  occupation_title: string;
  occupation_uri: string;
  confidence: 'high' | 'medium' | 'low';
  explanation: string;
  matched_evidence: string[];
};

export type CareerResult = {
  run_id: string;
  status: string;
  message: string;
  recommendations: CareerRecommendation[];
};

export type JobOpportunity = {
  title: string;
  company: string;
  location: string;
  source_url: string;
  interview_probability: number;
  recommendation: string;
  reason: string;
  strengths: string[];
  gaps: string[];
};

export type RoleGuidance = {
  title: string;
  readiness: 'ready_now' | 'near_term_stretch' | 'longer_term_transition';
  confidence: 'high' | 'medium' | 'low';
  rationale: string;
  evidence: string[];
  missing_skills: string[];
  skills_to_learn: string[];
  effort: 'low' | 'medium' | 'high';
  next_step: string;
};

export type CareerReport = {
  id: string;
  profile_id: string;
  status: 'ok' | 'degraded_no_llm';
  created_at: string;
  content: {
    candidate_name: string | null;
    candidate_location: string | null;
    profile_skills: string[];
    job_titles: string[];
    narrative: {
      headline: string;
      executive_summary: string[];
      strongest_direction: string;
      adjacent_direction: string;
      development_priority: string;
      roles: RoleGuidance[];
      pathways: Array<{
        kind: 'immediate' | 'growth' | 'pivot';
        title: string;
        target_roles: string[];
        evidence: string[];
        gaps: string[];
        learning_priorities: string[];
        example_job_titles: string[];
      }>;
      actions: Array<{ horizon: string; action: string; based_on: string }>;
      limitations: string[];
    };
    skill_unlocks: Array<{
      skill: string;
      category: 'quick_win' | 'core_gap' | 'differentiator';
      unlocks: string[];
      evidence_count: number;
    }>;
    funnel: { discovered: number; filtered: number; shortlisted: number };
    opportunities: JobOpportunity[];
    methodology: string[];
  };
};
