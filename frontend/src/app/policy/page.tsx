"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ToastStack } from "@/components/dashboard/Toast";
import { api, ApiError, type DryRunResult, type PolicyVersionSummary } from "@/lib/api";
import { useToken } from "@/lib/useToken";
import { useToasts } from "@/lib/useToasts";

export default function PolicyPage() {
  const { token, setToken } = useToken();
  const { toasts, push: notify } = useToasts();

  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [policyId, setPolicyId] = useState("default");
  const [source, setSource] = useState<"seed" | "saved" | null>(null);
  const [rulesText, setRulesText] = useState("");
  const [versions, setVersions] = useState<PolicyVersionSummary[]>([]);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState<"dry-run" | "save" | string | null>(null);

  useEffect(() => {
    api.listPolicyIds().then(setPolicyIds).catch(() => {});
  }, []);

  const loadPolicy = (id: string) => {
    api
      .policyRules(id)
      .then((res) => {
        setSource(res.source);
        setRulesText(JSON.stringify(res.rules, null, 2));
        setDryRunResult(null);
      })
      .catch(() => notify(`Could not load policy ${id}`, "error"));
    api
      .policyVersions(id)
      .then(setVersions)
      .catch(() => {});
  };

  useEffect(() => {
    loadPolicy(policyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policyId]);

  const parsedRules = () => {
    try {
      const parsed = JSON.parse(rulesText);
      if (!Array.isArray(parsed)) throw new Error("must be a JSON array of rules");
      return parsed;
    } catch (err) {
      notify(`Invalid JSON: ${err instanceof Error ? err.message : "parse error"}`, "error");
      return null;
    }
  };

  const runDryRun = async () => {
    const rules = parsedRules();
    if (!rules) return;
    setBusy("dry-run");
    try {
      const result = await api.dryRunPolicy(policyId, rules);
      setDryRunResult(result);
      notify(
        result.would_change === 0
          ? "No historical calls would change verdict."
          : `${result.would_change} of ${result.sample_size} historical calls would change.`,
        result.would_change === 0 ? "success" : "info"
      );
    } catch {
      notify("Dry run failed.", "error");
    } finally {
      setBusy(null);
    }
  };

  const saveDraft = async () => {
    const rules = parsedRules();
    if (!rules) return;
    if (!token) {
      notify("Set the demo token first.", "error");
      return;
    }
    setBusy("save");
    try {
      const version = await api.savePolicyDraft(policyId, rules, description, token);
      notify(`Saved as version ${version.version} (not active yet).`, "success");
      loadPolicy(policyId);
    } catch (err) {
      notify(err instanceof ApiError && err.status === 401 ? "Token rejected." : "Save failed.", "error");
    } finally {
      setBusy(null);
    }
  };

  const activate = async (versionId: string) => {
    if (!token) {
      notify("Set the demo token first.", "error");
      return;
    }
    setBusy(versionId);
    try {
      const version = await api.activatePolicyVersion(policyId, versionId, token);
      notify(`Activated version ${version.version}.`, "success");
      loadPolicy(policyId);
      setDryRunResult(null);
    } catch (err) {
      notify(err instanceof ApiError && err.status === 401 ? "Token rejected." : "Activate failed.", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/dashboard"
            className="text-sm text-[var(--faint)] transition-colors hover:text-[var(--text)]"
          >
            Back to dashboard
          </Link>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">Policy authoring</h1>
          <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
            Edit a policy&apos;s rules, dry run the change against recent history before
            committing to it, then activate. Every activation is a new version; rolling back
            is just activating an older one again.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={policyId}
            onChange={(e) => setPolicyId(e.target.value)}
            className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
          >
            {(policyIds.length ? policyIds : [policyId]).map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <input
            type="password"
            placeholder="Demo token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="w-40 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--faint)]"
          />
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-widest text-[var(--faint)]">
              Rules ({source ?? "..."})
            </span>
          </div>
          <textarea
            value={rulesText}
            onChange={(e) => setRulesText(e.target.value)}
            spellCheck={false}
            className="mt-3 h-96 w-full resize-y rounded-lg border border-[var(--line)] bg-[var(--bg)] p-3 font-mono text-xs text-[var(--text)] outline-none focus:border-[var(--accent)]"
          />

          <input
            type="text"
            placeholder="Description for this version (e.g. 'tighten refund threshold')"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-3 w-full rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--faint)]"
          />

          <div className="mt-3 flex gap-2">
            <button
              onClick={runDryRun}
              disabled={busy !== null}
              className="flex-1 rounded-lg border border-[var(--line-strong)] py-2 text-sm text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-50"
            >
              {busy === "dry-run" ? "Running..." : "Dry run"}
            </button>
            <button
              onClick={saveDraft}
              disabled={busy !== null}
              className="flex-1 rounded-lg py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              {busy === "save" ? "Saving..." : "Save as new version"}
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          {dryRunResult && (
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
              <span className="text-xs font-mono uppercase tracking-widest text-[var(--faint)]">
                Dry run result
              </span>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <Stat label="Sample" value={dryRunResult.sample_size} />
                <Stat label="Would change" value={dryRunResult.would_change} tone="var(--hold)" />
                <Stat label="Newly held" value={dryRunResult.newly_forced_hold} tone="var(--hold)" />
                <Stat
                  label="Newly blocked"
                  value={dryRunResult.newly_forced_block}
                  tone="var(--block)"
                />
              </div>
              {dryRunResult.results.filter((r) => r.changed).length > 0 && (
                <ul className="mt-4 space-y-1.5 max-h-64 overflow-y-auto">
                  {dryRunResult.results
                    .filter((r) => r.changed)
                    .map((r) => (
                      <li
                        key={r.call_id}
                        className="flex items-center justify-between rounded border border-[var(--line)] px-2.5 py-1.5 text-xs"
                      >
                        <code className="text-[var(--text)]">{r.tool_name}</code>
                        <span className="text-[var(--faint)]">
                          {r.actual_verdict_tier} &rarr;{" "}
                          <span style={{ color: "var(--hold)" }}>
                            {r.proposed_forced_verdict ?? "unforced"}
                          </span>
                        </span>
                      </li>
                    ))}
                </ul>
              )}
            </div>
          )}

          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
            <span className="text-xs font-mono uppercase tracking-widest text-[var(--faint)]">
              Version history
            </span>
            <ul className="mt-3 space-y-2">
              {versions.length === 0 && (
                <li className="text-sm text-[var(--faint)]">
                  No saved versions yet, this policy is on its seed file.
                </li>
              )}
              {versions.map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                  style={{ borderColor: v.is_active ? "var(--accent)" : "var(--line)" }}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-mono text-[var(--faint)]">v{v.version}</span>
                      {v.is_active && (
                        <span
                          className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide"
                          style={{ color: "var(--accent)", background: "var(--surface-2)" }}
                        >
                          active
                        </span>
                      )}
                    </div>
                    <div className="truncate text-xs text-[var(--muted)]">
                      {v.description || "(no description)"}
                    </div>
                  </div>
                  {!v.is_active && (
                    <button
                      onClick={() => activate(v.id)}
                      disabled={busy !== null}
                      className="shrink-0 rounded-lg border border-[var(--line-strong)] px-2.5 py-1 text-xs text-[var(--text)] transition-colors hover:bg-[var(--surface-2)] disabled:opacity-50"
                    >
                      {busy === v.id ? "..." : "Activate"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <ToastStack toasts={toasts} />
    </main>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <div className="text-lg font-mono font-semibold" style={{ color: tone ?? "var(--text)" }}>
        {value}
      </div>
      <div className="text-[11px] text-[var(--faint)]">{label}</div>
    </div>
  );
}
