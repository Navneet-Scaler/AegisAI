"use client";

import { motion } from "framer-motion";

import type { FeedCall } from "@/lib/feedStore";

import { VerdictBadge } from "./VerdictBadge";

const VERDICT_BORDER: Record<FeedCall["verdict"], string> = {
  allow: "var(--allow)",
  hold: "var(--hold)",
  block: "var(--block)",
};

export function CallCard({
  call,
  selected,
  onSelect,
}: {
  call: FeedCall;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <motion.li layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
      <button
        onClick={onSelect}
        className="w-full rounded-lg border px-3.5 py-3 text-left transition-colors"
        style={{
          borderColor: selected ? VERDICT_BORDER[call.verdict] : "var(--line)",
          background: selected ? "var(--surface-2)" : "var(--surface)",
          borderLeftWidth: 3,
          borderLeftColor: VERDICT_BORDER[call.verdict],
        }}
      >
        <div className="flex items-center justify-between gap-3">
          <code className="truncate text-sm text-[var(--text)]">{call.tool_name}</code>
          <VerdictBadge verdict={call.verdict} />
        </div>
        <div className="mt-1 flex items-center justify-between gap-3 text-xs text-[var(--faint)]">
          <span>{call.status === "pending" ? "awaiting review" : call.executed ? "executed" : "not executed"}</span>
          <span className="font-mono">
            {call.composite_score === null ? "" : Math.round(call.composite_score * 100)}
          </span>
        </div>
      </button>
    </motion.li>
  );
}
