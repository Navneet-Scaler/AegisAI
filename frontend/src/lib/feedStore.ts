import { create } from "zustand";

import { api, type Verdict } from "@/lib/api";

export interface FeedCall {
  id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  verdict: Verdict;
  status: "pending" | "resolved";
  composite_score: number | null;
  rule_score: number | null;
  pattern_score: number | null;
  judge_score: number | null;
  matched_rules: string[];
  judge_reasoning: string | null;
  executed: boolean;
}

interface FeedState {
  calls: FeedCall[];
  connected: boolean;
  upsert: (call: FeedCall) => void;
  setConnected: (connected: boolean) => void;
}

const MAX_FEED_LENGTH = 50;

export const useFeedStore = create<FeedState>((set) => ({
  calls: [],
  connected: false,
  upsert: (call) =>
    set((state) => {
      const index = state.calls.findIndex((c) => c.id === call.id);
      if (index === -1) {
        return { calls: [call, ...state.calls].slice(0, MAX_FEED_LENGTH) };
      }
      const next = [...state.calls];
      next[index] = call;
      return { calls: next };
    }),
  setConnected: (connected) => set({ connected }),
}));

let activeSource: EventSource | null = null;
let reconnectDelay = 1000;

export function connectFeed(): () => void {
  if (activeSource) {
    return () => {};
  }

  const connect = () => {
    const source = new EventSource(api.streamUrl());
    activeSource = source;

    source.addEventListener("open", () => {
      reconnectDelay = 1000;
      useFeedStore.getState().setConnected(true);
    });

    source.addEventListener("call", (event: MessageEvent) => {
      const data = JSON.parse(event.data) as FeedCall;
      useFeedStore.getState().upsert(data);
    });

    source.addEventListener("error", () => {
      useFeedStore.getState().setConnected(false);
      source.close();
      activeSource = null;
      reconnectDelay = Math.min(reconnectDelay * 2, 15000);
      setTimeout(connect, reconnectDelay);
    });
  };

  connect();

  return () => {
    activeSource?.close();
    activeSource = null;
  };
}
