"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { addDays, addMonths } from "./dates";
import type { EventCategory } from "./types";

export type ViewType = "agenda" | "day" | "week" | "month";

interface CalendarContextValue {
  currentDate: Date;
  setCurrentDate: (date: Date) => void;
  viewType: ViewType;
  setViewType: (view: ViewType) => void;
  goToPrev: () => void;
  goToNext: () => void;
  goToToday: () => void;
  selectedCategories: Set<EventCategory>;
  toggleCategory: (cat: EventCategory) => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

const CalendarContext = createContext<CalendarContextValue | null>(null);

const ALL_CATEGORIES: Set<EventCategory> = new Set([
  "work",
  "personal",
  "focus",
  "health",
]);

export function CalendarProvider({ children }: { children: ReactNode }) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewType, setViewType] = useState<ViewType>("agenda");
  const [selectedCategories, setSelectedCategories] =
    useState<Set<EventCategory>>(new Set(ALL_CATEGORIES));
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const goToPrev = useCallback(() => {
    setCurrentDate((d) => {
      switch (viewType) {
        case "day":
        case "agenda":
          return addDays(d, -1);
        case "week":
          return addDays(d, -7);
        case "month":
          return addMonths(d, -1);
      }
    });
  }, [viewType]);

  const goToNext = useCallback(() => {
    setCurrentDate((d) => {
      switch (viewType) {
        case "day":
        case "agenda":
          return addDays(d, 1);
        case "week":
          return addDays(d, 7);
        case "month":
          return addMonths(d, 1);
      }
    });
  }, [viewType]);

  const goToToday = useCallback(() => {
    setCurrentDate(new Date());
  }, []);

  const toggleCategory = useCallback((cat: EventCategory) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  }, []);

  return (
    <CalendarContext.Provider
      value={{
        currentDate,
        setCurrentDate,
        viewType,
        setViewType,
        goToPrev,
        goToNext,
        goToToday,
        selectedCategories,
        toggleCategory,
        sidebarOpen,
        setSidebarOpen,
      }}
    >
      {children}
    </CalendarContext.Provider>
  );
}

export function useCalendar() {
  const ctx = useContext(CalendarContext);
  if (!ctx) throw new Error("useCalendar must be used within CalendarProvider");
  return ctx;
}
