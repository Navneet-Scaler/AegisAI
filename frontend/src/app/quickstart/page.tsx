import Link from "next/link";

import { Logo } from "@/components/brand/Logo";
import { CodeBlock } from "@/components/landing/CodeBlock";
import { Nav } from "@/components/landing/Nav";
import { Reveal } from "@/components/landing/Reveal";

const STEPS = [
  {
    n: "01",
    title: "Run AegisAI",
    body: "No API keys required. Falls back to a mock judge and SQLite automatically, so the whole stack comes up from a clean clone.",
    code: {
      label: "terminal",
      lines: [
        "git clone https://github.com/Navneet-Scaler/AegisAI",
        "cd AegisAI",
        "docker compose up",
        "",
        "# API on :8000, dashboard on :3000",
      ],
    },
  },
  {
    n: "02",
    title: "Mint a key",
    body: "No signup. The key is returned once, you keep it. Every call to the guard endpoint authenticates with it.",
    code: {
      label: "terminal",
      lines: [
        "curl -X POST localhost:8000/v1/keys -d \"{}\"",
        "",
        "# { \"key\": \"ag_live_...\", \"key_id\": \"...\" }",
        "export AEGIS_API_KEY=ag_live_...",
      ],
    },
  },
  {
    n: "03",
    title: "Score a call over curl",
    body: "Before your agent executes a tool call, send it here first. The response carries the verdict, the three layer scores, and the judge's reasoning.",
    code: {
      label: "terminal",
      lines: [
        "curl -X POST localhost:8000/v1/guard \\",
        '  -H "Authorization: Bearer $AEGIS_API_KEY" \\',
        "  -H \"Content-Type: application/json\" \\",
        "  -d '{",
        '    "tool": "delete_customer",',
        '    "args": {"customer_ids": ["CUST-1002"]},',
        '    "user_request": "Remove this customer",',
        '    "agent_id": "support-agent"',
        "  }'",
        "",
        "# { \"verdict\": \"hold\", \"score\": 0.81, \"reasoning\": \"...\" }",
      ],
    },
  },
];

const INTEGRATIONS = [
  {
    id: "python",
    name: "Plain Python",
    body: "The guard() call that everything else below reduces to: one HTTP request before a tool executes.",
    code: {
      label: "guard.py",
      lines: [
        "import os, requests",
        "",
        "def guard(tool_name, arguments, user_request, history):",
        '    r = requests.post(',
        '        "http://localhost:8000/v1/guard",',
        '        headers={"Authorization": f"Bearer {os.environ[\'AEGIS_API_KEY\']}"},',
        "        json={",
        '            "tool": tool_name,',
        '            "args": arguments,',
        '            "user_request": user_request,',
        '            "history": history,',
        "        },",
        "    )",
        "    return r.json()",
        "",
        "verdict = guard(\"delete_customer\", {\"customer_ids\": [\"CUST-1002\"]}, ",
        '                 "Remove this customer", [])',
        'if verdict["verdict"] == "block":',
        "    raise RuntimeError(verdict[\"reasoning\"])",
        'elif verdict["verdict"] == "hold":',
        "    # surface to a human, poll /calls/{call_id} for the decision",
        "    ...",
        "else:",
        "    execute_tool(...)",
      ],
    },
  },
  {
    id: "openai",
    name: "OpenAI function calling",
    body: "Insert the guard call between the model proposing a tool call and your code executing it. Full runnable example in examples/openai-function-calling/.",
    code: {
      label: "agent.py",
      lines: [
        "for call in response.choices[0].message.tool_calls:",
        "    args = json.loads(call.function.arguments)",
        "    verdict = guard(call.function.name, args, user_request, history)",
        "",
        '    if verdict["verdict"] == "block":',
        '        output = {"error": f"blocked: {verdict[\'reasoning\']}"}',
        '    elif verdict["verdict"] == "hold":',
        '        output = {"status": "held_for_review", "call_id": verdict["call_id"]}',
        "    else:",
        "        output = execute_tool(call.function.name, args)",
      ],
    },
  },
  {
    id: "langchain",
    name: "LangChain",
    body: "Wrap each StructuredTool so the guard call runs inside the tool's own func, transparent to the agent executor. Full example in examples/langchain/.",
    code: {
      label: "guarded_tool.py",
      lines: [
        "from langchain_core.tools import StructuredTool",
        "",
        "def guarded(tool_fn, tool_name, user_request):",
        "    def wrapped(**kwargs):",
        "        verdict = guard(tool_name, kwargs, user_request, [])",
        '        if verdict["verdict"] != "allow":',
        '            return f"{verdict[\'verdict\']}: {verdict[\'reasoning\']}"',
        "        return tool_fn(**kwargs)",
        "    return wrapped",
        "",
        "guarded_tools = [",
        "    StructuredTool.from_function(",
        "        func=guarded(delete_customer, \"delete_customer\", user_request),",
        '        name="delete_customer",',
        "    ),",
        "    # ... one per tool",
        "]",
      ],
    },
  },
  {
    id: "mcp",
    name: "MCP server",
    body: "Run the bundled MCP server and every tools/call routed through it is guarded before the underlying tool runs, with no changes on the client side. Source in examples/mcp-server/.",
    code: {
      label: "terminal",
      lines: [
        "export AEGIS_BASE_URL=http://localhost:8000",
        "export AEGIS_API_KEY=$(curl -s -X POST $AEGIS_BASE_URL/v1/keys \\",
        "  -H \"Content-Type: application/json\" -d '{}' | python3 -c \\",
        "  \"import json,sys; print(json.load(sys.stdin)['key'])\")",
        "",
        "uv run examples/mcp-server/server.py",
        "",
        "# speaks JSON-RPC 2.0 over stdio, same transport Claude Desktop uses",
      ],
    },
  },
];

