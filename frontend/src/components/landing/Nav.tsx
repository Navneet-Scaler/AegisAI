"use client";

import Link from "next/link";
import { motion } from "framer-motion";

import { Logo } from "@/components/brand/Logo";

export function Nav() {
  return (
    <motion.header
      initial={{ y: -16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <Link href="/" aria-label="AegisAI home">
          <Logo size={24} />
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-[var(--muted)] sm:flex">
          <a href="#approach" className="transition-colors hover:text-[var(--text)]">
            Approach
          </a>
          <a href="#scoring" className="transition-colors hover:text-[var(--text)]">
            Scoring
          </a>
          <a href="#features" className="transition-colors hover:text-[var(--text)]">
            Features
          </a>
          <Link href="/dashboard" className="transition-colors hover:text-[var(--text)]">
            Dashboard
          </Link>
        </nav>

        <a
          href="https://github.com/Navneet-Scaler/AegisAI"
          className="rounded-md border border-[var(--line-strong)] px-3 py-1.5 text-xs font-medium text-[var(--text)] transition-colors hover:bg-[var(--surface)]"
        >
          GitHub
        </a>
      </div>
    </motion.header>
  );
}
