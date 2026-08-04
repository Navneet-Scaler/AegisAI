"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { StatTile } from "@/components/analytics/StatTile";
import { api, type ModelSnapshot, type ToolBreakdown, type VerdictBreakdown } from "@/lib/api";

export default function AnalyticsPage() {
  const [verdicts, setVerdicts] = useState<VerdictBreakdown[]>([]);
  const [tools, setTools] = useState<ToolBreakdown[]>([]);
  const [model, setModel] = useState<ModelSnapshot | null>(null);

  useEffect(() => {
    api.verdictBreakdown().then(setVerdicts).catch(() => {});
    api.toolBreakdown().then(setTools).catch(() => {});
    api.modelSnapshot().then(setModel).catch(() => {});
  }, []);

  const total = verdicts.reduce((sum, v) => sum + v.count, 0);
  const blocked = verdicts.find((v) => v.verdict === "block")?.count ?? 0;
  const blockRate = total > 0 ? `${Math.round((blocked / total) * 100)}%` : "n/a";

  const toolRows = tools.map((t) => ({
    tool: t.tool_name,
    allowed: t.total - t.blocked - t.held,
    held: t.held,
    blocked: t.blocked,
  }));

  return (
    <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-10">
      <Link
        href="/dashboard"
        className="text-sm text-[var(--faint)] transition-colors hover:text-[var(--text)]"
      >
        Back to dashboard
      </Link>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">Analytics</h1>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <StatTile label="Total calls" value={String(total)} />
        <StatTile label="Block rate" value={blockRate} tone="var(--block)" />
        <StatTile
          label="Model updates"
          value={model ? String(model.update_count) : "..."}
          tone="var(--accent)"
        />
      </div>

      <section className="mt-8 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-medium text-[var(--text)]">Verdicts by tool</h2>
        <p className="mt-1 text-xs text-[var(--faint)]">
          Allowed, held, and blocked calls per tool, most recent demo session.
        </p>
        <div className="mt-4 h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={toolRows} layout="vertical" barSize={14} barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
              <XAxis type="number" allowDecimals={false} stroke="var(--faint)" fontSize={12} />
              <YAxis
                type="category"
                dataKey="tool"
                stroke="var(--faint)"
                fontSize={12}
                width={120}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="allowed" stackId="v" fill="var(--allow)" name="Allowed" radius={[2, 2, 2, 2]} />
              <Bar dataKey="held" stackId="v" fill="var(--hold)" name="Held" radius={[2, 2, 2, 2]} />
              <Bar dataKey="blocked" stackId="v" fill="var(--block)" name="Blocked" radius={[2, 2, 2, 2]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {model && (
        <section className="mt-6 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
          <h2 className="text-sm font-medium text-[var(--text)]">Pattern model weights</h2>
          <p className="mt-1 text-xs text-[var(--faint)]">
            Updated online, once per human decision. {model.update_count} update
            {model.update_count === 1 ? "" : "s"} so far.
          </p>
          <ul className="mt-4 space-y-2">
            {model.feature_names.map((name, i) => {
              const weight = model.weights[i] ?? 0;
              const pct = Math.min(Math.abs(weight) / 3, 1) * 50;
              return (
                <li key={name} className="flex items-center gap-3 text-xs">
                  <span className="w-40 shrink-0 truncate text-[var(--muted)]">{name}</span>
                  <div className="relative h-1.5 flex-1 rounded-full bg-[var(--surface-2)]">
                    <div
                      className="absolute top-0 h-full rounded-full"
                      style={{
                        left: weight >= 0 ? "50%" : `${50 - pct}%`,
                        width: `${pct}%`,
                        background: weight >= 0 ? "var(--block)" : "var(--allow)",
                      }}
                    />
                    <div className="absolute left-1/2 top-0 h-full w-px bg-[var(--line-strong)]" />
                  </div>
                  <span className="w-12 shrink-0 text-right font-mono text-[var(--faint)]">
                    {weight.toFixed(2)}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
