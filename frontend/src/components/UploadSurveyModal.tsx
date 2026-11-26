import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, FileText, Upload, X } from 'lucide-react';
import { adminApi } from '../api';
import type { ParseError } from '../types';

interface Props {
  onClose: () => void;
  onSuccess: (surveyId: string) => void;
}

export const UploadSurveyModal: React.FC<Props> = ({ onClose, onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [dslText, setDslText] = useState('');
  const [mode, setMode] = useState<'file' | 'paste'>('file');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors([]);
    setGeneralError(null);
    setLoading(true);

    try {
      let res;
      if (mode === 'file') {
        if (!file) {
          setGeneralError('Please select a .txt questionnaire file.');
          setLoading(false);
          return;
        }
        res = await adminApi.uploadFile(file);
      } else {
        if (!dslText.trim()) {
          setGeneralError('Please paste questionnaire tags.');
          setLoading(false);
          return;
        }
        res = await adminApi.uploadText(dslText);
      }

      if (!res.valid) {
        setErrors(res.errors);
      } else if (res.survey_id) {
        onSuccess(res.survey_id);
      }
    } catch (err) {
      setGeneralError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-slate-900">Upload Questionnaire (.txt)</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="flex gap-2 rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => { setMode('file'); setErrors([]); setGeneralError(null); }}
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition ${
                mode === 'file' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'
              }`}
            >
              Upload .txt File
            </button>
            <button
              type="button"
              onClick={() => { setMode('paste'); setErrors([]); setGeneralError(null); }}
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition ${
                mode === 'paste' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'
              }`}
            >
              Paste DSL Text
            </button>
          </div>

          {mode === 'file' ? (
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center hover:border-indigo-400 hover:bg-indigo-50/30 transition">
              <FileText className="mb-2 h-8 w-8 text-indigo-500" />
              <span className="text-sm font-medium text-slate-700">
                {file ? file.name : 'Click to choose a questionnaire .txt file'}
              </span>
              <span className="mt-1 text-xs text-slate-500">
                Syntax, IDs, skip-to, show-if, and quotas are checked automatically
              </span>
              <input
                type="file"
                accept=".txt,text/plain"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
          ) : (
            <textarea
              rows={9}
              value={dslText}
              onChange={(e) => setDslText(e.target.value)}
              placeholder='<survey id="my_study" title="My Study" target="100">...'
              className="w-full rounded-xl border border-slate-300 p-3 font-mono text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
          )}

          {generalError && (
            <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{generalError}</span>
            </div>
          )}

          {errors.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-red-800">
                <AlertCircle className="h-4 w-4" />
                <span>Found {errors.length} validation error{errors.length > 1 ? 's' : ''}:</span>
              </div>
              <ul className="max-h-48 space-y-1.5 overflow-y-auto text-xs text-red-700">
                {errors.map((err, idx) => (
                  <li key={idx} className="flex items-start gap-2 rounded bg-white/80 px-2.5 py-1.5 border border-red-100">
                    <span className="shrink-0 rounded bg-red-100 px-1.5 py-0.5 font-mono font-semibold text-red-800">
                      Line {err.line}
                    </span>
                    <span className="pt-0.5">{err.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              {loading ? 'Checking...' : 'Validate & Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
