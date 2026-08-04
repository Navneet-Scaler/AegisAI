export function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5">
      <div className="text-xs text-[var(--faint)]">{label}</div>
      <div
        className="mt-2 text-3xl font-semibold tracking-tight tabular-nums"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
    </div>
  );
}
