"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { AnimatePresence, motion as Motion } from "framer-motion";
import { apiFetch } from "@/lib/api";
import type { CareerRoleOption, CareerRoleSuggestion } from "@/lib/celtm";
import AppIcon from "@/components/AppIcon";

interface CareerRoleInputProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: CareerRoleOption[];
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  inputClassName?: string;
}

interface MenuPosition {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
  placement: "top" | "bottom";
}

function normalize(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, " ");
}

function compact(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function tokens(value: string) {
  return normalize(value).split(" ").filter(Boolean);
}

function optionMatches(option: CareerRoleOption, query: string) {
  const cleanQuery = normalize(query);
  if (!cleanQuery) {
    return true;
  }
  const candidates = [option.label, option.value, ...(option.aliases ?? [])];
  const haystack = normalize([...candidates, option.description ?? ""].join(" "));
  const haystackTokens = tokens(haystack);
  const queryTokens = tokens(cleanQuery);
  const compactQuery = compact(cleanQuery);
  const compactCandidates = candidates.map((candidate) => compact(candidate));

  if (compactQuery.length >= 5 && compactCandidates.some((candidate) => candidate.includes(compactQuery))) {
    return true;
  }

  return queryTokens.every((queryToken) =>
    haystackTokens.some((hayToken) => hayToken === queryToken || hayToken.startsWith(queryToken)),
  );
}

function optionKey(option: CareerRoleOption) {
  return normalize(option.label || option.value).replace(/\s+/g, "");
}

export default function CareerRoleInput({
  label,
  value,
  onChange,
  options,
  placeholder = "Type a career aim",
  required = false,
  disabled = false,
  className = "",
  inputClassName = "",
}: CareerRoleInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<CareerRoleSuggestion[]>([]);
  const [isResolvingSuggestions, setIsResolvingSuggestions] = useState(false);
  const [menuPosition, setMenuPosition] = useState<MenuPosition>({
    top: 0,
    left: 0,
    width: 0,
    maxHeight: 320,
    placement: "bottom",
  });
  const fieldRef = useRef<HTMLDivElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const cleanValue = value.trim();
  const exactMatch = useMemo(
    () =>
      options.some((option) => {
        const candidates = [option.label, option.value, ...(option.aliases ?? [])];
        return candidates.some((candidate) => normalize(candidate) === normalize(cleanValue));
      }),
    [cleanValue, options],
  );
  const localSuggestions = useMemo(
    () => options.filter((option) => optionMatches(option, value)).slice(0, 8),
    [options, value],
  );
  const suggestions = useMemo(() => {
    const seen = new Set<string>();
    const merged: CareerRoleSuggestion[] = [];

    for (const option of [...aiSuggestions, ...localSuggestions]) {
      const key = optionKey(option);
      if (!key || seen.has(key)) {
        continue;
      }
      seen.add(key);
      merged.push(option);
    }

    return merged.slice(0, 8);
  }, [aiSuggestions, localSuggestions]);
  const shouldAskAi = isFocused && !disabled && cleanValue.length >= 2 && !exactMatch && localSuggestions.length === 0;
  const showSuggestions = isFocused && !disabled && (suggestions.length > 0 || isResolvingSuggestions || (cleanValue && !exactMatch));

  const updateMenuPosition = useCallback(() => {
    const field = fieldRef.current;
    if (!field || typeof window === "undefined") {
      return;
    }

    const rect = field.getBoundingClientRect();
    const gap = 8;
    const viewportPadding = 10;
    const preferredHeight = 320;
    const minHeight = 120;
    const availableBelow = window.innerHeight - rect.bottom - gap - viewportPadding;
    const availableAbove = rect.top - gap - viewportPadding;
    const placement = availableBelow < preferredHeight && availableAbove >= minHeight ? "top" : "bottom";
    const availableHeight = Math.max(0, placement === "top" ? availableAbove : availableBelow);
    const maxHeight = Math.min(preferredHeight, Math.max(minHeight, availableHeight));
    const width = Math.min(rect.width, Math.max(180, window.innerWidth - viewportPadding * 2));
    const left = Math.min(
      Math.max(viewportPadding, rect.left),
      Math.max(viewportPadding, window.innerWidth - width - viewportPadding),
    );
    const top = placement === "top"
      ? Math.max(viewportPadding, rect.top - gap - maxHeight)
      : Math.min(rect.bottom + gap, Math.max(viewportPadding, window.innerHeight - viewportPadding - maxHeight));

    setMenuPosition({ top, left, width, maxHeight, placement });
  }, []);

  useEffect(() => {
    if (!shouldAskAi) {
      setAiSuggestions([]);
      setIsResolvingSuggestions(false);
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setIsResolvingSuggestions(true);
      apiFetch<{ suggestions: CareerRoleSuggestion[] }>("/career-roles/suggestions", {
        method: "POST",
        body: JSON.stringify({ desired_role: cleanValue, limit: 6 }),
        signal: controller.signal,
      })
        .then((payload) => {
          setAiSuggestions(Array.isArray(payload.suggestions) ? payload.suggestions : []);
        })
        .catch((error) => {
          if (error && typeof error === "object" && "name" in error && String(error.name) === "AbortError") {
            return;
          }
          setAiSuggestions([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsResolvingSuggestions(false);
          }
        });
    }, 700);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [cleanValue, shouldAskAi]);

  useEffect(() => {
    if (!showSuggestions) {
      return;
    }

    updateMenuPosition();
    const handleViewportChange = () => updateMenuPosition();
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);

    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [showSuggestions, updateMenuPosition, suggestions.length, isResolvingSuggestions]);

  useEffect(() => {
    if (!showSuggestions) {
      return;
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsFocused(false);
      }
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [showSuggestions]);

  const menu = (
    <AnimatePresence>
      {showSuggestions && typeof document !== "undefined" ? (
        <Motion.div
          ref={menuRef}
          initial={{ opacity: 0, y: menuPosition.placement === "top" ? 10 : -10, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: menuPosition.placement === "top" ? 8 : -8, scale: 0.98 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          style={{
            left: menuPosition.left,
            top: menuPosition.top,
            width: menuPosition.width,
            maxHeight: menuPosition.maxHeight,
            transformOrigin: menuPosition.placement === "top" ? "bottom center" : "top center",
          }}
          className="fixed z-[9999] overflow-y-auto rounded-2xl border border-outline-variant/30 bg-surface-container-lowest p-1.5 shadow-2xl shadow-black/20 ring-1 ring-black/5 dark:border-outline-variant/20 dark:bg-surface-container dark:ring-white/10"
        >
          {isResolvingSuggestions ? (
            <div className="rounded-xl bg-surface-container px-3 py-2.5 text-xs font-black uppercase tracking-widest text-on-surface-variant dark:bg-surface-container-high">
              Asking AI for this career...
            </div>
          ) : null}

          {cleanValue && !exactMatch ? (
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(cleanValue);
                setIsFocused(false);
              }}
              className="w-full rounded-xl border border-dashed border-primary/35 bg-surface-container px-3 py-2.5 text-left text-primary transition hover:bg-surface-container-high dark:bg-surface-container-high dark:hover:bg-surface-container-highest"
            >
              <span className="block text-sm font-black">Use typed aim: {cleanValue}</span>
              <span className="mt-0.5 block text-xs font-semibold text-on-surface-variant">
                No exact local match. CELTM can still normalize this custom aim.
              </span>
            </button>
          ) : null}

          {suggestions.map((option) => (
            <button
              key={`${option.source ?? "local"}-${option.value}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(option.value);
                setIsFocused(false);
              }}
              className="mt-1 w-full rounded-xl px-3 py-2.5 text-left text-on-surface transition hover:bg-surface-container-high hover:text-primary dark:hover:bg-surface-container-highest"
            >
              <span className="flex items-start justify-between gap-3">
                <span className="block text-sm font-black">{option.label}</span>
                {"source" in option && option.source ? (
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-black uppercase tracking-widest text-primary">
                    {option.source === "ai" ? "AI" : option.source}
                  </span>
                ) : null}
              </span>
              {option.interpretation || option.description ? (
                <span className="mt-0.5 block text-xs font-semibold text-on-surface-variant">
                  {option.interpretation || option.description}
                </span>
              ) : null}
              {option.aliases?.length ? (
                <span className="mt-1 block text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                  Also: {option.aliases.slice(0, 3).join(", ")}
                </span>
              ) : null}
            </button>
          ))}
        </Motion.div>
      ) : null}
    </AnimatePresence>
  );

  return (
    <div className={`relative ${className}`}>
      {label ? (
        <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
          {label}
        </label>
      ) : null}
      <div ref={fieldRef} className="relative">
        <input
          required={required}
          disabled={disabled}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => {
            setIsFocused(true);
            window.setTimeout(updateMenuPosition, 0);
          }}
          onBlur={() => window.setTimeout(() => setIsFocused(false), 140)}
          placeholder={placeholder}
          className={`min-h-12 w-full rounded-2xl border border-outline-variant/20 bg-surface px-4 py-3 pr-11 text-sm font-bold text-on-surface shadow-sm outline-none transition-all duration-200 placeholder:text-on-surface-variant hover:border-primary/35 hover:shadow-md focus:border-primary/55 focus:ring-4 focus:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-55 ${inputClassName}`}
        />
        <div className="pointer-events-none absolute right-3 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-surface-container-low text-on-surface-variant">
          <AppIcon name="search" className="h-4 w-4" />
        </div>
      </div>

      {typeof document !== "undefined" ? createPortal(menu, document.body) : null}
    </div>
  );
}
