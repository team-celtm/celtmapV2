"use client";

import { useEffect, useMemo, useState } from "react";

import type { ScheduleEvent, ScheduleEventPayload } from "@/lib/celtm";
import { formatDateTime, formatRelativeTime, toTitleCase } from "@/lib/celtm";
import ThemedSelect from "@/components/ThemedSelect";

interface SchedulePlannerProps {
  events: ScheduleEvent[];
  onCreate: (payload: ScheduleEventPayload) => Promise<void>;
  onUpdate: (eventId: string, payload: ScheduleEventPayload) => Promise<void>;
  onDelete: (eventId: string) => Promise<void>;
}

type PlannerMode = "create" | "edit";

const eventTypes = ["assessment", "learning", "interview", "deadline", "practice"];

function toInputValue(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function fromInputValue(value: string) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function sameDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
  );
}

function buildDefaultStart(selectedDate: Date) {
  const start = new Date(selectedDate);
  start.setHours(10, 0, 0, 0);
  return toInputValue(start.toISOString());
}

function buildDefaultEnd(startValue: string) {
  const start = new Date(startValue);
  if (Number.isNaN(start.getTime())) {
    return "";
  }
  start.setHours(start.getHours() + 1);
  return toInputValue(start.toISOString());
}

export function SchedulePlanner({ events, onCreate, onUpdate, onDelete }: SchedulePlannerProps) {
  const today = useMemo(() => new Date(), []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [visibleMonth, setVisibleMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [mode, setMode] = useState<PlannerMode>("create");
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    starts_at: buildDefaultStart(today),
    ends_at: buildDefaultEnd(buildDefaultStart(today)),
    event_type: "assessment",
    notes: "",
  });

  const sortedEvents = useMemo(
    () =>
      [...events].sort(
        (left, right) => new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime(),
      ),
    [events],
  );

  const monthDays = useMemo(() => {
    const firstDay = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1);
    const startOffset = (firstDay.getDay() + 6) % 7;
    const start = new Date(firstDay);
    start.setDate(firstDay.getDate() - startOffset);

    return Array.from({ length: 42 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return date;
    });
  }, [visibleMonth]);

  const selectedDayEvents = useMemo(
    () =>
      sortedEvents.filter((event) => sameDay(new Date(event.starts_at), selectedDate)),
    [selectedDate, sortedEvents],
  );

  useEffect(() => {
    if (mode === "edit" && editingEventId) {
      const event = sortedEvents.find((item) => item.id === editingEventId);
      if (!event) {
        setMode("create");
        setEditingEventId(null);
      }
      return;
    }

    const nextStart = buildDefaultStart(selectedDate);
    setForm((current) => ({
      ...current,
      starts_at: current.starts_at || nextStart,
      ends_at: current.ends_at || buildDefaultEnd(nextStart),
    }));
  }, [editingEventId, mode, selectedDate, sortedEvents]);

  const resetForm = (date = selectedDate) => {
    const nextStart = buildDefaultStart(date);
    setForm({
      title: "",
      starts_at: nextStart,
      ends_at: buildDefaultEnd(nextStart),
      event_type: "assessment",
      notes: "",
    });
    setMode("create");
    setEditingEventId(null);
  };

  const beginEdit = (event: ScheduleEvent) => {
    setMode("edit");
    setEditingEventId(event.id);
    setForm({
      title: event.title,
      starts_at: toInputValue(event.starts_at),
      ends_at: toInputValue(event.ends_at),
      event_type: event.event_type,
      notes: event.metadata?.notes || "",
    });
  };

  const saveEvent = async () => {
    if (!form.title.trim() || !form.starts_at) {
      setError("Title and start time are required.");
      return;
    }

    const payload: ScheduleEventPayload = {
      title: form.title.trim(),
      starts_at: fromInputValue(form.starts_at),
      ends_at: form.ends_at ? fromInputValue(form.ends_at) : null,
      event_type: form.event_type,
      metadata: form.notes.trim() ? { notes: form.notes.trim() } : {},
    };

    if (!payload.starts_at) {
      setError("Start time is invalid.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      if (mode === "edit" && editingEventId) {
        await onUpdate(editingEventId, payload);
      } else {
        await onCreate(payload);
      }
      resetForm();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save the schedule event.");
    } finally {
      setIsSaving(false);
    }
  };

  const removeEvent = async (eventId: string) => {
    try {
      setIsSaving(true);
      setError(null);
      await onDelete(eventId);
      if (editingEventId === eventId) {
        resetForm();
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to delete the schedule event.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {error ? (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 md:grid-cols-[1.18fr_0.82fr]">
        <div className="lift-card rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 md:p-6">
          <div className="mb-5 flex items-center justify-between">
            <button
              type="button"
              onClick={() =>
                setVisibleMonth(
                  new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1),
                )
              }
              className="rounded-full bg-surface px-3 py-2 text-xs font-black uppercase tracking-[0.18em] text-on-surface"
            >
              Prev
            </button>
            <div className="text-center">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                Calendar view
              </p>
              <p className="mt-1 text-lg font-bold text-on-surface">
                {visibleMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                setVisibleMonth(
                  new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1),
                )
              }
              className="rounded-full bg-surface px-3 py-2 text-xs font-black uppercase tracking-[0.18em] text-on-surface"
            >
              Next
            </button>
          </div>

          <div className="grid grid-cols-7 gap-2 text-center text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label) => (
              <div key={label} className="py-2">
                {label}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-2">
            {monthDays.map((day) => {
              const isCurrentMonth = day.getMonth() === visibleMonth.getMonth();
              const isSelected = sameDay(day, selectedDate);
              const dayEvents = sortedEvents.filter((event) => sameDay(new Date(event.starts_at), day));

              return (
                <button
                  key={day.toISOString()}
                  type="button"
                  onClick={() => {
                    setSelectedDate(day);
                    if (mode === "create") {
                      resetForm(day);
                    }
                  }}
                  className={`lift-tile min-h-[56px] rounded-xl border p-1.5 text-left transition flex flex-col ${
                    isSelected
                      ? "border-primary/40 bg-primary/10"
                      : "border-outline-variant/12 dark:border-transparent bg-surface hover:border-primary/20"
                  } ${isCurrentMonth ? "text-on-surface" : "text-on-surface-variant/40"}`}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="text-[10px] font-bold">{day.getDate()}</span>
                    {dayEvents.length ? (
                      <span className="rounded-full bg-primary/15 px-1 py-0.5 text-[7px] font-black uppercase tracking-[0.16em] text-primary">
                        {dayEvents.length}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-auto pt-0.5 w-full space-y-0.5">
                    {dayEvents.slice(0, 1).map((event) => (
                      <div
                        key={event.id}
                        className="truncate rounded-full bg-surface-container-high px-1 py-0.5 text-[7px] font-bold text-on-surface"
                      >
                        {event.title}
                      </div>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <div className="lift-card rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 md:p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  {mode === "edit" ? "Edit event" : "Create event"}
                </p>
                <h3 className="mt-1 text-xl font-bold text-on-surface">
                  {selectedDate.toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </h3>
              </div>
              {mode === "edit" ? (
                <button
                  type="button"
                  onClick={() => resetForm()}
                  className="rounded-full bg-surface px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-on-surface"
                >
                  New event
                </button>
              ) : null}
            </div>

            <div className="space-y-4">
              <label className="block">
                <span className="mb-2 block text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                  Title
                </span>
                <input
                  value={form.title}
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  className="h-12 w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface px-4 text-sm text-on-surface outline-none"
                  placeholder="Assessment sprint"
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                    Starts
                  </span>
                  <input
                    type="datetime-local"
                    value={form.starts_at}
                    onChange={(event) => setForm((current) => ({ ...current, starts_at: event.target.value }))}
                    className="h-12 w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface px-4 text-sm text-on-surface outline-none"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                    Ends
                  </span>
                  <input
                    type="datetime-local"
                    value={form.ends_at}
                    onChange={(event) => setForm((current) => ({ ...current, ends_at: event.target.value }))}
                    className="h-12 w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface px-4 text-sm text-on-surface outline-none"
                  />
                </label>
              </div>

              <ThemedSelect
                label="Event type"
                value={form.event_type}
                onChange={(value) => setForm((current) => ({ ...current, event_type: value }))}
                options={eventTypes.map((eventType) => ({ value: eventType, label: toTitleCase(eventType) }))}
                buttonClassName="min-h-12 border-outline-variant/12 dark:border-transparent"
              />

              <label className="block">
                <span className="mb-2 block text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                  Notes
                </span>
                <textarea
                  rows={4}
                  value={form.notes}
                  onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                  className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface px-4 py-3 text-sm text-on-surface outline-none"
                  placeholder="Optional details for this schedule item"
                />
              </label>

              <button
                type="button"
                onClick={() => void saveEvent()}
                disabled={isSaving}
                className="inline-flex rounded-full bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white disabled:opacity-60"
              >
                {isSaving ? "Saving..." : mode === "edit" ? "Update event" : "Create event"}
              </button>
            </div>
          </div>

          <div className="lift-card rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 md:p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  Day queue
                </p>
                <h3 className="mt-1 text-xl font-bold text-on-surface">
                  {selectedDayEvents.length} event{selectedDayEvents.length === 1 ? "" : "s"}
                </h3>
              </div>
            </div>

            {selectedDayEvents.length ? (
              <div className="max-h-[24rem] space-y-3 overflow-y-auto pr-2 custom-scrollbar">
                {selectedDayEvents.map((event) => (
                  <div
                    key={event.id}
                    className="lift-tile rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface px-4 py-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h4 className="text-base font-bold text-on-surface">{event.title}</h4>
                        <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                          {formatDateTime(event.starts_at)}
                        </p>
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                          {toTitleCase(event.event_type)} · {formatRelativeTime(event.starts_at)}
                        </p>
                        {event.metadata?.notes ? (
                          <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                            {event.metadata.notes}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => beginEdit(event)}
                          className="rounded-full bg-surface-container-high px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-on-surface"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeEvent(event.id)}
                          disabled={isSaving}
                          className="rounded-full bg-red-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-red-300 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm leading-6 text-on-surface-variant">
                No events are scheduled for this day yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
