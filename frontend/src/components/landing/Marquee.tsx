"use client";

import { useReducedMotion } from "framer-motion";

export function Marquee({ items }: { items: string[] }) {
  const reduced = useReducedMotion();
  const loop = [...items, ...items];

  return (
    <div className="overflow-hidden border-y border-[var(--line)] bg-[var(--surface)] py-3">
      <div
        className={reduced ? "flex flex-wrap justify-center gap-x-10 gap-y-2 px-6" : "flex w-max"}
        style={reduced ? undefined : { animation: "marquee 28s linear infinite" }}
      >
        {(reduced ? items : loop).map((item, i) => (
          <span
            key={i}
            className="mx-5 shrink-0 font-mono text-xs uppercase tracking-widest text-[var(--faint)]"
          >
            {item}
            {!reduced && <span className="ml-10 text-[var(--brand)]">/</span>}
          </span>
        ))}
      </div>
      {!reduced && (
        <style>{`
          @keyframes marquee {
            from { transform: translateX(0); }
            to { transform: translateX(-50%); }
          }
        `}</style>
      )}
    </div>
  );
}
