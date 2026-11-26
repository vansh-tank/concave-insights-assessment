export interface ParseError {
  line: number;
  message: string;
}

export interface UploadResponse {
  valid: boolean;
  survey_id?: string;
  version_id?: number;
  version_number?: number;
  title?: string;
  question_count: number;
  quota_count: number;
  errors: ParseError[];
}

export interface SurveySummary {
  id: string;
  title: string;
  target: number;
  status: 'draft' | 'live' | 'closed';
  deadline?: string | null;
  latest_version?: number | null;
  approved_version?: number | null;
  created_at: string;
}

export interface QuotaItem {
  id: number;
  question_id: string;
  match_value: string;
  target_count: number;
  current_count: number;
  remaining: number;
}

export interface DashboardStats {
  survey_id: string;
  title: string;
  status: string;
  target: number;
  started: number;
  completed: number;
  terminated: number;
  in_progress: number;
  quotas: QuotaItem[];
  termination_reasons: Record<string, number>;
  drop_off_by_question: Record<string, number>;
  quality_flag_counts: Record<string, number>;
}

export interface RespondentLink {
  respondent_id: string;
  token: string;
  url: string;
  status?: string;
  is_test: boolean;
  started_at?: string;
}

export interface QuestionOption {
  text: string;
  is_fixed: boolean;
  is_other: boolean;
  is_exclusive: boolean;
}

export interface PreviousAnswer {
  selected_options?: string[] | null;
  text_value?: string | null;
  numeric_value?: number | null;
  matrix_answers?: Record<string, string> | null;
}

export interface RenderedQuestion {
  question_id: string;
  order_index: number;
  type:
    | 'single'
    | 'multi'
    | 'dropdown'
    | 'yesno'
    | 'rating'
    | 'nps'
    | 'matrix'
    | 'text'
    | 'longtext'
    | 'number'
    | 'formatted'
    | 'info'
    | 'consent';
  text: string;
  required: boolean;
  min_val?: number | null;
  max_val?: number | null;
  min_length?: number | null;
  format_rule?: string | null;
  low_label?: string | null;
  high_label?: string | null;
  options: QuestionOption[];
  rows: string[];
  previous_answer?: PreviousAnswer | null;
}

export interface RespondentState {
  respondent_id: string;
  survey_id: string;
  survey_title: string;
  version_number: number;
  status: 'in_progress' | 'completed' | 'terminated' | 'closed' | 'already_completed';
  end_screen?: 'completed' | 'not_eligible' | 'survey_closed' | 'already_completed' | null;
  is_test: boolean;
  progress_percent: number;
  current_question?: RenderedQuestion | null;
  can_go_back: boolean;
}

export interface AnswerPayload {
  question_id: string;
  selected_options?: string[] | null;
  text_value?: string | null;
  numeric_value?: number | null;
  matrix_answers?: Record<string, string> | null;
}
