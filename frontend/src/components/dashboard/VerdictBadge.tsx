import type { Verdict } from "@/lib/api";

const STYLE: Record<Verdict, { label: string; color: string; bg: string }> = {
  allow: { label: "Allowed", color: "var(--allow)", bg: "var(--allow)" },
  hold: { label: "Held", color: "var(--hold)", bg: "var(--hold)" },
  block: { label: "Blocked", color: "var(--block)", bg: "var(--block)" },
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const style = STYLE[verdict];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium"
      style={{
        color: style.color,
        borderColor: `color-mix(in srgb, ${style.bg} 45%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${style.bg} 12%, transparent)`,
      }}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: style.bg }} />
      {style.label}
    </span>
  );
}