export default function QuickstartPage() {
  return (
    <>
      <Nav />
      <main className="bg-[var(--bg)] text-[var(--text)]">
        <section className="border-b border-[var(--border)]">
          <div className="mx-auto max-w-4xl px-6 py-20 sm:py-28">
            <Reveal>
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
                Wire this into your agent in 5 minutes
              </h1>
              <p className="mt-4 max-w-xl text-[var(--muted)] leading-relaxed">
                AegisAI is a chokepoint, not a framework. If your agent can make one HTTP
                request before it executes a tool call, it can be guarded.
              </p>
            </Reveal>
          </div>
        </section>

        <section className="border-b border-[var(--border)]">
          <div className="mx-auto max-w-4xl px-6 py-16 sm:py-20 space-y-16">
            {STEPS.map((step) => (
              <Reveal key={step.n}>
                <div className="grid gap-6 lg:grid-cols-2 lg:gap-10 items-start">
                  <div>
                    <span
                      className="font-mono text-4xl font-bold"
                      style={{ color: "var(--brand)" }}
                    >
                      {step.n}
                    </span>
                    <h2 className="mt-3 text-xl font-semibold tracking-tight">{step.title}</h2>
                    <p className="mt-2 max-w-sm text-[var(--muted)] leading-relaxed">
                      {step.body}
                    </p>
                  </div>
                  <CodeBlock label={step.code.label} lines={step.code.lines} />
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <section className="border-b border-[var(--border)]">
          <div className="mx-auto max-w-4xl px-6 py-16 sm:py-20">
            <Reveal>
              <h2 className="text-sm font-mono uppercase tracking-widest text-[var(--text-faint)]">
                Pick your integration
              </h2>
              <p className="mt-4 max-w-xl text-2xl leading-snug tracking-tight">
                The guard call is the same everywhere. Only how you insert it changes.
              </p>
            </Reveal>

            <div className="mt-12 space-y-14">
              {INTEGRATIONS.map((item) => (
                <Reveal key={item.id}>
                  <h3 className="text-base font-semibold tracking-tight">{item.name}</h3>
                  <p className="mt-1.5 max-w-2xl text-sm text-[var(--muted)] leading-relaxed">
                    {item.body}
                  </p>
                  <div className="mt-4">
                    <CodeBlock label={item.code.label} lines={item.code.lines} />
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-4xl px-6 py-16 sm:py-20 text-center">
            <Reveal>
              <p className="text-2xl sm:text-3xl font-semibold tracking-tight">
                Watch it decide, live.
              </p>
              <p className="mt-3 text-[var(--muted)]">
                The dashboard streams every call as it is scored, held, and resolved.
              </p>
              <Link
                href="/dashboard"
                className="mt-7 inline-block rounded-full px-7 py-3.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                style={{ background: "var(--brand)" }}
              >
                Open the dashboard
              </Link>
            </Reveal>
          </div>
        </section>

        <footer className="mx-auto max-w-4xl px-6 py-10">
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
