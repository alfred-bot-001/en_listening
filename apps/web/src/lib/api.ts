import type {
  Material,
  Sentence,
  Group,
  SubmitResult,
  ProgressInfo,
  ContinueResponse,
} from "@/types/listenflow";

import { authHeaders, handleUnauthorized } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
      ...authHeaders(),
    },
  });
  if (!res.ok) {
    handleUnauthorized(res.status);
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  // 204 No Content (e.g. DELETE /favorite, DELETE /material) has no body —
  // res.json() would throw SyntaxError. Callers of fetchAPI<void> rely on this.
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Materials
export async function listMaterials(
  category?: string,
  sourceType?: string
): Promise<Material[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (sourceType) params.set("source_type", sourceType);
  const qs = params.toString();
  return fetchAPI<Material[]>(`/api/materials${qs ? `?${qs}` : ""}`);
}

export async function importURL(
  url: string,
  title?: string
): Promise<Material> {
  return fetchAPI<Material>("/api/materials/import", {
    method: "POST",
    body: JSON.stringify({ url, title }),
  });
}

export async function uploadFile(
  file: File,
  title?: string
): Promise<Material> {
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);
  const res = await fetch(`${API_BASE}/api/materials/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) {
    handleUnauthorized(res.status);
    throw new Error(`Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteMaterial(id: string): Promise<void> {
  await fetchAPI<void>(`/api/materials/${id}`, { method: "DELETE" });
}

export async function reanalyzeKeywords(
  id: string
): Promise<{ material_id: string; sentence_count: number }> {
  return fetchAPI(`/api/materials/${id}/reanalyze`, { method: "POST" });
}

export async function getJobStatus(
  materialId: string
): Promise<{ id: string; status: string; progress: number }> {
  return fetchAPI(`/api/materials/${materialId}/job`);
}

// Practice
export async function recentMaterial(): Promise<{ material_id: string } | null> {
  const res = await fetch(`${API_BASE}/api/practice/recent`, {
    headers: authHeaders(),
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    handleUnauthorized(res.status);
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export async function continuePractice(
  materialId: string
): Promise<ContinueResponse> {
  return fetchAPI<ContinueResponse>(`/api/practice/continue/${materialId}`);
}

export async function getGroup(
  materialId: string,
  groupIndex: number
): Promise<Group> {
  return fetchAPI<Group>(`/api/practice/group/${materialId}/${groupIndex}`);
}

export async function submitAnswer(
  sentenceId: string,
  answers: Record<string, string>
): Promise<SubmitResult> {
  return fetchAPI<SubmitResult>("/api/practice/submit", {
    method: "POST",
    body: JSON.stringify({ sentence_id: sentenceId, answers }),
  });
}

export async function addFavorite(sentenceId: string): Promise<void> {
  await fetchAPI<void>(`/api/practice/favorite/${sentenceId}`, {
    method: "POST",
  });
}

export async function removeFavorite(sentenceId: string): Promise<void> {
  await fetchAPI<void>(`/api/practice/favorite/${sentenceId}`, {
    method: "DELETE",
  });
}

export async function getWrongbook(): Promise<Sentence[]> {
  return fetchAPI<Sentence[]>("/api/practice/wrongbook");
}

// Stages (关卡)
export interface Stage {
  group_index: number;
  sentence_count: number;
  stars: number;
  best_accuracy: number;
  attempts: number;
}

export async function getStages(
  materialId: string
): Promise<{ material_id: string; stages: Stage[] }> {
  return fetchAPI(`/api/practice/stages/${materialId}`);
}

export async function completeStage(
  materialId: string,
  groupIndex: number,
  correctCount: number,
  totalCount: number
): Promise<Stage> {
  return fetchAPI(
    `/api/practice/stages/${materialId}/${groupIndex}/complete`,
    {
      method: "POST",
      body: JSON.stringify({
        correct_count: correctCount,
        total_count: totalCount,
      }),
    }
  );
}

export async function getFavorites(): Promise<Sentence[]> {
  return fetchAPI<Sentence[]>("/api/practice/favorites");
}
