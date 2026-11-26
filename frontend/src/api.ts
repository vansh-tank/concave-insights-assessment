import type {
  AnswerPayload,
  DashboardStats,
  RespondentLink,
  RespondentState,
  SurveySummary,
  UploadResponse,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '';

async function handleJson<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`;
    throw Object.assign(new Error(msg), { status: res.status, data });
  }
  return data as T;
}

export const adminApi = {
  listSurveys: (): Promise<SurveySummary[]> =>
    fetch(`${API_BASE}/api/admin/surveys`).then((r) => handleJson<SurveySummary[]>(r)),

  uploadFile: async (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/api/admin/surveys/upload`, {
      method: 'POST',
      body: form,
    });
    const data = (await res.json()) as UploadResponse;
    if (!res.ok && res.status !== 422) {
      throw new Error('Upload failed');
    }
    return data;
  },

  uploadText: async (dslText: string): Promise<UploadResponse> => {
    const res = await fetch(`${API_BASE}/api/admin/surveys/upload-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dsl_text: dslText }),
    });
    const data = (await res.json()) as UploadResponse;
    if (!res.ok && res.status !== 422) {
      throw new Error('Upload failed');
    }
    return data;
  },

  approveVersion: (surveyId: string) =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/approve`, { method: 'POST' }).then(handleJson),

  updateStatus: (surveyId: string, status: 'draft' | 'live' | 'closed') =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }).then(handleJson),

  cloneSurvey: (surveyId: string, newId: string, newTitle?: string) =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_id: newId, new_title: newTitle || undefined }),
    }).then(handleJson),

  getDashboard: (surveyId: string): Promise<DashboardStats> =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/dashboard`).then((r) =>
      handleJson<DashboardStats>(r)
    ),

  listLinks: (surveyId: string): Promise<RespondentLink[]> =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/links`).then((r) =>
      handleJson<RespondentLink[]>(r)
    ),

  createLinks: (surveyId: string, count: number, isTest: boolean): Promise<RespondentLink[]> =>
    fetch(`${API_BASE}/api/admin/surveys/${surveyId}/links`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count, is_test: isTest }),
    }).then((r) => handleJson<RespondentLink[]>(r)),

  exportUrl: (surveyId: string, format: 'csv' | 'xlsx') =>
    `${API_BASE}/api/admin/surveys/${surveyId}/export?format=${format}`,
};

export const respondApi = {
  getState: (token: string): Promise<RespondentState> =>
    fetch(`${API_BASE}/api/respond/${token}`).then((r) => handleJson<RespondentState>(r)),

  submitAnswer: (token: string, payload: AnswerPayload): Promise<RespondentState> =>
    fetch(`${API_BASE}/api/respond/${token}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((r) => handleJson<RespondentState>(r)),

  goBack: (token: string, currentQuestionId?: string): Promise<RespondentState> =>
    fetch(`${API_BASE}/api/respond/${token}/back`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_question_id: currentQuestionId }),
    }).then((r) => handleJson<RespondentState>(r)),
};
