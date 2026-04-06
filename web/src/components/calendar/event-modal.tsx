"use client";

import { useState, useEffect } from "react";
import type { CalendarEvent, EventCategory } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface EventModalProps {
  event: CalendarEvent | null; // null = create mode
  defaultStart?: Date;
  onSave: (data: {
    title: string;
    description: string;
    start_time: string;
    end_time: string;
    location: string;
    category: string;
    is_all_day: boolean;
  }) => void;
  onDelete?: () => void;
  onClose: () => void;
}

const CATEGORIES: { value: EventCategory; label: string }[] = [
  { value: "work", label: "Work" },
  { value: "personal", label: "Personal" },
  { value: "focus", label: "Focus" },
  { value: "health", label: "Health" },
];

function toLocalDatetime(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function EventModal({
  event,
  defaultStart,
  onSave,
  onDelete,
  onClose,
}: EventModalProps) {
  const isEdit = !!event;

  const getInitialStart = () => {
    if (event) return toLocalDatetime(new Date(event.start_time));
    if (defaultStart) return toLocalDatetime(defaultStart);
    return toLocalDatetime(new Date());
  };

  const getInitialEnd = () => {
    if (event) return toLocalDatetime(new Date(event.end_time));
    const d = defaultStart ? new Date(defaultStart) : new Date();
    d.setHours(d.getHours() + 1);
    return toLocalDatetime(d);
  };

  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [startTime, setStartTime] = useState(getInitialStart);
  const [endTime, setEndTime] = useState(getInitialEnd);
  const [location, setLocation] = useState(event?.location ?? "");
  const [category, setCategory] = useState(event?.category ?? "work");
  const [isAllDay, setIsAllDay] = useState(event?.is_all_day ?? false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSave({
      title: title.trim(),
      description: description.trim(),
      start_time: new Date(startTime).toISOString(),
      end_time: new Date(endTime).toISOString(),
      location: location.trim(),
      category,
      is_all_day: isAllDay,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-background border border-border rounded-xl shadow-2xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">
            {isEdit ? "Edit event" : "New event"}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-surface transition-colors"
          >
            <svg className="w-5 h-5 text-muted" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Title */}
          <Input
            type="text"
            placeholder="Event title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-base"
            autoFocus
          />

          {/* All day toggle */}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isAllDay}
              onChange={(e) => setIsAllDay(e.target.checked)}
              className="rounded"
            />
            All day
          </label>

          {/* Date/time */}
          {!isAllDay && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-muted mb-1">Start</label>
                <input
                  type="datetime-local"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">End</label>
                <input
                  type="datetime-local"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
          )}

          {/* Location */}
          <Input
            type="text"
            placeholder="Add location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />

          {/* Category */}
          <div>
            <label className="block text-xs text-muted mb-1.5">Category</label>
            <div className="flex gap-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => setCategory(cat.value)}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    category === cat.value
                      ? "bg-primary text-white border-primary"
                      : "border-border text-muted hover:border-foreground"
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <textarea
            placeholder="Add description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
          />

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <div>
              {isEdit && onDelete && (
                confirmDelete ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-danger">Delete this event?</span>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={onDelete}
                    >
                      Yes, delete
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setConfirmDelete(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="text-sm text-danger hover:underline"
                  >
                    Delete
                  </button>
                )
              )}
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={!title.trim()}>
                {isEdit ? "Save changes" : "Create event"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
