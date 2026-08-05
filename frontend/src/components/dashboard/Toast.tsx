"use client";

import { AnimatePresence, motion } from "framer-motion";

export type ToastTone = "info" | "success" | "error";

export interface ToastMessage {
  id: number;
  text: string;
  tone: ToastTone;
}

const TONE_COLOR: Record<ToastTone, string> = {
  info: "var(--accent)",
  success: "var(--allow)",
  error: "var(--block)",
};

export function ToastStack({ toasts }: { toasts: ToastMessage[] }) {
  return (
    <div
      className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col gap-2"
      aria-live="polite"
    >
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, y: 12, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 24, transition: { duration: 0.15 } }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="pointer-events-auto flex items-center gap-2.5 rounded-lg border px-4 py-2.5 text-sm shadow-lg backdrop-blur-md"
            style={{
              borderColor: TONE_COLOR[toast.tone],
              background: "color-mix(in srgb, var(--surface) 92%, transparent)",
              color: "var(--text)",
            }}
          >
            <span
              aria-hidden
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ background: TONE_COLOR[toast.tone] }}
            />
            {toast.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
