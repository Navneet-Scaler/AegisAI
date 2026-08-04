import Link from "next/link";

import { Logo } from "@/components/brand/Logo";
import { InterceptGraphic } from "@/components/landing/InterceptGraphic";
import { Nav } from "@/components/landing/Nav";
import { PipelineDemo } from "@/components/landing/PipelineDemo";
import { Reveal } from "@/components/landing/Reveal";

const LAYERS = [
  {
    n: "01",
    name: "Static rules",
    body: "Hard policy that holds regardless of what the model decides. Destructive verbs, spend thresholds, PII access, recipient allowlists. A rule can force a verdict outright.",
  },
  {
    n: "02",
    name: "Behavioural pattern model",
    body: "An online classifier over call features. Argument shapes this agent has never used before score higher. Every human decision updates the weights immediately.",
  },
  {
    n: "03",
    name: "LLM judge",
    body: "A second model asks whether the proposed call actually follows from what the user asked. This is the layer that catches hijacked intent, which name matching alone cannot.",
  },
];

const FEATURES = [
  {
    group: "Interception",
    items: [
      "One chokepoint every tool call must pass through",
      "Three way verdict: allow, hold for a human, or block",
      "Blocked calls return a structured refusal the agent can adapt to",
      "Framework agnostic, wraps existing tool calling code",
    ],
  },
  {
    group: "Scoring",
    items: [
      "Three independent signals combined into one explainable score",
      "Per layer sub scores persisted on every call",
      "Every dependency fails toward hold, never toward allow",
      "Editable policy rules, no redeploy needed",
    ],
  },
  {
    group: "Learning and audit",
    items: [
      "Online weight updates on every approve or reject",
      "Full audit trail of calls, scores, reasoning, and outcomes",
      "Block rate and drift tracked over time",
      "Per tool and per agent risk breakdown",
    ],
  },
];

