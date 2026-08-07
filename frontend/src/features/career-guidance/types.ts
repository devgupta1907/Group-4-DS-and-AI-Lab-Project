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

export type ActionItem = {
  horizon: '7_days' | '30_days' | '90_days';
  action: string;
  based_on: string;
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
    profile_snapshot?: {
      current_positioning: string;
      experience: Array<{
        role: string;
        company: string;
        location: string;
        period: string;
        evidence: string;
      }>;
      education: Array<{ qualification: string; institution: string; period: string }>;
      projects: Array<{ name: string; description: string; technologies: string[] }>;
      certifications: string[];
      demonstrated_strengths: string[];
      data_limitations: string[];
    };
    source_status?: {
      career_status: string;
      career_message: string;
      job_status: string;
      job_message: string;
    };
    narrative: {
      headline: string;
      executive_summary: string[];
      strongest_direction: string;
      adjacent_direction: string;
      development_priority: string;
      profile_assessment?: {
        seniority_signal: string;
        market_position: string;
        evidence_depth: string;
        strongest_lane: string;
        differentiators: string[];
        evidence_summary: string[];
        watchouts: string[];
      };
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
      actions: ActionItem[];
      weekly_plan?: Array<{
        week: number;
        theme: string;
        outcome: string;
        tasks: ActionItem[];
      }>;
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
