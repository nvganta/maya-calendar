"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import type { CalendarEvent, EventCreate, EventUpdate } from "@/lib/types";
import {
  listEvents,
  createEvent as apiCreateEvent,
  updateEvent as apiUpdateEvent,
  deleteEvent as apiDeleteEvent,
} from "@/lib/api";
import {
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  addDays,
} from "@/lib/dates";
import { useCalendar } from "@/lib/calendar-context";

// ── Mock data for preview (remove when backend is connected) ──
function getMockEvents(monday: Date): CalendarEvent[] {
  const makeDate = (dayOffset: number, hour: number, minute = 0) => {
    const d = new Date(monday);
    d.setDate(d.getDate() + dayOffset);
    d.setHours(hour, minute, 0, 0);
    return d.toISOString();
  };
  const now = new Date().toISOString();
  return [
    { id: "1", title: "Team Standup", description: "Daily sync", start_time: makeDate(0, 9, 0), end_time: makeDate(0, 9, 30), location: "Zoom", is_all_day: false, recurrence: null, tags: null, category: "work", created_at: now, updated_at: now },
    { id: "2", title: "Deep Work Block", description: "Focus time, no meetings", start_time: makeDate(0, 10, 0), end_time: makeDate(0, 12, 0), location: null, is_all_day: false, recurrence: null, tags: null, category: "focus", created_at: now, updated_at: now },
    { id: "3", title: "Lunch with Sarah", description: null, start_time: makeDate(1, 12, 30), end_time: makeDate(1, 13, 30), location: "Cafe Milano", is_all_day: false, recurrence: null, tags: null, category: "personal", created_at: now, updated_at: now },
    { id: "4", title: "Design Review", description: "Review Q2 mockups", start_time: makeDate(1, 15, 0), end_time: makeDate(1, 16, 0), location: "Meeting Room B", is_all_day: false, recurrence: null, tags: null, category: "work", created_at: now, updated_at: now },
    { id: "5", title: "Gym", description: "Leg day", start_time: makeDate(2, 7, 0), end_time: makeDate(2, 8, 0), location: "Fitness Center", is_all_day: false, recurrence: null, tags: null, category: "health", created_at: now, updated_at: now },
    { id: "6", title: "1:1 with Alex", description: "Quarterly check-in", start_time: makeDate(2, 14, 0), end_time: makeDate(2, 14, 30), location: "Google Meet", is_all_day: false, recurrence: null, tags: null, category: "work", created_at: now, updated_at: now },
    { id: "7", title: "Sprint Planning", description: "Plan next sprint", start_time: makeDate(3, 10, 0), end_time: makeDate(3, 11, 30), location: "Zoom", is_all_day: false, recurrence: null, tags: null, category: "work", created_at: now, updated_at: now },
    { id: "8", title: "Yoga", description: null, start_time: makeDate(3, 18, 0), end_time: makeDate(3, 19, 0), location: "Home", is_all_day: false, recurrence: null, tags: null, category: "health", created_at: now, updated_at: now },
    { id: "9", title: "Product Demo", description: "Demo to stakeholders", start_time: makeDate(4, 11, 0), end_time: makeDate(4, 12, 0), location: "Main Conference Room", is_all_day: false, recurrence: null, tags: null, category: "work", created_at: now, updated_at: now },
    { id: "10", title: "Happy Hour", description: "Team social", start_time: makeDate(4, 17, 0), end_time: makeDate(4, 18, 30), location: "The Pub", is_all_day: false, recurrence: null, tags: null, category: "personal", created_at: now, updated_at: now },
  ];
}

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

export function useEvents() {
  const { currentDate, viewType, selectedCategories } = useCalendar();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const dateRange = useMemo(() => {
    switch (viewType) {
      case "day": {
        const start = new Date(currentDate);
        start.setHours(0, 0, 0, 0);
        const end = new Date(currentDate);
        end.setHours(23, 59, 59, 999);
        return { start, end };
      }
      case "week":
        return { start: startOfWeek(currentDate), end: endOfWeek(currentDate) };
      case "month":
        return { start: startOfMonth(currentDate), end: endOfMonth(currentDate) };
      case "agenda":
      default: {
        const start = new Date(currentDate);
        start.setHours(0, 0, 0, 0);
        return { start, end: addDays(start, 7) };
      }
    }
  }, [currentDate, viewType]);

  const fetchEvents = useCallback(async () => {
    if (USE_MOCK) {
      const monday = startOfWeek(currentDate);
      setEvents(getMockEvents(monday));
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listEvents(
        dateRange.start.toISOString(),
        dateRange.end.toISOString()
      );
      setEvents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, [currentDate, dateRange]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Filter by selected categories
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const cat = e.category as string;
      if (!cat) return true; // show uncategorized events always
      return selectedCategories.has(cat as never);
    });
  }, [events, selectedCategories]);

  const handleCreate = useCallback(
    async (data: EventCreate) => {
      if (USE_MOCK) {
        const newEvent: CalendarEvent = {
          id: crypto.randomUUID(),
          title: data.title,
          description: data.description || null,
          start_time: data.start_time,
          end_time: data.end_time,
          location: data.location || null,
          is_all_day: data.is_all_day || false,
          recurrence: data.recurrence || null,
          tags: data.tags || null,
          category: data.category || null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        setEvents((prev) => [...prev, newEvent]);
        return newEvent;
      }
      const created = await apiCreateEvent(data);
      await fetchEvents();
      return created;
    },
    [fetchEvents]
  );

  const handleUpdate = useCallback(
    async (id: string, data: EventUpdate) => {
      if (USE_MOCK) {
        setEvents((prev) =>
          prev.map((e) =>
            e.id === id
              ? { ...e, ...data, updated_at: new Date().toISOString() }
              : e
          )
        );
        return;
      }
      await apiUpdateEvent(id, data);
      await fetchEvents();
    },
    [fetchEvents]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (USE_MOCK) {
        setEvents((prev) => prev.filter((e) => e.id !== id));
        return;
      }
      await apiDeleteEvent(id);
      await fetchEvents();
    },
    [fetchEvents]
  );

  return {
    events: filteredEvents,
    allEvents: events,
    loading,
    error,
    refetch: fetchEvents,
    createEvent: handleCreate,
    updateEvent: handleUpdate,
    deleteEvent: handleDelete,
  };
}
