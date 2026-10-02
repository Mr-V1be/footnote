"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

import { createBrowserApi, type ApiClient } from "./client";

const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ children }: { children: ReactNode }) {
  const [api] = useState(createBrowserApi);
  return <ApiContext value={api}>{children}</ApiContext>;
}

export function useApi(): ApiClient {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside ApiProvider");
  return api;
}
