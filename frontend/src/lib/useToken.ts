"use client";

import { useState } from "react";

const STORAGE_KEY = "aegis-demo-token";

export function useToken() {
  const [token, setTokenState] = useState(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  });

  const setToken = (value: string) => {
    setTokenState(value);
    window.localStorage.setItem(STORAGE_KEY, value);
  };

  return { token, setToken };
}
