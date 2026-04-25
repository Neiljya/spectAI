// src/components/match/PostMatchUpload.tsx
// Form is entirely auto-generated from MATCH_SCHEMA in types/match.ts.
// To add/remove fields, edit MATCH_SCHEMA only. No changes needed here.

import { useState, FormEvent } from 'react';
import { supabase } from '@/lib/supabase';
import {
  MATCH_SCHEMA,
  MATCH_SCHEMA_GROUPS,
  GROUP_LABELS,
  CURRENT_SCHEMA_VERSION,
  type MatchDataPayload,
  type MatchField,
} from '@/types/match';
import './PostMatchUpload.css';

interface Props {
  profileId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

type FormValues = Record<string, string>;

function initValues(): FormValues {
  return Object.fromEntries(MATCH_SCHEMA.map(f => [f.key, '']));
}

function castValue(field: MatchField, raw: string): string | number | boolean | null {
  if (raw === '') return null;
  if (field.type === 'number') {
    const n = parseFloat(raw);
    return isNaN(n) ? null : n;
  }
  if (field.type === 'boolean') return raw === 'true';
  return raw;
}

export function PostMatchUpload({ profileId, onSuccess, onCancel }: Props) {
  const [values, setValues]   = useState<FormValues>(initValues);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  function set(key: string, val: string) {
    setValues(v => ({ ...v, [key]: val }));
  }

  function validate(): string | null {
    for (const field of MATCH_SCHEMA) {
      if (field.required && !values[field.key]) {
        return `${field.label} is required`;
      }
      if (field.type === 'number' && values[field.key] !== '') {
        const n = parseFloat(values[field.key]);
        if (isNaN(n)) return `${field.label} must be a number`;
        if (field.min != null && n < field.min) return `${field.label} must be ≥ ${field.min}`;
        if (field.max != null && n > field.max) return `${field.label} must be ≤ ${field.max}`;
      }
    }
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }

    setLoading(true);
    setError(null);

    // Cast values to proper types
    const payload: MatchDataPayload = {};
    for (const field of MATCH_SCHEMA) {
      payload[field.key] = castValue(field, values[field.key]);
    }

    const { error: dbErr } = await supabase.from('match_data').insert({
      profile_id:     profileId,
      schema_version: CURRENT_SCHEMA_VERSION,
      data:           payload,
    });

    setLoading(false);
    if (dbErr) { setError(dbErr.message); return; }
    onSuccess();
  }

  return (
    <div className="post-match-upload">
      <div className="post-match-upload__header">
        <div>
          <span className="post-match-upload__eyebrow">Post-match</span>
          <h2 className="post-match-upload__title">Upload Match Data</h2>
        </div>
        <button className="post-match-upload__close" onClick={onCancel} aria-label="Close">✕</button>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {error && <div className="post-match-upload__error">{error}</div>}

        {/* Render groups in order */}
        {Object.entries(MATCH_SCHEMA_GROUPS).map(([group, fields]) => (
          <fieldset key={group} className="match-fieldset">
            <legend className="match-fieldset__legend">{GROUP_LABELS[group] ?? group}</legend>
            <div className="match-fieldset__grid">
              {fields.map(field => (
                <MatchFieldInput
                  key={field.key}
                  field={field}
                  value={values[field.key]}
                  onChange={val => set(field.key, val)}
                />
              ))}
            </div>
          </fieldset>
        ))}

        <div className="post-match-upload__actions">
          <button type="button" className="post-match-upload__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="post-match-upload__submit" disabled={loading}>
            {loading ? <span className="upload-spinner" /> : 'Save Match'}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ── Individual field renderer ───────────────────────────── */

function MatchFieldInput({
  field, value, onChange,
}: {
  field: MatchField;
  value: string;
  onChange: (val: string) => void;
}) {
  const isWide = field.type === 'string' && field.key === 'notes';

  return (
    <div className={`match-field ${isWide ? 'match-field--wide' : ''}`}>
      <label className="match-field__label" htmlFor={`mf-${field.key}`}>
        {field.label}
        {field.required && <span className="match-field__req">*</span>}
        {field.description && (
          <span className="match-field__tip" title={field.description}>?</span>
        )}
      </label>

      {field.type === 'select' ? (
        <select
          id={`mf-${field.key}`}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="match-field__input"
          required={field.required}
        >
          <option value="">— Select —</option>
          {field.options!.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : field.type === 'boolean' ? (
        <select
          id={`mf-${field.key}`}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="match-field__input"
        >
          <option value="">—</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      ) : isWide ? (
        <textarea
          id={`mf-${field.key}`}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="match-field__input match-field__textarea"
          placeholder={field.placeholder}
          rows={3}
        />
      ) : (
        <input
          id={`mf-${field.key}`}
          type={field.type === 'number' ? 'number' : 'text'}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="match-field__input"
          placeholder={field.placeholder ?? (field.type === 'number' ? '0' : '')}
          min={field.min}
          max={field.max}
          required={field.required}
        />
      )}
    </div>
  );
}
