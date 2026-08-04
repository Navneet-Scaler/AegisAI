"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

type Verdict = "allow" | "hold" | "block";

type ScriptedCall = {
  tool: string;
  args: string;
  score: number;
  verdict: Verdict;
  reason: string;
};

/*
  A scripted preview of what the real dashboard shows. The numbers here are
  illustrative, taken from the seeded demo scenario, so the landing page conveys
  the shape of the system without needing the backend to be awake.
*/
const SCRIPT: ScriptedCall[] = [
  {
    tool: "read_ticket",
    args: "id: TCK-4417",
    score: 0.08,
    verdict: "allow",
    reason: "Read only, seen 214 times before",
  },
  {
    tool: "search_customers",
    args: "query: acme corp",
    score: 0.11,
    verdict: "allow",
    reason: "Read only, familiar argument shape",
  },
  {
    tool: "create_refund",
    args: "amount: 42.00",
    score: 0.22,
    verdict: "allow",
    reason: "Below the review threshold",
  },
  {
    tool: "send_email",
    args: "to: ops@external.io",
    score: 0.61,
    verdict: "hold",
    reason: "Recipient domain is not on the allowlist",
  },
  {
    tool: "delete_customer",
    args: "ids: 212 records",
    score: 0.91,
    verdict: "block",
    reason: "Judge: inconsistent with the user request",
  },
];

const VERDICT_STYLE: Record<Verdict, { label: string; color: string; ring: string }> = {
  allow: { label: "allowed", color: "var(--allow)", ring: "var(--allow)" },
  hold: { label: "held", color: "var(--hold)", ring: "var(--hold)" },
  block: { label: "blocked", color: "var(--block)", ring: "var(--block)" },
};

export function PipelineDemo() {
  const reduced = useReducedMotion();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const timer = setInterval(() => {
      setTick((n) => (n >= SCRIPT.length ? 0 : n + 1));
    }, 1400);
    return () => clearInterval(timer);
  }, [reduced]);

  // With reduced motion the whole list is shown at once rather than revealed.
  const visible = SCRIPT.slice(0, reduced ? SCRIPT.length : tick);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
        <span className="h-2 w-2 rounded-full bg-[var(--allow)] animate-pulse" />
        <span className="text-xs font-mono text-[var(--text-muted)]">
          aegisai: intercepting tool calls
        </span>
      </div>

      <ul
        className="p-2 sm:p-3 space-y-1.5 min-h-[19rem]"
        aria-live="polite"
        aria-label="Preview of intercepted tool calls"
      >
        <AnimatePresence initial={false}>
          {visible.map((call) => {
            const style = VERDICT_STYLE[call.verdict];
            return (
              <motion.li
                key={call.tool}
                layout
                initial={reduced ? false : { opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={reduced ? undefined : { opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5"
                style={{ borderLeft: `2px solid ${style.ring}` }}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <code className="text-sm text-[var(--text)]">{call.tool}</code>
                  <span
                    className="text-[11px] font-mono uppercase tracking-wider shrink-0"
                    style={{ color: style.color }}
                  >
                    {style.label} {call.score.toFixed(2)}
                  </span>
                </div>
                <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-xs">
                  <code className="text-[var(--text-faint)]">{call.args}</code>
                  <span className="text-[var(--text-muted)]">{call.reason}</span>
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
    </div>
  );
}
