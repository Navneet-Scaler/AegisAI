"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import type { ToastTone } from "./Toast";

function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function DemoControls({
  token,
  onTokenChange,
  connected,
  notify,
}: {
  token: string;
  onTokenChange: (value: string) => void;
  connected: boolean;
  notify: (text: string, tone?: ToastTone) => void;
}) {
  const [running, setRunning] = useState<"refund" | "delete" | null>(null);
  const [resetting, setResetting] = useState(false);

  const runAgent = async (scenario: "refund" | "delete") => {
    setRunning(scenario);
    try {
      if (scenario === "refund") {
        await api.runAgent("Please refund the duplicate charge on ticket TCK-4417.", "demo-agent", "refund");
        notify("Refund run started, watch the feed.", "success");
      } else {
        await api.runAgent("Please remove the requested customer record.", "demo-agent", "delete");
        notify("Delete run started, it will be held for review.", "info");
      }
    } catch {
      notify("Could not start a run.", "error");
    } finally {
      setRunning(null);
    }
  };

  const resetDemo = async () => {
    if (!token) {
      notify("Set the demo token first.", "error");
      return;
    }
    setResetting(true);
    try {
      await api.resetDemo(token);
      notify("Demo state reset.", "success");
    } catch {
      notify("Reset failed, check the token.", "error");
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
          style={{
            background: connected ? "var(--allow)" : "var(--faint)",
            boxShadow: connected ? "0 0 0 3px color-mix(in srgb, var(--allow) 25%, transparent)" : "none",
          }}
        />
        {connected ? "Live" : "Connecting"}
      </span>

      <button
        onClick={() => runAgent("refund")}
        disabled={running !== null}
        className="inline-flex items-center gap-2 rounded-lg border border-[var(--line-strong)] px-3.5 py-1.5 text-sm text-[var(--text)] transition-colors hover:border-[var(--allow)] hover:bg-[var(--surface-2)] disabled:opacity-50"
      >
        {running === "refund" && <Spinner />}
        {running === "refund" ? "Starting..." : "Run refund (auto allowed)"}
      </button>

      <button
        onClick={() => runAgent("delete")}
        disabled={running !== null}
        className="inline-flex items-center gap-2 rounded-lg border border-[var(--line-strong)] px-3.5 py-1.5 text-sm text-[var(--text)] transition-colors hover:border-[var(--hold)] hover:bg-[var(--surface-2)] disabled:opacity-50"
      >
        {running === "delete" && <Spinner />}
        {running === "delete" ? "Starting..." : "Run delete (gets held)"}
      </button>

      <button
        onClick={resetDemo}
        disabled={resetting}
        className="inline-flex items-center gap-2 rounded-lg border border-[var(--line-strong)] px-3.5 py-1.5 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-50"
      >
        {resetting && <Spinner />}
        {resetting ? "Resetting..." : "Reset demo"}
      </button>

      <input
        type="password"
        placeholder="Demo token"
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
        className="w-40 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] outline-none transition-colors placeholder:text-[var(--faint)] focus:border-[var(--accent)]"
      />
    </div>
  );
}
