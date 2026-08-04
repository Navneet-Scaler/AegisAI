"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CallCard } from "@/components/dashboard/CallCard";
import { CallDetail } from "@/components/dashboard/CallDetail";
import { DemoControls } from "@/components/dashboard/DemoControls";
import { api } from "@/lib/api";
import { connectFeed, useFeedStore } from "@/lib/feedStore";
import { useToken } from "@/lib/useToken";

export default function DashboardPage() {
  const calls = useFeedStore((s) => s.calls);
  const connected = useFeedStore((s) => s.connected);
  const upsert = useFeedStore((s) => s.upsert);
  const { token, setToken } = useToken();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const disconnect = connectFeed();
    return disconnect;
  }, []);

  useEffect(() => {
    api
      .listCalls()
      .then((rows) => {
        for (const row of rows.slice(0, 30).reverse()) {
          upsert({
            id: row.id,
            tool_name: row.tool_name,
            arguments: row.arguments,
            verdict: row.verdict,
            status: row.status,
            composite_score: row.composite_score,
            rule_score: row.rule_score,
            pattern_score: row.pattern_score,
            judge_score: row.judge_score,
            matched_rules: row.matched_rules,
            judge_reasoning: row.judge_reasoning,
            executed: row.executed,
          });
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = calls.find((c) => c.id === selectedId) ?? null;

  return (
    <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/"
            className="text-sm text-[var(--faint)] transition-colors hover:text-[var(--text)]"
          >
            Back
          </Link>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">Live decision feed</h1>
        </div>
        <Link
          href="/analytics"
          className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--text)]"
        >
          View analytics
        </Link>
      </div>

      <div className="mt-5">
        <DemoControls token={token} onTokenChange={setToken} connected={connected} />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <ul
          className="space-y-2"
          aria-live="polite"
          aria-label="Intercepted tool calls, most recent first"
        >
          {calls.length === 0 && (
            <li className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-4 py-8 text-center text-sm text-[var(--faint)]">
              No calls yet. Run the demo request above to see the feed.
            </li>
          )}
          {calls.map((call) => (
            <CallCard
              key={call.id}
              call={call}
              selected={call.id === selectedId}
              onSelect={() => setSelectedId(call.id)}
            />
          ))}
        </ul>

        <div className="lg:sticky lg:top-6 lg:self-start lg:h-[calc(100vh-8rem)]">
          <CallDetail call={selected} token={token} onDecided={() => {}} />
        </div>
      </div>
    </main>
  );
}
