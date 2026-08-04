export function LogoMark({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M16 2 L28 7 V15 C28 22.5 23 27.5 16 30 C9 27.5 4 22.5 4 15 V7 Z"
        stroke="var(--brand)"
        strokeWidth="2"
        strokeLinejoin="round"
        fill="var(--brand-glow)"
      />
      {/* The gate: a call is either let through, or stopped at the line. */}
      <path
        d="M11 16 L14.5 19.5 L21.5 12"
        stroke="var(--brand)"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className ?? ""}`}>
      <LogoMark size={size} />
      <span
        className="font-mono font-semibold tracking-tight text-[var(--text)]"
        style={{ fontSize: size * 0.62 }}
      >
        AegisAI
      </span>
    </span>
  );
}
