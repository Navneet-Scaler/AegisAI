"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { FeedCall } from "@/lib/feedStore";

import { ScoreBar } from "./ScoreBar";
import { VerdictBadge } from "./VerdictBadge";

export function CallDetail({
  call,
  token,
  onDecided,
}: {
  call: FeedCall | null;
  token: string;
  onDecided: () => void;
}) {
  const [pending, setPending] = useState<"approve" | "block" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canDecide = call?.status === "pending";

  const decide = async (approve: boolean) => {
    if (!call) return;
    setError(null);
    setPending(approve ? "approve" : "block");
    try {
      await api.decide(call.id, approve, token);
      onDecided();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That token was rejected. Check it and try again."
          : "The decision could not be sent."
      );
    } finally {
      setPending(null);
    }
  };

  useEffect(() => {
    if (!canDecide) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "a" || event.key === "A") decide(true);
      if (event.key === "b" || event.key === "B") decide(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDecide, call?.id]);

  if (!call) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--faint)]">
        Select a call from the feed to see its full risk breakdown.
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={call.id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="flex flex-col rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <code className="text-base text-[var(--text)]">{call.tool_name}</code>
            <div className="mt-1 text-xs text-[var(--faint)]">{call.id}</div>
          </div>
          <VerdictBadge verdict={call.verdict} />
        </div>

        <div className="mt-4 rounded-lg border border-[var(--line)] bg-[var(--bg)] p-3">
          <pre className="overflow-x-auto text-xs text-[var(--muted)]">
            {JSON.stringify(call.arguments, null, 2)}
          </pre>
        </div>

        <div className="mt-5 space-y-3">
          <ScoreBar label="Composite" value={call.composite_score} />
          <ScoreBar label="Rule layer" value={call.rule_score} />
          <ScoreBar label="Pattern layer" value={call.pattern_score} />
          <ScoreBar label="Judge layer" value={call.judge_score} />
        </div>

        {call.matched_rules.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-[var(--faint)]">Matched rules</div>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {call.matched_rules.map((rule) => (
                <li
                  key={rule}
                  className="rounded border border-[var(--line)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--muted)]"
                >
                  {rule}
                </li>
              ))}
            </ul>
          </div>
        )}

        {call.judge_reasoning && (
          <div className="mt-4">
            <div className="text-xs text-[var(--faint)]">Judge reasoning</div>
            <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
              {call.judge_reasoning}
            </p>
          </div>
        )}

        <div className="mt-6">
          {canDecide ? (
            <>
              <div className="flex gap-2">
                <button
                  onClick={() => decide(true)}
                  disabled={pending !== null}
                  className="flex-1 rounded-lg py-2.5 text-sm font-medium text-[var(--bg)] transition-opacity disabled:opacity-50"
                  style={{ background: "var(--allow)" }}
                >
                  {pending === "approve" ? "Approving..." : "Approve (A)"}
                </button>
                <button
                  onClick={() => decide(false)}
                  disabled={pending !== null}
                  className="flex-1 rounded-lg py-2.5 text-sm font-medium text-[var(--bg)] transition-opacity disabled:opacity-50"
                  style={{ background: "var(--block)" }}
                >
                  {pending === "block" ? "Blocking..." : "Block (B)"}
                </button>
              </div>
              {error && <p className="mt-2 text-xs text-[var(--block)]">{error}</p>}
              {!token && (
                <p className="mt-2 text-xs text-[var(--faint)]">
                  Set the demo token above before deciding.
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-[var(--faint)]">This call is already resolved.</p>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
