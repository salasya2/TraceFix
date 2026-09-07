const API = "";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(API + path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(body.message || body.detail?.message || res.statusText);
  }
  return res.json();
}

export const api = {
  overview: () => req<{ active_runs: number; verified_candidates: number; unsuccessful: number; runs: number }>("/v1/overview"),
  runs: () => req<{ items: Run[] }>("/v1/repair-runs"),
  run: (id: string) => req<RunDetail>(`/v1/repair-runs/${id}`),
  candidate: (id: string) => req<CandidateDetail>(`/v1/candidates/${id}`),
  approve: (id: string, patch_digest: string) =>
    req(`/v1/candidates/${id}/approve`, { method: "POST", body: JSON.stringify({ patch_digest }) }),
  publish: (id: string) => req<PublishResult>(`/v1/candidates/${id}/publish`, { method: "POST" }),
  repos: () => req<{ items: Repo[] }>("/v1/repositories"),
  usage: () => req<{ reserved_usd: number; settled_usd: number }>("/v1/usage"),
  audit: () => req<{ items: Audit[] }>("/v1/audit-events"),
  cancel: (id: string) => req(`/v1/repair-runs/${id}/cancel`, { method: "POST" }),
};

export type Run = {
  id: string;
  state: string;
  reason_code?: string;
  simulated: boolean;
  github_run_id: number;
  source_sha: string;
  cost_reserved_usd: number;
};

export type RunDetail = {
  run: Run & { diagnosis?: { hypothesis?: string; failure_category?: string; expected_behavior?: string; known_limitations?: string[] }; limitations?: string[]; execution_sha: string; base_sha: string; reason_detail?: string };
  events: { state: string; actor: string; reason?: string; detail?: string }[];
  candidates: { id: string; iteration: number; patch_digest: string; verified: boolean; badge: string; changed_files: string[]; model: string }[];
};

export type CandidateDetail = {
  id: string;
  patch: string;
  patch_digest: string;
  verified: boolean;
  badge: string;
  limitations: string[];
  verification?: Record<string, unknown>;
  changed_files: string[];
};

export type PublishResult = { mode: string; pr_url?: string; branch?: string };
export type Repo = { id: string; full_name: string; mode: string; publication_mode: string; selected: boolean };
export type Audit = { id: string; actor: string; action: string; target_type: string; at?: string };