export default function Home() {
  return (
    <>
      <Nav />
      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-[var(--border)]">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.18]"
            style={{
              backgroundImage:
                "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
              backgroundSize: "44px 44px",
              maskImage:
                "radial-gradient(ellipse 70% 60% at 50% 0%, #000 40%, transparent 100%)",
            }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -top-40 left-1/2 h-[32rem] w-[32rem] -translate-x-1/2 rounded-full opacity-[0.15] blur-[110px]"
            style={{ background: "var(--brand)" }}
          />

          <div className="relative mx-auto max-w-6xl px-6 pt-16 pb-16 sm:pt-24 sm:pb-24">
            <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 lg:items-center">
              <Reveal>
                <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-mono text-[var(--text-muted)]">
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--brand)" }}
                  />
                  zero trust for AI agents
                </span>

                <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.05]">
                  Constrain the architecture,
                  <br />
                  <span className="text-[var(--text-muted)]">not the prompt.</span>
                </h1>

                <p className="mt-6 max-w-xl text-lg leading-relaxed text-[var(--text-muted)]">
                  AegisAI sits between an AI agent and its tools. Every call the agent
                  proposes is intercepted before it executes, scored by a layered risk
                  engine, and then allowed, held for a human, or blocked.
                </p>

                <div className="mt-9 flex flex-wrap gap-3">
                  <Link
                    href="/dashboard"
                    className="rounded-lg px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                    style={{ background: "var(--brand)" }}
                  >
                    Open the live dashboard
                  </Link>
                  <a
                    href="https://github.com/Navneet-Scaler/AegisAI"
                    className="rounded-lg border border-[var(--border-strong)] px-5 py-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--surface)]"
                  >
                    Read the source
                  </a>
                </div>
              </Reveal>

              <Reveal delay={0.12}>
                <InterceptGraphic />
              </Reveal>
            </div>
          </div>
        </section>

        {/* Live preview */}
        <section className="border-b border-[var(--border)]">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <Reveal>
              <h2 className="text-sm font-mono uppercase tracking-widest text-[var(--text-faint)]">
                What the feed looks like
              </h2>
            </Reveal>
            <Reveal delay={0.08} className="mt-6">
              <PipelineDemo />
            </Reveal>
          </div>
        </section>

        {/* The problem */}
        <section id="approach" className="border-b border-[var(--border)] scroll-mt-16">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <Reveal className="max-w-3xl">
              <h2 className="text-sm font-mono uppercase tracking-widest text-[var(--text-faint)]">
                The problem
              </h2>
              <p className="mt-5 text-2xl sm:text-3xl leading-snug tracking-tight">
                Agent safety is mostly enforced by asking the model nicely.
              </p>
              <p className="mt-5 text-lg leading-relaxed text-[var(--text-muted)]">
                A system prompt saying &ldquo;never delete customer records&rdquo; is
                advisory. It is a string in a context window competing with every other
                string in that context window, including any text the agent happens to read
                from a support ticket. Meanwhile the tools are real: they send email, issue
                refunds, and drop rows.
              </p>
              <p className="mt-4 text-lg leading-relaxed text-[var(--text-muted)]">
                Nothing structural stands between a hijacked agent and the database. AegisAI
                is that structure. It does not ask the agent to behave. It removes the code
                path where misbehaving was possible.
              </p>
            </Reveal>
          </div>
        </section>

        {/* Layers */}
        <section id="scoring" className="border-b border-[var(--border)] scroll-mt-16">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <Reveal>
              <h2 className="text-sm font-mono uppercase tracking-widest text-[var(--text-faint)]">
                How a call is scored
              </h2>
              <p className="mt-5 max-w-2xl text-lg text-[var(--text-muted)]">
                Three independent signals, combined into one score with the reasoning kept
                attached. Any layer can escalate, none can silently wave a call through.
              </p>
            </Reveal>

            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {LAYERS.map((layer, i) => (
                <Reveal key={layer.n} delay={i * 0.08}>
                  <div className="h-full rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 transition-colors hover:border-[var(--border-strong)]">
                    <span className="font-mono text-xs" style={{ color: "var(--brand)" }}>
                      {layer.n}
                    </span>
                    <h3 className="mt-3 text-lg font-medium tracking-tight">{layer.name}</h3>
                    <p className="mt-3 text-sm leading-relaxed text-[var(--text-muted)]">
                      {layer.body}
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>

            <Reveal delay={0.24}>
              <div className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-6">
                <pre className="overflow-x-auto text-sm font-mono leading-relaxed text-[var(--text-muted)]">
{`score = 0.35 * rule + 0.30 * pattern + 0.35 * judge

score >= 0.75          ->  block
0.40 <= score < 0.75   ->  hold for human approval
score <  0.40          ->  allow
any forcing rule       ->  that verdict wins`}
                </pre>
              </div>
            </Reveal>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="border-b border-[var(--border)] scroll-mt-16">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <Reveal>
              <h2 className="text-sm font-mono uppercase tracking-widest text-[var(--text-faint)]">
                What it does
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-10 md:grid-cols-3">
              {FEATURES.map((group, i) => (
                <Reveal key={group.group} delay={i * 0.08}>
                  <h3 className="text-base font-medium tracking-tight">{group.group}</h3>
                  <ul className="mt-4 space-y-3">
                    {group.items.map((item) => (
                      <li
                        key={item}
                        className="flex gap-3 text-sm leading-relaxed text-[var(--text-muted)]"
                      >
                        <span
                          aria-hidden
                          className="mt-1.5 h-1 w-1 shrink-0 rounded-full"
                          style={{ background: "var(--brand)" }}
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <footer className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Logo size={20} />
            <a
              className="text-sm text-[var(--text-faint)] transition-colors hover:text-[var(--text)]"
              href="https://github.com/Navneet-Scaler/AegisAI"
            >
              github.com/Navneet-Scaler/AegisAI
            </a>
          </div>
        </footer>
      </main>
    </>
  );
}
