"use client";

import { useState } from "react";

export function CodeBlock({ lines, label }: { lines: string[]; label?: string }) {
  const [copied, setCopied] = useState(false);
  const text = lines.join("\n");

  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--surface)]">
      <div className="flex items-center justify-between border-b border-[var(--line)] bg-[var(--surface-2)] px-4 py-2">
        <span className="text-xs font-mono text-[var(--faint)]">{label ?? "terminal"}</span>
        <button
          onClick={copy}
          className="rounded-md border border-[var(--line-strong)] px-2 py-1 text-xs text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--text)]"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-sm leading-relaxed">
        {lines.map((line, i) => {
          const isComment = line.startsWith("#");
          const isContinuation = line.startsWith(" ") || line === "";
          return (
            <div key={i} className="font-mono">
              {isComment ? (
                <span className="text-[var(--faint)]">{line}</span>
              ) : isContinuation ? (
                <span className="text-[var(--text)]">{line || " "}</span>
              ) : (
                <>
                  <span style={{ color: "var(--brand)" }}>$ </span>
                  <span className="text-[var(--text)]">{line}</span>
                </>
              )}
            </div>
          );
        })}
      </pre>
    </div>
  );
}
