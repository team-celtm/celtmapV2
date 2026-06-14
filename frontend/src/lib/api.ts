"use client";

import type { Session } from "@supabase/supabase-js";

import { clearSupabaseAuthStorage, isInvalidRefreshTokenError, supabase } from "./supabase";

const envApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const isEnvInvalid = !envApiUrl || envApiUrl === 'undefined' || envApiUrl === 'null' || envApiUrl.trim() === '';

if (isEnvInvalid) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL must be configured for the hosted CELTM frontend.");
}

export const apiBaseUrl = envApiUrl.replace(/\/$/, "");

const defaultCacheTtlMs = 300_000;
const cacheNamespace = "celtm-api-cache:";

type ApiFetchOptions = RequestInit & {
  cacheTtlMs?: number;
  skipCache?: boolean;
  revalidate?: boolean;
  onCacheHit?: (data: unknown) => void;
};

interface CachedResponseEntry {
  expiresAt: number;
  payload: unknown;
}

const responseCache = new Map<string, CachedResponseEntry>();
const inflightRequests = new Map<string, Promise<unknown>>();
let activeSessionSnapshot: Session | null | undefined;
let refreshPromise: Promise<Session | null> | null = null;

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

const extractApiErrorMessage = (payload: unknown, status: number): string => {
  if (typeof payload === "object" && payload) {
    if ("message" in payload && typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }

    if ("detail" in payload && typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  }

  return `Request failed with status ${status}`;
};

const clonePayload = <T>(payload: T): T => {
  if (payload == null || typeof payload !== "object") {
    return payload;
  }

  if (typeof structuredClone === "function") {
    return structuredClone(payload);
  }

  return JSON.parse(JSON.stringify(payload)) as T;
};

const clearInvalidAuthState = async () => {
  activeSessionSnapshot = null;
  clearCachedResponses();
  clearSupabaseAuthStorage();
  try {
    await supabase.auth.signOut({ scope: "local" });
  } catch {
    // The refresh token is already invalid; local storage has been cleared.
  }
};

const refreshActiveSession = async (): Promise<Session | null> => {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const {
        data: { session: refreshedSession },
        error,
      } = await supabase.auth.refreshSession();

      if (error) {
        if (isInvalidRefreshTokenError(error)) {
          await clearInvalidAuthState();
          return null;
        }
        activeSessionSnapshot = null;
        return null;
      }

      activeSessionSnapshot = refreshedSession;
      return refreshedSession;
    } catch (err) {
      if (isInvalidRefreshTokenError(err)) {
        await clearInvalidAuthState();
        return null;
      }
      activeSessionSnapshot = null;
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
};

const buildHeaders = async (headers?: HeadersInit) => {
  const resolvedHeaders = new Headers(headers);
  let session = activeSessionSnapshot;

  if (session === undefined) {
    try {
      const {
        data: { session: liveSession },
        error,
      } = await supabase.auth.getSession();
      if (error) {
        if (isInvalidRefreshTokenError(error)) {
          await clearInvalidAuthState();
        } else {
          activeSessionSnapshot = null;
        }
        session = null;
      } else {
        activeSessionSnapshot = liveSession;
        session = liveSession;
      }
    } catch (err) {
      if (isInvalidRefreshTokenError(err)) {
        await clearInvalidAuthState();
      } else {
        activeSessionSnapshot = null;
      }
      session = null;
    }
  }

  // Pre-emptive refresh if session is about to expire
  if (session?.expires_at && session.expires_at * 1000 <= Date.now() + 30_000) {
    session = await refreshActiveSession();
  }

  if (session?.access_token) {
    resolvedHeaders.set("Authorization", `Bearer ${session.access_token}`);
  }
  
  return {
    headers: resolvedHeaders,
    identityKey: session?.user?.id || "anonymous",
    session,
  };
};

const canCacheRequest = (init: ApiFetchOptions) => {
  const method = (init.method || "GET").toUpperCase();
  return method === "GET" && !init.body && !init.skipCache && init.cache !== "no-store";
};

const isAbortLikeError = (error: unknown) => {
  if (!error || typeof error !== "object") {
    return false;
  }

  const name = "name" in error ? String((error as { name?: unknown }).name) : "";
  return name === "AbortError" || name === "TimeoutError";
};

const clearCachedResponses = () => {
  responseCache.clear();
  inflightRequests.clear();

  if (typeof window === "undefined") {
    return;
  }

  try {
    for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = window.sessionStorage.key(index);
      if (key?.startsWith(cacheNamespace)) {
        window.sessionStorage.removeItem(key);
      }
    }
  } catch {
    // Ignore storage access errors.
  }
};

export const setApiAuthSession = (session: Session | null) => {
  const previousIdentity = activeSessionSnapshot?.user?.id || "anonymous";
  const nextIdentity = session?.user?.id || "anonymous";

  activeSessionSnapshot = session;

  if (previousIdentity !== nextIdentity) {
    clearCachedResponses();
  }
};

const readSessionCache = (cacheKey: string): CachedResponseEntry | null => {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawEntry = window.sessionStorage.getItem(`${cacheNamespace}${cacheKey}`);
    if (!rawEntry) {
      return null;
    }

    const parsedEntry = JSON.parse(rawEntry) as CachedResponseEntry;
    if (parsedEntry.expiresAt <= Date.now()) {
      window.sessionStorage.removeItem(`${cacheNamespace}${cacheKey}`);
      return null;
    }

    return parsedEntry;
  } catch {
    return null;
  }
};

