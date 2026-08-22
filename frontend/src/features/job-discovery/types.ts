/**
 * Mirrors `backend/src/job_discovery_matching/models.py` exactly — see
 * that file for the authoritative field-by-field docs.
 */

export type SearchPreferences = {
  target_location: string | null;
  remote_only: boolean;
  min_salary_lpa: number | null;
};

export type JobPostingView = {
  title: string;
  company: string;
  location: string;
  is_remote: boolean;
  required_skills: string[];
  employment_type: string;
  description: string;
  source_url: string;
};

export type JudgeResultView = {
  interview_probability: number;
  strengths: string[];
  gaps: string[];
  recommendation: 'Apply Immediately' | 'Apply' | 'Skip';
  one_line_reason: string;
  used_llm_judge: boolean;
};

export type RankedJob = {
  job: JobPostingView;
  bm25_score: number;
  embedding_score: number;
  hybrid_score: number;
  rank_position: number;
  judge: JudgeResultView | null;
  final_score: number;
};

export type JobDiscoveryStatus =
  | 'ok'
  | 'degraded_no_llm'
  | 'hybrid_only'
  | 'no_jobs'
  | 'no_candidates'
  | 'error'
  | 'awaiting_query_selection'
  | 'awaiting_judge_confirmation';

export type JobDiscoveryResult = {
  run_id: string | null;
  status: JobDiscoveryStatus;
  message: string;
  search_queries: string[];
  generated_queries: string[] | null;
  jobs_discovered: number;
  jobs_after_filter: number;
  top_jobs: RankedJob[];
};
