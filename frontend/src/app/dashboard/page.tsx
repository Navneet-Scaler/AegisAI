import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-20">
      <Link
        href="/"
        className="text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
      >
        Back
      </Link>
      <h1 className="mt-6 text-3xl font-semibold tracking-tight">Live decision feed</h1>
      <p className="mt-4 max-w-xl text-[var(--text-muted)]">
        The dashboard streams intercepted tool calls, their layered risk scores, and the
        approve or block controls. It arrives in the dashboard phase of the build.
      </p>
    </main>
  );
}
