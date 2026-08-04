export function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = Math.round((value ?? 0) * 100);
  const tone = pct >= 75 ? "var(--block)" : pct >= 40 ? "var(--hold)" : "var(--allow)";

  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-[var(--muted)]">{label}</span>
        <span className="font-mono text-[var(--text)]">{value === null ? "n/a" : pct}</span>
      </div>
      <div
        className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-2)]"
        role="meter"
        aria-label={label}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%`, background: tone }}
        />
      </div>
    </div>
  );
}
