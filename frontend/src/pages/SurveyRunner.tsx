import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Ban,
  CheckCircle2,
  Clock,
  FlaskConical,
  Lock,
  Search,
} from 'lucide-react';
import { respondApi } from '../api';
import type { AnswerPayload, RenderedQuestion, RespondentState } from '../types';

export const SurveyRunner: React.FC = () => {
  const { token: paramToken } = useParams<{ token?: string }>();
  const [searchParams] = useSearchParams();
  const token = paramToken || searchParams.get('token') || '';

  const [state, setState] = useState<RespondentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  // Local answer state for current question
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [textValue, setTextValue] = useState('');
  const [numericValue, setNumericValue] = useState<string>('');
  const [matrixAnswers, setMatrixAnswers] = useState<Record<string, string>>({});
  const [dropdownSearch, setDropdownSearch] = useState('');

  const hydrateAnswer = (q?: RenderedQuestion | null) => {
    setFieldError(null);
    setDropdownSearch('');
    if (!q || !q.previous_answer) {
      setSelectedOptions([]);
      setTextValue('');
      setNumericValue('');
      setMatrixAnswers({});
      return;
    }
    const prev = q.previous_answer;
    setSelectedOptions(prev.selected_options || []);
    setTextValue(prev.text_value || '');
    setNumericValue(prev.numeric_value !== null && prev.numeric_value !== undefined ? String(prev.numeric_value) : '');
    setMatrixAnswers(prev.matrix_answers || {});
  };

  useEffect(() => {
    if (!token) {
      setFatalError('No survey link token provided.');
      setLoading(false);
      return;
    }
    setLoading(true);
    respondApi
      .getState(token)
      .then((res) => {
        setState(res);
        hydrateAnswer(res.current_question);
      })
      .catch((err) => {
        setFatalError(err instanceof Error ? err.message : 'Unable to load survey.');
      })
      .finally(() => setLoading(false));
  }, [token]);

  const q = state?.current_question || null;

  const filteredDropdownOptions = useMemo(() => {
    if (!q || q.type !== 'dropdown') return [];
    const term = dropdownSearch.trim().toLowerCase();
    if (!term) return q.options;
    return q.options.filter((o) => o.text.toLowerCase().includes(term));
  }, [q, dropdownSearch]);

  const toggleMultiOption = (optText: string, isExclusive: boolean) => {
    if (!q) return;
    setFieldError(null);
    const exclusiveTexts = new Set(q.options.filter((o) => o.is_exclusive).map((o) => o.text));

    if (selectedOptions.includes(optText)) {
      setSelectedOptions(selectedOptions.filter((x) => x !== optText));
      return;
    }

    if (isExclusive) {
      setSelectedOptions([optText]);
      return;
    }

    const withoutExclusive = selectedOptions.filter((x) => !exclusiveTexts.has(x));
    if (q.max_val && withoutExclusive.length >= q.max_val) {
      setFieldError(`You can select at most ${q.max_val} options.`);
      return;
    }
    setSelectedOptions([...withoutExclusive, optText]);
  };

  const handleNext = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!q || !token) return;

    setFieldError(null);
    setSubmitting(true);

    const payload: AnswerPayload = {
      question_id: q.question_id,
    };

    if (['single', 'multi', 'dropdown', 'yesno', 'consent'].includes(q.type)) {
      payload.selected_options = selectedOptions;
      if (textValue.trim()) payload.text_value = textValue.trim();
    } else if (['number', 'rating', 'nps'].includes(q.type)) {
      if (numericValue.trim() !== '') {
        const parsed = Number(numericValue);
        if (Number.isNaN(parsed)) {
          setFieldError('Please enter a valid number.');
          setSubmitting(false);
          return;
        }
        payload.numeric_value = parsed;
      }
    } else if (['text', 'longtext', 'formatted'].includes(q.type)) {
      payload.text_value = textValue;
    } else if (q.type === 'matrix') {
      payload.matrix_answers = matrixAnswers;
    }

    try {
      const nextState = await respondApi.submitAnswer(token, payload);
      setState(nextState);
      hydrateAnswer(nextState.current_question);
    } catch (err) {
      setFieldError(err instanceof Error ? err.message : 'Please check your answer.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBack = async () => {
    if (!q || !token) return;
    setSubmitting(true);
    setFieldError(null);
    try {
      const prevState = await respondApi.goBack(token, q.question_id);
      setState(prevState);
      hydrateAnswer(prevState.current_question);
    } catch (err) {
      setFieldError(err instanceof Error ? err.message : 'Could not go back.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-600">Loading your survey...</p>
        </div>
      </div>
    );
  }

  if (fatalError || !state) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm">
          <AlertCircle className="mx-auto mb-3 h-10 w-10 text-red-500" />
          <h1 className="text-lg font-bold text-slate-900">Unable to Open Survey</h1>
          <p className="mt-2 text-sm text-slate-600">{fatalError || 'Invalid survey link.'}</p>
        </div>
      </div>
    );
  }

  // Dedicated 4 End Screens
  if (state.end_screen) {
    const endConfig = {
      completed: {
        icon: <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-emerald-600" />,
        title: 'Thank You!',
        desc: 'Your survey response has been completed and saved.',
        badge: 'Completed',
        badgeClass: 'bg-emerald-100 text-emerald-800',
      },
      not_eligible: {
        icon: <Ban className="mx-auto mb-4 h-12 w-12 text-amber-600" />,
        title: 'Not Eligible',
        desc: 'Thank you for your interest. Unfortunately, you do not meet the criteria for this study.',
        badge: 'Terminated',
        badgeClass: 'bg-amber-100 text-amber-800',
      },
      survey_closed: {
        icon: <Lock className="mx-auto mb-4 h-12 w-12 text-slate-500" />,
        title: 'Survey Closed',
        desc: 'This study has reached its target number of responses or its deadline has passed.',
        badge: 'Closed',
        badgeClass: 'bg-slate-200 text-slate-700',
      },
      already_completed: {
        icon: <Clock className="mx-auto mb-4 h-12 w-12 text-indigo-600" />,
        title: 'Already Completed',
        desc: 'You have already submitted a response using this link. Thank you for participating!',
        badge: 'Already Submitted',
        badgeClass: 'bg-indigo-100 text-indigo-800',
      },
    }[state.end_screen];

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-4">
        {state.is_test && (
          <div className="mb-4 flex items-center gap-2 rounded-full bg-purple-100 px-4 py-1.5 text-xs font-semibold text-purple-800">
            <FlaskConical className="h-3.5 w-3.5" /> Preview / Test Mode
          </div>
        )}
        <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          {endConfig.icon}
          <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${endConfig.badgeClass}`}>
            {endConfig.badge}
          </span>
          <h1 className="mt-4 text-2xl font-bold text-slate-900">{endConfig.title}</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{endConfig.desc}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {/* Top Progress Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        {state.is_test && (
          <div className="flex items-center justify-center gap-1.5 bg-purple-600 px-3 py-1 text-xs font-semibold text-white">
            <FlaskConical className="h-3.5 w-3.5" />
            Preview / Test Mode — Answers are not counted
          </div>
        )}
        <div className="mx-auto max-w-xl px-4 py-3">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span className="truncate font-semibold text-slate-800">{state.survey_title}</span>
            <span>{state.progress_percent}%</span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all duration-300"
              style={{ width: `${Math.max(4, state.progress_percent)}%` }}
            />
          </div>
        </div>
      </header>

      {/* Question Card */}
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center px-4 py-6">
        {q && (
          <form
            onSubmit={handleNext}
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 font-mono text-xs font-semibold text-indigo-700 uppercase">
                {q.question_id}
              </span>
              {q.required && <span className="text-xs font-medium text-rose-600">* Required</span>}
            </div>

            <h2 className="text-lg font-bold leading-snug text-slate-900 sm:text-xl">{q.text}</h2>

            <div className="mt-6">
              {/* INFO */}
              {q.type === 'info' && (
                <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                  Tap Continue to begin the survey.
                </p>
              )}

              {/* YESNO & CONSENT */}
              {(q.type === 'yesno' || q.type === 'consent') && (
                <div className="grid grid-cols-2 gap-3">
                  {(q.options.length > 0 ? q.options : [{ text: 'Yes' }, { text: 'No' }]).map((opt) => {
                    const active = selectedOptions.includes(opt.text);
                    return (
                      <button
                        key={opt.text}
                        type="button"
                        onClick={() => {
                          setSelectedOptions([opt.text]);
                          setFieldError(null);
                        }}
                        className={`rounded-2xl border-2 py-5 text-base font-bold transition ${
                          active
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        {opt.text}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* SINGLE */}
              {q.type === 'single' && (
                <div className="space-y-2.5">
                  {q.options.map((opt) => {
                    const active = selectedOptions.includes(opt.text);
                    return (
                      <div key={opt.text}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedOptions([opt.text]);
                            setFieldError(null);
                          }}
                          className={`flex w-full items-center gap-3 rounded-2xl border-2 px-4 py-3.5 text-left text-sm font-medium transition ${
                            active
                              ? 'border-indigo-600 bg-indigo-50 text-indigo-900'
                              : 'border-slate-200 bg-white text-slate-800 hover:border-slate-300'
                          }`}
                        >
                          <span
                            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                              active ? 'border-indigo-600' : 'border-slate-300'
                            }`}
                          >
                            {active && <span className="h-2.5 w-2.5 rounded-full bg-indigo-600" />}
                          </span>
                          <span>{opt.text}</span>
                        </button>
                        {opt.is_other && active && (
                          <input
                            type="text"
                            value={textValue}
                            onChange={(e) => setTextValue(e.target.value)}
                            placeholder="Please specify..."
                            className="mt-2 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* MULTI */}
              {q.type === 'multi' && (
                <div className="space-y-2.5">
                  {q.max_val && (
                    <div className="mb-2 flex justify-between text-xs font-medium text-slate-500">
                      <span>Select up to {q.max_val}</span>
                      <span className="text-indigo-600 font-semibold">
                        {selectedOptions.length} / {q.max_val} selected
                      </span>
                    </div>
                  )}
                  {q.options.map((opt) => {
                    const active = selectedOptions.includes(opt.text);
                    return (
                      <div key={opt.text}>
                        <button
                          type="button"
                          onClick={() => toggleMultiOption(opt.text, opt.is_exclusive)}
                          className={`flex w-full items-center gap-3 rounded-2xl border-2 px-4 py-3.5 text-left text-sm font-medium transition ${
                            active
                              ? 'border-indigo-600 bg-indigo-50 text-indigo-900'
                              : 'border-slate-200 bg-white text-slate-800 hover:border-slate-300'
                          }`}
                        >
                          <span
                            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 text-xs font-bold ${
                              active
                                ? 'border-indigo-600 bg-indigo-600 text-white'
                                : 'border-slate-300 bg-white'
                            }`}
                          >
                            {active && '✓'}
                          </span>
                          <span>{opt.text}</span>
                        </button>
                        {opt.is_other && active && (
                          <input
                            type="text"
                            value={textValue}
                            onChange={(e) => setTextValue(e.target.value)}
                            placeholder="Please specify..."
                            className="mt-2 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* DROPDOWN (Searchable) */}
              {q.type === 'dropdown' && (
                <div className="space-y-2">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
                    <input
                      type="text"
                      value={dropdownSearch}
                      onChange={(e) => setDropdownSearch(e.target.value)}
                      placeholder="Search options..."
                      className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                    />
                  </div>
                  <div className="max-h-56 overflow-y-auto rounded-2xl border border-slate-200 divide-y divide-slate-100">
                    {filteredDropdownOptions.length === 0 ? (
                      <p className="p-4 text-center text-xs text-slate-500">No matching options.</p>
                    ) : (
                      filteredDropdownOptions.map((opt) => {
                        const active = selectedOptions.includes(opt.text);
                        return (
                          <button
                            key={opt.text}
                            type="button"
                            onClick={() => {
                              setSelectedOptions([opt.text]);
                              setFieldError(null);
                            }}
                            className={`flex w-full items-center justify-between px-4 py-3 text-left text-sm transition ${
                              active ? 'bg-indigo-50 font-semibold text-indigo-700' : 'hover:bg-slate-50'
                            }`}
                          >
                            <span>{opt.text}</span>
                            {active && <CheckCircle2 className="h-4 w-4 text-indigo-600" />}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* RATING */}
              {q.type === 'rating' && (
                <div>
                  <div className="grid grid-cols-5 gap-2 sm:gap-3">
                    {Array.from(
                      { length: (q.max_val ?? 5) - (q.min_val ?? 1) + 1 },
                      (_, i) => (q.min_val ?? 1) + i
                    ).map((val) => {
                      const active = numericValue === String(val);
                      return (
                        <button
                          key={val}
                          type="button"
                          onClick={() => {
                            setNumericValue(String(val));
                            setFieldError(null);
                          }}
                          className={`rounded-2xl border-2 py-4 text-base font-bold transition ${
                            active
                              ? 'border-indigo-600 bg-indigo-600 text-white'
                              : 'border-slate-200 bg-white text-slate-800 hover:border-indigo-300'
                          }`}
                        >
                          {val}
                        </button>
                      );
                    })}
                  </div>
                  {(q.low_label || q.high_label) && (
                    <div className="mt-2 flex justify-between text-xs text-slate-500">
                      <span>{q.low_label}</span>
                      <span>{q.high_label}</span>
                    </div>
                  )}
                </div>
              )}

              {/* NPS (0 to 10) */}
              {q.type === 'nps' && (
                <div>
                  <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-11">
                    {Array.from({ length: 11 }, (_, i) => i).map((val) => {
                      const active = numericValue === String(val);
                      return (
                        <button
                          key={val}
                          type="button"
                          onClick={() => {
                            setNumericValue(String(val));
                            setFieldError(null);
                          }}
                          className={`rounded-xl border-2 py-3 text-sm font-bold transition ${
                            active
                              ? 'border-indigo-600 bg-indigo-600 text-white'
                              : 'border-slate-200 bg-white text-slate-800 hover:border-indigo-300'
                          }`}
                        >
                          {val}
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-slate-500">
                    <span>0 = Not at all likely</span>
                    <span>10 = Extremely likely</span>
                  </div>
                </div>
              )}

              {/* MATRIX */}
              {q.type === 'matrix' && (
                <div className="space-y-4">
                  {q.rows.map((rowText) => (
                    <div key={rowText} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                      <p className="mb-3 text-sm font-semibold text-slate-800">{rowText}</p>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                        {q.options.map((opt) => {
                          const active = matrixAnswers[rowText] === opt.text;
                          return (
                            <button
                              key={opt.text}
                              type="button"
                              onClick={() => {
                                setMatrixAnswers({ ...matrixAnswers, [rowText]: opt.text });
                                setFieldError(null);
                              }}
                              className={`rounded-xl border px-2.5 py-2 text-xs font-medium transition ${
                                active
                                  ? 'border-indigo-600 bg-indigo-600 text-white'
                                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                              }`}
                            >
                              {opt.text}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* NUMBER */}
              {q.type === 'number' && (
                <div>
                  <input
                    type="number"
                    inputMode="numeric"
                    value={numericValue}
                    min={q.min_val ?? undefined}
                    max={q.max_val ?? undefined}
                    onChange={(e) => {
                      setNumericValue(e.target.value);
                      setFieldError(null);
                    }}
                    placeholder="Enter a number"
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3.5 text-base focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                  {(q.min_val !== null || q.max_val !== null) && (
                    <p className="mt-1.5 text-xs text-slate-500">
                      Allowed range: {q.min_val ?? '—'} to {q.max_val ?? '—'}
                    </p>
                  )}
                </div>
              )}

              {/* TEXT / FORMATTED */}
              {(q.type === 'text' || q.type === 'formatted') && (
                <div>
                  <input
                    type={q.format_rule === 'email' ? 'email' : q.format_rule === 'phone' ? 'tel' : 'text'}
                    inputMode={q.format_rule === 'pincode' || q.format_rule === 'phone' ? 'numeric' : 'text'}
                    value={textValue}
                    onChange={(e) => {
                      setTextValue(e.target.value);
                      setFieldError(null);
                    }}
                    placeholder={
                      q.format_rule === 'pincode'
                        ? 'Enter 6-digit pincode (e.g. 400001)'
                        : q.format_rule === 'phone'
                        ? 'Enter 10-digit phone number'
                        : q.format_rule === 'email'
                        ? 'name@example.com'
                        : 'Type your answer...'
                    }
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3.5 text-base focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                </div>
              )}

              {/* LONGTEXT */}
              {q.type === 'longtext' && (
                <div>
                  <textarea
                    rows={4}
                    value={textValue}
                    onChange={(e) => {
                      setTextValue(e.target.value);
                      setFieldError(null);
                    }}
                    placeholder="Share your thoughts..."
                    className="w-full rounded-2xl border border-slate-300 p-4 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                  {q.min_length && (
                    <p className="mt-1 text-right text-xs text-slate-500">
                      {textValue.trim().length} / {q.min_length} min characters
                    </p>
                  )}
                </div>
              )}
            </div>

            {fieldError && (
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{fieldError}</span>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="mt-8 flex items-center justify-between gap-3">
              {state.can_go_back ? (
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={submitting}
                  className="inline-flex items-center gap-1.5 rounded-2xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  <ArrowLeft className="h-4 w-4" /> Back
                </button>
              ) : (
                <div />
              )}

              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-7 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition"
              >
                {submitting ? 'Saving...' : q.type === 'info' ? 'Continue' : 'Next'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
};
