"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion as Motion } from "framer-motion";

import AppIcon from "@/components/AppIcon";

export interface ThemedSelectOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface ThemedSelectProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: ThemedSelectOption[];
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  buttonClassName?: string;
}

interface MenuPosition {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
  placement: "top" | "bottom";
}

export default function ThemedSelect({
  label,
  value,
  onChange,
  options,
  placeholder = "Select",
  disabled = false,
  required = false,
  className = "",
  buttonClassName = "",
}: ThemedSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<MenuPosition>({
    top: 0,
    left: 0,
    width: 0,
    maxHeight: 288,
    placement: "bottom",
  });
  const containerRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const buttonId = useId();
  const listboxId = useId();

  const selectedOption = useMemo(() => options.find((option) => option.value === value) ?? null, [options, value]);

  const updateMenuPosition = useCallback(() => {
    const button = buttonRef.current;
    if (!button || typeof window === "undefined") {
      return;
    }

    const rect = button.getBoundingClientRect();
    const gap = 8;
    const viewportPadding = 8;
    const minMenuHeight = 96;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const availableBelow = viewportHeight - rect.bottom - gap - viewportPadding;
    const availableAbove = rect.top - gap - viewportPadding;
    const placement = availableBelow >= 180 || availableBelow >= availableAbove ? "bottom" : "top";
    const availableHeight = Math.max(0, placement === "top" ? availableAbove : availableBelow);
    const maxHeight = Math.min(288, Math.max(minMenuHeight, availableHeight));
    const width = Math.min(rect.width, Math.max(160, viewportWidth - viewportPadding * 2));
    const left = Math.min(
      Math.max(viewportPadding, rect.left),
      Math.max(viewportPadding, viewportWidth - width - viewportPadding),
    );
    const top = placement === "top"
      ? Math.max(viewportPadding, rect.top - gap - maxHeight)
      : Math.min(rect.bottom + gap, Math.max(viewportPadding, viewportHeight - viewportPadding - maxHeight));

    setMenuPosition({ top, left, width, maxHeight, placement });
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const closeOnOutsideClick = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!containerRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setIsOpen(false);
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
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
  }, [isOpen, updateMenuPosition]);

  const selectOption = (option: ThemedSelectOption) => {
    if (option.disabled) {
      return;
    }
    onChange(option.value);
    setIsOpen(false);
    window.setTimeout(() => buttonRef.current?.focus(), 0);
  };

  const openMenu = () => {
    updateMenuPosition();
    setIsOpen(true);
  };

  const toggleMenu = () => {
    if (!isOpen) {
      updateMenuPosition();
    }
    setIsOpen((current) => !current);
  };

  const menu = (
    <AnimatePresence>
      {isOpen && typeof document !== "undefined" ? (
        <Motion.div
          ref={menuRef}
          id={listboxId}
          role="listbox"
          aria-labelledby={buttonId}
          initial={{ opacity: 0, y: menuPosition.placement === "top" ? 8 : -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: menuPosition.placement === "top" ? 6 : -6, scale: 0.98 }}
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
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={selected}
                disabled={option.disabled}
                onClick={() => selectOption(option)}
                className={`relative w-full rounded-xl px-3 py-2.5 text-left transition-all duration-200 ${
                  selected
                    ? "bg-primary text-white shadow-sm"
                    : "text-on-surface hover:bg-surface-container-high hover:text-primary dark:hover:bg-surface-container-highest"
                } disabled:cursor-not-allowed disabled:opacity-45`}
              >
                <span className="block text-sm font-black">{option.label}</span>
                {option.description ? (
                  <span className={`mt-0.5 block text-xs font-semibold ${selected ? "text-white/75" : "text-on-surface-variant"}`}>
                    {option.description}
                  </span>
                ) : null}
              </button>
            );
          })}
        </Motion.div>
      ) : null}
    </AnimatePresence>
  );

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label ? (
        <label htmlFor={buttonId} className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
          {label}
        </label>
      ) : null}

      <select
        aria-hidden="true"
        className="pointer-events-none absolute h-px w-px opacity-0"
        required={required}
        tabIndex={-1}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>

      <button
        ref={buttonRef}
        id={buttonId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        disabled={disabled}
        onClick={toggleMenu}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openMenu();
          }
        }}
        className={`group flex min-h-12 w-full items-center justify-between gap-3 rounded-2xl border border-outline-variant/20 bg-surface px-4 py-3 text-left text-sm font-bold text-on-surface shadow-sm outline-none transition-all duration-200 hover:border-primary/35 hover:shadow-md focus:border-primary/55 focus:ring-4 focus:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-55 ${buttonClassName}`}
      >
        <span className={selectedOption ? "text-on-surface" : "text-on-surface-variant"}>
          {selectedOption?.label ?? placeholder}
        </span>
        <Motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-container-low text-on-surface-variant transition group-hover:bg-primary/10 group-hover:text-primary"
        >
          <AppIcon name="expand_more" className="h-5 w-5" />
        </Motion.span>
      </button>

      {typeof document !== "undefined" ? createPortal(menu, document.body) : null}
    </div>
  );
}
