import { useState } from 'react';

import type { SearchPreferences } from './types';
import { MAX_TARGET_LOCATIONS } from './types';

import styles from '../../App.module.css';

type Props = {
  onSubmit: (preferences: SearchPreferences) => void;
  onSkip: () => void;
};

/**
 * Asked once, right before report generation, rather than as its own page
 * step. If left entirely blank, the backend falls back to the candidate's
 * own resume location for search — this dialog never shows that fallback
 * value pre-filled, since a blank field and "explicitly re-typed your own
 * city" should both just resolve the same way server-side.
 */
export function SearchPreferencesDialog({ onSubmit, onSkip }: Props) {
  const [locationInput, setLocationInput] = useState('');
  const [locations, setLocations] = useState<string[]>([]);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [minSalaryLpa, setMinSalaryLpa] = useState('');

  const atCap = locations.length >= MAX_TARGET_LOCATIONS;

  const addLocation = () => {
    const value = locationInput.trim();
    if (!value || atCap) return;
    if (locations.some((loc) => loc.toLowerCase() === value.toLowerCase())) {
      setLocationInput('');
      return;
    }
    setLocations([...locations, value]);
    setLocationInput('');
  };

  const removeLocation = (index: number) => {
    setLocations(locations.filter((_, i) => i !== index));
  };

  const handleLocationKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addLocation();
    }
  };

  const submit = () => {
    onSubmit({
      target_locations: locations,
      remote_only: remoteOnly,
      min_salary_lpa: minSalaryLpa ? Number(minSalaryLpa) : null,
    });
  };

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="prefs-title">
      <div className={styles.dialog}>
        <p className="eyebrow">Before we search</p>
        <h2 id="prefs-title">Shape the job search</h2>
        <p className={styles.dialogNote} style={{ background: 'transparent', color: 'inherit', padding: 0, margin: '0 0 1.5rem' }}>
          Optional — leave blank and we&apos;ll search using your resume&apos;s own location with
          no other constraints.
        </p>

        <div style={{ display: 'grid', gap: '1.25rem' }}>
          <label style={{ display: 'grid', gap: '.5rem', fontWeight: 700, fontSize: '.85rem' }}>
            Preferred location{locations.length > 0 ? 's' : ''} (up to {MAX_TARGET_LOCATIONS})
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <input
                value={locationInput}
                onChange={(event) => setLocationInput(event.target.value)}
                onKeyDown={handleLocationKeyDown}
                placeholder={atCap ? `${MAX_TARGET_LOCATIONS} added` : 'Bengaluru, India'}
                disabled={atCap}
              />
              <button
                type="button"
                className={styles.secondaryAction}
                onClick={addLocation}
                disabled={atCap || !locationInput.trim()}
              >
                Add
              </button>
            </div>
            {locations.length > 0 && (
              <ul style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem', listStyle: 'none', padding: 0, margin: '.25rem 0 0' }}>
                {locations.map((location, index) => (
                  <li
                    key={location}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '.4rem',
                      padding: '.3rem .7rem', borderRadius: '999px',
                      background: 'var(--c-surface-2, #f0f0f0)', fontWeight: 500, fontSize: '.85rem',
                    }}
                  >
                    {location}
                    <button
                      type="button"
                      onClick={() => removeLocation(index)}
                      aria-label={`Remove ${location}`}
                      style={{ border: 'none', background: 'none', cursor: 'pointer', font: 'inherit', opacity: .6 }}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </label>

          <label style={{ display: 'grid', gap: '.5rem', fontWeight: 700, fontSize: '.85rem' }}>
            Minimum salary (LPA)
            <input
              type="number"
              min="0"
              value={minSalaryLpa}
              placeholder="Optional"
              onChange={(event) => setMinSalaryLpa(event.target.value)}
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '.7rem', fontWeight: 700, fontSize: '.85rem' }}>
            <input
              type="checkbox"
              checked={remoteOnly}
              onChange={(event) => setRemoteOnly(event.target.checked)}
            />
            Remote opportunities only
          </label>
        </div>

        <div className={styles.dialogActions}>
          <button className={styles.secondaryAction} type="button" onClick={onSkip}>
            Skip
          </button>
          <button className="primary-action" type="button" onClick={submit}>
            Build my career report <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </div>
  );
}
