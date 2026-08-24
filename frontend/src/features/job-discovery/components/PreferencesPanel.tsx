import { useState } from 'react';

import { MAX_TARGET_LOCATIONS, type SearchPreferences } from '../types';

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
  const [locationInput, setLocationInput] = useState('');
  const atCap = value.target_locations.length >= MAX_TARGET_LOCATIONS;

  const addLocation = () => {
    const next = locationInput.trim();
    if (!next || atCap) return;
    if (value.target_locations.some((loc) => loc.toLowerCase() === next.toLowerCase())) {
      setLocationInput('');
      return;
    }
    onChange({ ...value, target_locations: [...value.target_locations, next] });
    setLocationInput('');
  };

  const removeLocation = (index: number) => {
    onChange({
      ...value,
      target_locations: value.target_locations.filter((_, i) => i !== index),
    });
  };

  return (
    <section className="preference-panel" aria-labelledby="preferences-title">
      <div>
        <p className="eyebrow">Step 02 · Shape the search</p>
        <h2 id="preferences-title">Where should your next move take you?</h2>
        <p className="muted">A little context makes live opportunities much more useful.</p>
      </div>
      <div className="preference-grid">
        <label>
          Target location{value.target_locations.length > 1 ? 's' : ''} (up to {MAX_TARGET_LOCATIONS})
          <span style={{ display: 'flex', gap: '.5rem' }}>
            <input
              value={locationInput}
              placeholder={atCap ? `${MAX_TARGET_LOCATIONS} added` : 'Bengaluru, India'}
              disabled={atCap}
              onChange={(event) => setLocationInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  addLocation();
                }
              }}
            />
            <button type="button" onClick={addLocation} disabled={atCap || !locationInput.trim()}>
              Add
            </button>
          </span>
          {value.target_locations.length > 0 && (
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: '.4rem', marginTop: '.4rem' }}>
              {value.target_locations.map((loc, index) => (
                <span
                  key={loc}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '.35rem',
                    padding: '.2rem .6rem', borderRadius: '999px',
                    background: 'var(--c-accent-soft)', fontSize: '.8125rem',
                  }}
                >
                  {loc}
                  <button
                    type="button"
                    aria-label={`Remove ${loc}`}
                    onClick={() => removeLocation(index)}
                    style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, font: 'inherit' }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </span>
          )}
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
