/**
 * The feature's public surface. The app shell imports this and nothing deeper.
 */
export { ResumeParsingPage } from './pages/ResumeParsingPage';
export { ResultsPanel } from './components/ResultsPanel';
export { ResumeUploadPanel } from './components/ResumeUploadPanel';
export { useFileValidation } from './hooks/useFileValidation';
export { useResumeUpload } from './hooks/useResumeUpload';
export type { CandidateProfile, ProfileRecord } from './types/parsedProfile';
