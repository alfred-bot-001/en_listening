export interface Material {
  id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  category: string | null;
  duration_seconds: number | null;
  job_status: string | null;
}

export interface Sentence {
  id: string;
  text: string;
  display_text: string;
  keywords: string[];
  group_index: number;
  sentence_index: number;
  audio_path: string | null;
  start_time: number;
  end_time: number;
  is_favorite: boolean;
  wrong_count: number;
}

export interface Group {
  material_id: string;
  group_index: number;
  total_sentences: number;
  sentences: Sentence[];
}

export interface SubmitResult {
  sentence_id: string;
  results: Record<string, boolean>;
  all_correct: boolean;
  wrong_count_total: number;
  added_to_wrongbook: boolean;
}

export interface ProgressInfo {
  material_id: string;
  group_index: number;
  sentence_index: number;
}

export interface ContinueResponse {
  progress: ProgressInfo;
  group: Group;
}
