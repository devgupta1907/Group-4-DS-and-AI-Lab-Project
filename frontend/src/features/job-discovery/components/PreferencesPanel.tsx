import type { SearchPreferences } from '../types';

type Props = {
  value: SearchPreferences;
  onChange: (value: SearchPreferences) => void;
  onRun: () => void;
  actionLabel?: string;
};

/**
 * Location / salary / remote-only — inputs that shape a JOB SEARCH, not a
 * career recommendation (career recommendation takes no preferences at
 * all, see career-guidance/careerRecommendationApi.ts). Lives here, not
 * in career-guidance, for that reason; the combined report flow
 * (career-guidance/useCareerGuidance.ts) still needs the same shape for
 * its own `generateReport()` call and keeps its own copy of the
 * `SearchPreferences` type rather than importing this feature's.
 */
export function PreferencesPanel({ value, onChange, onRun, actionLabel }: Props) {
  return (
    <section className="preference-panel" aria-labelledby="preferences-title">
      <div>
        <p className="eyebrow">Step 02 · Shape the search</p>
        <h2 id="preferences-title">Where should your next move take you?</h2>
        <p className="muted">A little context makes live opportunities much more useful.</p>
      </div>
      <div className="preference-grid">
        <label>
          Target location
          <input
            value={value.target_location ?? ''}
            placeholder="Bengaluru, India"
            onChange={(event) =>
              onChange({ ...value, target_location: event.target.value || null })
            }
          />
        </label>
        <label>
          Minimum salary (LPA)
          <input
            type="number"
            min="0"
            value={value.min_salary_lpa ?? ''}
            placeholder="Optional"
            onChange={(event) =>
              onChange({
                ...value,
                min_salary_lpa: event.target.value ? Number(event.target.value) : null,
              })
            }
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={value.remote_only}
            onChange={(event) => onChange({ ...value, remote_only: event.target.checked })}
          />
          Remote opportunities only
        </label>
      </div>
      <button className="primary-action" type="button" onClick={onRun}>
        {actionLabel ?? 'Search for jobs'} <span aria-hidden="true">↗</span>
      </button>
    </section>
  );
}