const writeSessionCache = (cacheKey: string, entry: CachedResponseEntry) => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(
      `${cacheNamespace}${cacheKey}`,
      JSON.stringify(entry),
    );
  } catch {
    // Ignore storage quota and serialization failures.
  }
};

const getCachedEntry = (cacheKey: string): CachedResponseEntry | null => {
  const inMemoryEntry = responseCache.get(cacheKey);
  if (inMemoryEntry && inMemoryEntry.expiresAt > Date.now()) {
    return inMemoryEntry;
  }

  if (inMemoryEntry) {
    responseCache.delete(cacheKey);
  }

  const persistedEntry = readSessionCache(cacheKey);
  if (persistedEntry) {
    responseCache.set(cacheKey, persistedEntry);
    return persistedEntry;
  }

  return null;
};

export async function apiFetch<T>(path: string, init: ApiFetchOptions = {}): Promise<T> {
  const { headers, identityKey, session } = await buildHeaders(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  let requestUrl = `${apiBaseUrl}${normalizedPath}`;
  
  // Add refresh=true query parameter if revalidate is set and this is a dashboard summary request
  if (init.revalidate && normalizedPath.includes("/dashboard/summary")) {
    const separator = requestUrl.includes("?") ? "&" : "?";
    requestUrl = `${requestUrl}${separator}refresh=true`;
  }
  const shouldCache = canCacheRequest(init);
  const cacheKey = shouldCache
    ? `${identityKey}:${(init.method || "GET").toUpperCase()}:${requestUrl}`
    : null;
  const cacheTtlMs = init.cacheTtlMs ?? defaultCacheTtlMs;
  const canShareInflightRequest = cacheKey && !init.signal;

  if (cacheKey && !init.revalidate) {
    const cachedEntry = getCachedEntry(cacheKey);
    if (cachedEntry) {
      return clonePayload(cachedEntry.payload as T);
    }

    if (canShareInflightRequest) {
      const inflightRequest = inflightRequests.get(cacheKey);
      if (inflightRequest) {
        return clonePayload((await inflightRequest) as T);
      }
    }
  }

  const requestPromise = (async () => {
    const executeRequest = async (requestHeaders: Headers) =>
      fetch(requestUrl, {
        ...init,
        headers: requestHeaders,
      });

    let response: Response;
    try {
      response = await executeRequest(headers);
    } catch (err) {
      if (isAbortLikeError(err)) {
        throw err;
      }
      console.error(`[api-fetch] Network failure for ${requestUrl}:`, err);
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        throw new Error(
          `Backend API is not reachable for ${normalizedPath}. Verify NEXT_PUBLIC_API_BASE_URL and hosted CORS configuration for ${apiBaseUrl}.`,
        );
      }
      throw err;
    }

    // Harden: If 401, try to sync session once
    if (response.status === 401) {
      console.warn(`[api-fetch] 401 Unauthorized for ${normalizedPath}. Synchronizing...`);
      const refreshedSession = await refreshActiveSession();

      if (
        refreshedSession?.access_token &&
        refreshedSession.access_token !== session?.access_token
      ) {
        const retryHeaders = new Headers(headers);
        retryHeaders.set("Authorization", `Bearer ${refreshedSession.access_token}`);
        try {
          response = await executeRequest(retryHeaders);
        } catch (retryErr) {
          if (isAbortLikeError(retryErr)) {
            throw retryErr;
          }
          console.error(`[api-fetch] Network failure on retry for ${requestUrl}:`, retryErr);
          throw retryErr;
        }
      }
    }

    const contentType = response.headers.get("content-type") || "";
    let payload: unknown;
    try {
      payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
    } catch (parseErr) {
      console.error(`[api-fetch] Failed to parse response from ${requestUrl}:`, parseErr);
      throw new ApiError(
        `Failed to parse ${contentType} response from ${normalizedPath}`,
        response.status,
        null,
      );
    }

    if (!response.ok) {
      const message = extractApiErrorMessage(payload, response.status);
      console.warn(`[api-fetch] Request failed for ${normalizedPath}:`, {
        status: response.status,
        message,
        payload,
      });
      throw new ApiError(message, response.status, payload);
    }

    if (cacheKey) {
      const entry: CachedResponseEntry = {
        expiresAt: Date.now() + cacheTtlMs,
        payload: clonePayload(payload),
      };
      responseCache.set(cacheKey, entry);
      writeSessionCache(cacheKey, entry);
    } else if ((init.method || "GET").toUpperCase() !== "GET") {
      clearCachedResponses();
    }

    return payload as T;
  })();

  if (canShareInflightRequest) {
    inflightRequests.set(cacheKey, requestPromise);
  }

  try {
    const payload = await requestPromise;
    return clonePayload(payload);
  } finally {
    if (canShareInflightRequest) {
      inflightRequests.delete(cacheKey);
    }
  }
}

export async function apiFetchBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const { headers, session } = await buildHeaders(init.headers);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const requestUrl = `${apiBaseUrl}${normalizedPath}`;

  const executeRequest = async (requestHeaders: Headers) =>
    fetch(requestUrl, {
      ...init,
      headers: requestHeaders,
    });

  let response = await executeRequest(headers);

  if (response.status === 401 && session?.refresh_token) {
    const refreshedSession = await refreshActiveSession();

    if (
      refreshedSession?.access_token &&
      refreshedSession.access_token !== session.access_token
    ) {
      const retryHeaders = new Headers(headers);
      retryHeaders.set("Authorization", `Bearer ${refreshedSession.access_token}`);
      response = await executeRequest(retryHeaders);
    }
  }

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    const message = extractApiErrorMessage(payload, response.status);
    throw new ApiError(message, response.status, payload);
  }

  return response.blob();
}
