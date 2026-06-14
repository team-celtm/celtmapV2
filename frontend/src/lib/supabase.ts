"use client";

import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

const isConfigured = Boolean(supabaseUrl && supabaseAnonKey);
const missingConfigMessage =
  "Supabase auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
  "NEXT_PUBLIC_SUPABASE_ANON_KEY (or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) " +
  "for the hosted frontend environment.";
const supabaseProjectRef = (() => {
  try {
    return supabaseUrl ? new URL(supabaseUrl).hostname.split(".")[0] : "";
  } catch {
    return "";
  }
})();

export function assertSupabaseConfigured(): void {
  if (isConfigured) {
    return;
  }

  throw new Error(missingConfigMessage);
}

if (!isConfigured) {
  throw new Error(missingConfigMessage);
}

export function isInvalidRefreshTokenError(error: unknown): boolean {
  const value = error && typeof error === "object" ? error as { message?: unknown; name?: unknown } : null;
  const message = String(value?.message ?? error ?? "").toLowerCase();
  const name = String(value?.name ?? "").toLowerCase();
  return (
    name.includes("authapierror") &&
    message.includes("refresh token")
  ) || (
    message.includes("invalid refresh token") ||
    message.includes("refresh token not found") ||
    message.includes("refresh_token_not_found")
  );
}

export function clearSupabaseAuthStorage(): void {
  if (typeof window === "undefined") {
    return;
  }

  const explicitKey = supabaseProjectRef ? `sb-${supabaseProjectRef}-auth-token` : "";
  const clearStorage = (storage: Storage) => {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (!key) {
        continue;
      }
      if (
        key === explicitKey ||
        key === "supabase.auth.token" ||
        /^sb-.*-auth-token$/.test(key) ||
        /^sb-.*-code-verifier$/.test(key)
      ) {
        storage.removeItem(key);
      }
    }
  };

  try {
    clearStorage(window.localStorage);
    clearStorage(window.sessionStorage);
  } catch {
    // Ignore storage access failures.
  }
}

const sessionOnlyAuthStorage = typeof window === "undefined"
  ? undefined
  : {
      getItem: (key: string) => window.sessionStorage.getItem(key),
      setItem: (key: string, value: string) => window.sessionStorage.setItem(key, value),
      removeItem: (key: string) => window.sessionStorage.removeItem(key),
    };

export const supabase = createClient(
  supabaseUrl as string,
  supabaseAnonKey as string,
  {
    auth: {
      persistSession: true,
      autoRefreshToken: false,
      detectSessionInUrl: true,
      storage: sessionOnlyAuthStorage,
    },
  },
);
