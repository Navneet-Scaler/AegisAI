"use client";

import { useState } from "react";

import { api } from "@/lib/api";

export function DemoControls({
  token,
  onTokenChange,
  connected,
}: {
  token: string;
  onTokenChange: (value: string) => void;
  connected: boolean;
}) {
  const [running, setRunning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const runAgent = async () => {
    setRunning(true);
    setMessage(null);
    try {
      await api.runAgent("Please refund the duplicate charge on ticket TCK-4417.");
      setMessage("Run started, watch the feed.");
    } catch {
      setMessage("Could not start a run.");
    } finally {
      setRunning(false);
    }
  };

  const resetDemo = async () => {
    if (!token) {
      setMessage("Set the demo token first.");
      return;
    }
    setResetting(true);
    setMessage(null);
    try {
      await api.resetDemo(token);
      setMessage("Demo state reset.");
    } catch {
      setMessage("Reset failed, check the token.");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] px-2.5 py-1 text-xs text-[var(--muted)]"
        aria-live="polite"
      >
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: connected ? "var(--allow)" : "var(--faint)" }}
        />
        {connected ? "Live" : "Connecting"}
      </span>

      <button
        onClick={runAgent}
        disabled={running}
        className="rounded-lg border border-[var(--line-strong)] px-3.5 py-1.5 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-50"
      >
        {running ? "Starting..." : "Run demo request"}
      </button>

      <button
        onClick={resetDemo}
        disabled={resetting}
        className="rounded-lg border border-[var(--line-strong)] px-3.5 py-1.5 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-50"
      >
        {resetting ? "Resetting..." : "Reset demo"}
      </button>

      <input
        type="password"
        placeholder="Demo token"
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
        className="w-40 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--faint)]"
      />

      {message && <span className="text-xs text-[var(--faint)]">{message}</span>}
    </div>
  );
}
