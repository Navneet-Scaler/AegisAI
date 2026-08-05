const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Verdict = "allow" | "hold" | "block";
export type CallStatus = "pending" | "resolved";

export interface ToolCall {
  id: string;
  session_id: string;
  agent_name: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  step_index: number;
  rule_score: number | null;
  pattern_score: number | null;
  judge_score: number | null;
  composite_score: number | null;
  matched_rules: string[];
  judge_reasoning: string | null;
  failure_reason: string | null;
  verdict: Verdict;
  status: CallStatus;
  forced_by_rule: boolean;
  decided_by: string | null;
  decided_at: string | null;
  executed: boolean;
  result: string | null;
  created_at: string;
}

export interface ModelSnapshot {
  update_count: number;
  feature_names: string[];
  weights: number[];
  drift_detected: boolean;
  last_drift_magnitude: number;
}

export interface VerdictBreakdown {
  verdict: Verdict;
  count: number;
}

export interface ToolBreakdown {
  tool_name: string;
  total: number;
  blocked: number;
  held: number;
}

export interface PolicyRule {
  id: string;
  description?: string;
  match: Record<string, unknown>;
  score?: number;
  force?: "hold" | "block";
}

export interface PolicyRulesResponse {
  policy_id: string;
  rules: PolicyRule[];
  source: "seed" | "saved";
}

export interface PolicyVersionSummary {
  id: string;
  version: number;
  description: string;
  created_by: string;
  created_at: string;
  is_active: boolean;
}

export interface DryRunCallResult {
  call_id: string;
  tool_name: string;
  actual_verdict_tier: string;
  proposed_forced_verdict: string | null;
  matched_rule_ids: string[];
  changed: boolean;
}

export interface DryRunResult {
  sample_size: number;
  would_change: number;
  newly_forced_hold: number;
  newly_forced_block: number;
  no_longer_forced: number;
  results: DryRunCallResult[];
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body || response.statusText);
  }

  return (await response.json()) as T;
}

export const api = {
  listCalls: () => request<ToolCall[]>("/calls"),

  decide: (callId: string, approve: boolean, token: string) =>
    request<ToolCall>(`/calls/${callId}/decide`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ approve }),
    }),

  runAgent: (userRequest: string, agentName = "demo-agent", scenario: "refund" | "delete" = "refund") =>
    request<{ session_id: string; final_answer: string | null }>("/agent/run", {
      method: "POST",
      body: JSON.stringify({ request: userRequest, agent_name: agentName, scenario }),
    }),

  resetDemo: (token: string) =>
    request<{ status: string }>("/demo/reset", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),

  modelSnapshot: () => request<ModelSnapshot>("/analytics/model"),
  verdictBreakdown: () => request<VerdictBreakdown[]>("/analytics/verdicts"),
  toolBreakdown: () => request<ToolBreakdown[]>("/analytics/tools"),

  listPolicyIds: () => request<string[]>("/v1/policies"),
  policyRules: (policyId: string) =>
    request<PolicyRulesResponse>(`/v1/policies/${policyId}/rules`),
  policyVersions: (policyId: string) =>
    request<PolicyVersionSummary[]>(`/v1/policies/${policyId}/versions`),
  dryRunPolicy: (policyId: string, rules: PolicyRule[]) =>
    request<DryRunResult>(`/v1/policies/${policyId}/dry-run`, {
      method: "POST",
      body: JSON.stringify({ rules }),
    }),
  savePolicyDraft: (policyId: string, rules: PolicyRule[], description: string, token: string) =>
    request<PolicyVersionSummary>(`/v1/policies/${policyId}/draft`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ rules, description }),
    }),
  activatePolicyVersion: (policyId: string, versionId: string, token: string) =>
    request<PolicyVersionSummary>(`/v1/policies/${policyId}/versions/${versionId}/activate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),

  streamUrl: () => `${API_URL}/stream`,
};

export { ApiError };
