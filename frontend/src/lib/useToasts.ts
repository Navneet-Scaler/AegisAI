"use client";

import { useCallback, useState } from "react";

import type { ToastMessage, ToastTone } from "@/components/dashboard/Toast";

let nextId = 1;

export function useToasts() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const push = useCallback((text: string, tone: ToastTone = "info") => {
    const id = nextId++;
    setToasts((current) => [...current, { id, text, tone }]);
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  return { toasts, push };
}
