import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCopy,
  Copy,
  Download,
  ExternalLink,
  FileSpreadsheet,
  Link as LinkIcon,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  Upload,
  Users,
} from 'lucide-react';
import { adminApi } from '../api';
import { UploadSurveyModal } from '../components/UploadSurveyModal';
import type { DashboardStats, RespondentLink, SurveySummary } from '../types';

export const AdminDashboard: React.FC = () => {
  const [surveys, setSurveys] = useState<SurveySummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardStats | null>(null);
  const [links, setLinks] = useState<RespondentLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const loadSurveys = useCallback(async (preferId?: string) => {
    setLoading(true);
    try {
      const list = await adminApi.listSurveys();
      setSurveys(list);
      if (preferId) {
        setSelectedId(preferId);
      } else if (list.length > 0 && !selectedId) {
        setSelectedId(list[0].id);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load surveys');
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  const loadSelectedDetails = useCallback(async (id: string) => {
    try {
      const [dash, linkList] = await Promise.all([
        adminApi.getDashboard(id),
        adminApi.listLinks(id),
      ]);
      setDashboard(dash);
      setLinks(linkList);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load dashboard');
    }
  }, []);

  useEffect(() => {
    loadSurveys();
  }, []);

  useEffect(() => {
    if (selectedId) {
      loadSelectedDetails(selectedId);
    }
  }, [selectedId, loadSelectedDetails]);

  const selectedSurvey = surveys.find((s) => s.id === selectedId) || null;

  const showToast = (msg: string) => {
    setErrorMsg(null);
    setActionMsg(msg);
    setTimeout(() => setActionMsg(null), 4000);
  };

  const handleApprove = async () => {
    if (!selectedId) return;
    try {
      await adminApi.approveVersion(selectedId);
      showToast('Latest version approved and frozen.');
      await loadSurveys(selectedId);
      await loadSelectedDetails(selectedId);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to approve');
    }
  };

  const handleStatusChange = async (status: 'live' | 'closed' | 'draft') => {
    if (!selectedId) return;
    try {
      await adminApi.updateStatus(selectedId, status);
      showToast(`Survey status updated to ${status.toUpperCase()}.`);
      await loadSurveys(selectedId);
      await loadSelectedDetails(selectedId);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to update status');
    }
  };

  const handleGenerateLinks = async (count: number, isTest: boolean) => {
    if (!selectedId) return;
    try {
      const created = await adminApi.createLinks(selectedId, count, isTest);
      await loadSelectedDetails(selectedId);
      if (isTest && created[0]) {
        window.open(created[0].url, '_blank');
        showToast('Opened preview/test link in a new tab.');
      } else {
        showToast(`Generated ${created.length} unique respondent link(s).`);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Could not generate links');
    }
  };

  const handleClone = async () => {
    if (!selectedId || !selectedSurvey) return;
    const newId = window.prompt('Enter ID for the cloned survey:', `${selectedId}_wave2`);
    if (!newId) return;
    try {
      await adminApi.cloneSurvey(selectedId, newId.trim(), `${selectedSurvey.title} (Wave 2)`);
      showToast(`Cloned into '${newId.trim()}'.`);
      await loadSurveys(newId.trim());
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Clone failed');
    }
  };

  const copyLink = (url: string, token: string) => {
    navigator.clipboard.writeText(`${window.location.origin}${url}`);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const statusBadge = (status: string) => {
    if (status === 'live') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    if (status === 'closed') return 'bg-slate-200 text-slate-700 border-slate-300';
    return 'bg-amber-100 text-amber-800 border-amber-200';
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top Navbar */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 font-bold text-white">
              C
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Concave Insights</h1>
              <p className="text-xs text-slate-500">Custom Survey Studio & Live Dashboard</p>
            </div>
          </div>

          <button
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
          >
            <Upload className="h-4 w-4" />
            Upload Survey
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {actionMsg && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{actionMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {loading && surveys.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-slate-500">
            Loading surveys...
          </div>
        ) : surveys.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center">
            <Upload className="mx-auto mb-3 h-10 w-10 text-slate-400" />
            <h2 className="text-base font-semibold text-slate-800">No surveys uploaded yet</h2>
            <p className="mt-1 text-sm text-slate-500">
              Upload a plain-text questionnaire file (.txt) to validate, preview, and launch.
            </p>
            <button
              onClick={() => setShowUpload(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              <Plus className="h-4 w-4" /> Upload First Survey
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Survey Sidebar List */}
            <aside className="lg:col-span-4 space-y-3">
              <div className="flex items-center justify-between px-1">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Surveys ({surveys.length})
                </h2>
                <button
                  onClick={() => loadSurveys(selectedId || undefined)}
                  className="text-slate-400 hover:text-slate-600"
                  title="Refresh"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              {surveys.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedId === s.id
                      ? 'border-indigo-500 bg-white shadow-sm ring-2 ring-indigo-100'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-slate-900">{s.title}</h3>
                      <p className="mt-0.5 font-mono text-xs text-slate-500">{s.id}</p>
                    </div>
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${statusBadge(
                        s.status
                      )}`}
                    >
                      {s.status}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-4 text-xs text-slate-600">
                    <span>Target: {s.target}</span>
                    <span>
                      Version: v{s.latest_version ?? 1}
                      {s.approved_version ? ` (Approved v${s.approved_version})` : ' (Draft)'}
                    </span>
                  </div>
                </button>
              ))}
            </aside>

            {/* Selected Survey Workspace */}
            <section className="lg:col-span-8 space-y-6">
              {selectedSurvey && dashboard && (
                <>
                  {/* Controls Card */}
                  <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <h2 className="text-xl font-bold text-slate-900">{selectedSurvey.title}</h2>
                        <p className="text-xs text-slate-500">
                          ID: <span className="font-mono">{selectedSurvey.id}</span> • Latest: v
                          {selectedSurvey.latest_version} • Approved:{' '}
                          {selectedSurvey.approved_version ? `v${selectedSurvey.approved_version}` : 'None'}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => handleGenerateLinks(1, true)}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
                        >
                          <Play className="h-3.5 w-3.5" /> Preview / Test
                        </button>

                        {selectedSurvey.approved_version !== selectedSurvey.latest_version && (
                          <button
                            onClick={handleApprove}
                            className="inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" /> Approve v
                            {selectedSurvey.latest_version}
                          </button>
                        )}

                        {selectedSurvey.status !== 'live' ? (
                          <button
                            onClick={() => handleStatusChange('live')}
                            className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                          >
                            Go Live
                          </button>
                        ) : (
                          <button
                            onClick={() => handleStatusChange('closed')}
                            className="rounded-xl bg-slate-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
                          >
                            Close Survey
                          </button>
                        )}

                        <button
                          onClick={handleClone}
                          className="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          <Copy className="h-3.5 w-3.5" /> Clone
                        </button>
                      </div>
                    </div>

                    {/* Export Bar */}
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                      <span className="text-xs text-slate-500">
                        Export completed non-test responses in standardized layout:
                      </span>
                      <div className="flex items-center gap-2">
                        <a
                          href={adminApi.exportUrl(selectedSurvey.id, 'csv')}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <Download className="h-3.5 w-3.5 text-slate-500" /> Export CSV
                        </a>
                        <a
                          href={adminApi.exportUrl(selectedSurvey.id, 'xlsx')}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" /> Export Excel
                        </a>
                      </div>
                    </div>
                  </div>

                  {/* Live KPI Cards */}
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-medium text-slate-500">Started</p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">{dashboard.started}</p>
                    </div>
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4">
                      <p className="text-xs font-medium text-emerald-700">Completed</p>
                      <p className="mt-1 text-2xl font-bold text-emerald-700">
                        {dashboard.completed}
                        <span className="ml-1 text-xs font-normal text-emerald-600">
                          / {dashboard.target}
                        </span>
                      </p>
                    </div>
                    <div className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
                      <p className="text-xs font-medium text-amber-700">In Progress</p>
                      <p className="mt-1 text-2xl font-bold text-amber-700">
                        {dashboard.in_progress}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-rose-200 bg-rose-50/40 p-4">
                      <p className="text-xs font-medium text-rose-700">Terminated</p>
                      <p className="mt-1 text-2xl font-bold text-rose-700">
                        {dashboard.terminated}
                      </p>
                    </div>
                  </div>

                  {/* Quotas + Termination Breakdown */}
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200 bg-white p-5">
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Users className="h-4 w-4 text-indigo-600" /> Quotas
                      </h3>
                      {dashboard.quotas.length === 0 ? (
                        <p className="text-xs text-slate-500">No quotas defined for this survey.</p>
                      ) : (
                        <div className="space-y-3">
                          {dashboard.quotas.map((q) => {
                            const pct = Math.min(
                              100,
                              Math.round((q.current_count / Math.max(1, q.target_count)) * 100)
                            );
                            return (
                              <div key={q.id}>
                                <div className="mb-1 flex justify-between text-xs">
                                  <span className="font-medium text-slate-700">
                                    {q.question_id}: {q.match_value}
                                  </span>
                                  <span className="text-slate-500">
                                    {q.current_count} done / {q.target_count} target ({q.remaining}{' '}
                                    left)
                                  </span>
                                </div>
                                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                                  <div
                                    className="h-full rounded-full bg-indigo-600 transition-all"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
                      <div>
                        <h3 className="mb-2 text-sm font-semibold text-slate-900">
                          Termination Reasons
                        </h3>
                        {Object.keys(dashboard.termination_reasons).length === 0 ? (
                          <p className="text-xs text-slate-500">No terminations recorded yet.</p>
                        ) : (
                          <ul className="space-y-1.5 text-xs">
                            {Object.entries(dashboard.termination_reasons).map(([reason, count]) => (
                              <li
                                key={reason}
                                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5"
                              >
                                <span className="text-slate-700">{reason}</span>
                                <span className="font-semibold text-slate-900">{count}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      {Object.keys(dashboard.drop_off_by_question).length > 0 && (
                        <div>
                          <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                            In-Progress Drop-Offs
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(dashboard.drop_off_by_question).map(([qid, cnt]) => (
                              <span
                                key={qid}
                                className="rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 border border-amber-200"
                              >
                                {qid}: {cnt}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Respondent Links */}
                  <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <LinkIcon className="h-4 w-4 text-indigo-600" /> Respondent Links
                      </h3>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleGenerateLinks(1, false)}
                          className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                        >
                          <Plus className="h-3.5 w-3.5" /> New Live Link
                        </button>
                        <button
                          onClick={() => handleGenerateLinks(5, false)}
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          +5 Links
                        </button>
                      </div>
                    </div>

                    {links.length === 0 ? (
                      <p className="text-xs text-slate-500">No links generated yet.</p>
                    ) : (
                      <div className="max-h-60 overflow-y-auto divide-y divide-slate-100">
                        {links.map((lk) => (
                          <div
                            key={lk.token}
                            className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-medium text-slate-800">{lk.token}</span>
                              {lk.is_test && (
                                <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700">
                                  TEST
                                </span>
                              )}
                              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium capitalize text-slate-600">
                                {lk.status || 'in_progress'}
                              </span>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => copyLink(lk.url, lk.token)}
                                className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50"
                              >
                                <ClipboardCopy className="h-3 w-3" />
                                {copiedToken === lk.token ? 'Copied!' : 'Copy'}
                              </button>
                              <a
                                href={lk.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 rounded border border-indigo-200 bg-indigo-50 px-2 py-1 font-medium text-indigo-700 hover:bg-indigo-100"
                              >
                                Open <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </section>
          </div>
        )}
      </main>

      {showUpload && (
        <UploadSurveyModal
          onClose={() => setShowUpload(false)}
          onSuccess={(newId) => {
            setShowUpload(false);
            showToast(`Survey '${newId}' validated and saved as draft.`);
            loadSurveys(newId);
          }}
        />
      )}
    </div>
  );
};
