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

  streamUrl: () => `${API_URL}/stream`,
};

export { ApiError };
