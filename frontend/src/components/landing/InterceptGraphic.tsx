"use client";

import { motion, useReducedMotion } from "framer-motion";

/*
  The mechanism, drawn: a call leaves the agent, passes through the gate,
  and the gate routes it to one of three outcomes. This is not decorative,
  it is the same three way verdict described in prose everywhere else on
  the page, so changing the routing here without changing the copy would be
  a bug, not a redesign.
*/

const OUTCOMES = [
  { key: "allow", y: 40, color: "var(--allow)", label: "allow" },
  { key: "hold", y: 110, color: "var(--hold)", label: "hold" },
  { key: "block", y: 180, color: "var(--block)", label: "block" },
] as const;

const AGENT = { x: 30, y: 110 };
const GATE = { x: 200, y: 110 };
const END_X = 330;

function pathFor(y: number) {
  return `M${GATE.x} ${GATE.y} L${END_X} ${y}`;
}

export function InterceptGraphic() {
  const reduced = useReducedMotion();

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6">
      <svg
        viewBox="0 0 440 220"
        className="w-full h-auto"
        role="img"
        aria-label="A call leaves the agent, passes through the AegisAI gate, and is routed to allow, hold, or block"
      >
        {/* agent -> gate */}
        <motion.line
          x1={AGENT.x}
          y1={AGENT.y}
          x2={GATE.x}
          y2={GATE.y}
          stroke="var(--border-strong)"
          strokeWidth={2}
          initial={reduced ? undefined : { pathLength: 0 }}
          whileInView={reduced ? undefined : { pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />

        {/* gate -> each outcome */}
        {OUTCOMES.map((o, i) => (
          <motion.path
            key={o.key}
            d={pathFor(o.y)}
            stroke="var(--border-strong)"
            strokeWidth={2}
            fill="none"
            initial={reduced ? undefined : { pathLength: 0 }}
            whileInView={reduced ? undefined : { pathLength: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.3 + i * 0.1, ease: "easeOut" }}
          />
        ))}

        {/* agent node */}
        <circle cx={AGENT.x} cy={AGENT.y} r={9} fill="var(--surface-2)" stroke="var(--line-strong)" strokeWidth={2} />
        <text x={AGENT.x} y={AGENT.y + 26} textAnchor="middle" className="fill-[var(--faint)]" fontSize="11" fontFamily="var(--font-geist-mono)">
          agent
        </text>

        {/* the gate itself */}
        <motion.g
          initial={reduced ? undefined : { scale: 0.85, opacity: 0 }}
          whileInView={reduced ? undefined : { scale: 1, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <rect
            x={GATE.x - 24}
            y={GATE.y - 24}
            width={48}
            height={48}
            rx={10}
            fill="var(--brand-glow)"
            stroke="var(--brand)"
            strokeWidth={2}
          />
          <path
            d={`M${GATE.x - 9} ${GATE.y} l6 6 l12 -13`}
            stroke="var(--brand)"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </motion.g>
        <text
          x={GATE.x}
          y={GATE.y + 42}
          textAnchor="middle"
          className="fill-[var(--text)]"
          fontSize="11"
          fontWeight={600}
          fontFamily="var(--font-geist-mono)"
        >
          AegisAI
        </text>

        {/* outcomes */}
        {OUTCOMES.map((o) => (
          <g key={o.key}>
            <circle cx={END_X} cy={o.y} r={5} fill={o.color} />
            <text
              x={END_X + 12}
              y={o.y + 4}
              className="fill-[var(--muted)]"
              fontSize="12"
              fontFamily="var(--font-geist-mono)"
            >
              {o.label}
            </text>
          </g>
        ))}

        {/* traveling signal, staggered per outcome, off entirely under reduced motion */}
        {!reduced &&
          OUTCOMES.map((o, i) => (
            <motion.circle
              key={o.key}
              r={4}
              fill={o.color}
              initial={{ cx: GATE.x, cy: GATE.y, opacity: 0 }}
              animate={{
                cx: [GATE.x, END_X],
                cy: [GATE.y, o.y],
                opacity: [0, 1, 1, 0],
              }}
              transition={{
                duration: 1.6,
                repeat: Infinity,
                repeatDelay: 2.4,
                delay: i * 0.9,
                ease: "easeInOut",
              }}
            />
          ))}
      </svg>
    </div>
  );
}
