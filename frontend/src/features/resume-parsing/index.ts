/**
 * The feature's public surface. The app shell imports this and nothing deeper.
 */
export { ResumeParsingPage } from './pages/ResumeParsingPage';
export { ResultsPanel } from './components/ResultsPanel';
export { ProfileView } from './components/ProfileView';
export { ResumeUploadPanel } from './components/ResumeUploadPanel';
export { ManualProfileForm } from './components/ManualProfileForm';
export { useFileValidation } from './hooks/useFileValidation';
export { useResumeUpload } from './hooks/useResumeUpload';
export { useManualProfileSubmit } from './hooks/useManualProfileSubmit';
export type { CandidateProfile, ProfileRecord } from './types/parsedProfile';
