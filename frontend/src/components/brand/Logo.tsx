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
      {/* The checkpoint: a rounded gate every call passes through. */}
      <rect
        x="3"
        y="3"
        width="26"
        height="26"
        rx="8"
        stroke="var(--brand)"
        strokeWidth="2"
        fill="var(--brand-glow)"
      />
      {/* One call comes in, and is routed: through, or held at the gate. */}
      <path
        d="M8 16 H14"
        stroke="var(--brand)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="14" cy="16" r="1.6" fill="var(--brand)" />
      <path
        d="M14 16 L21 10"
        stroke="var(--brand)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M14 16 L21 22"
        stroke="var(--brand)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeOpacity="0.45"
      />
      <circle cx="21.5" cy="9.5" r="1.9" fill="var(--brand)" />
      <circle cx="21.5" cy="22.5" r="1.9" stroke="var(--brand)" strokeWidth="1.6" fill="var(--bg)" />
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
