"use client";

import { useState } from "react";
import MiniCalendar from "./sidebar/mini-calendar";
import { useCalendar } from "@/lib/calendar-context";
import { Separator } from "@/components/ui/separator";
import type { EventCategory } from "@/lib/types";
import {
  CATEGORY_BG_CLASSES,
} from "@/lib/types";

const CATEGORIES: { key: EventCategory; label: string }[] = [
  { key: "work", label: "Work" },
  { key: "personal", label: "Personal" },
  { key: "focus", label: "Focus" },
  { key: "health", label: "Health" },
];

export default function Sidebar() {
  const {
    currentDate,
    setCurrentDate,
    setViewType,
    selectedCategories,
    toggleCategory,
  } = useCalendar();
  const [displayMonth, setDisplayMonth] = useState(new Date(currentDate));

  const handleSelectDate = (date: Date) => {
    setCurrentDate(date);
    setViewType("day");
  };

  return (
    <aside className="w-56 border-r border-border bg-background flex-shrink-0 overflow-y-auto p-4 hidden md:block">
      <MiniCalendar
        currentDate={currentDate}
        onSelectDate={handleSelectDate}
        displayMonth={displayMonth}
        onChangeMonth={setDisplayMonth}
      />

      <Separator className="my-4" />

      {/* Category filters */}
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
          Calendars
        </h3>
        <div className="space-y-1">
          {CATEGORIES.map(({ key, label }) => (
            <label
              key={key}
              className="flex items-center gap-2.5 py-1 px-1 rounded cursor-pointer hover:bg-surface transition-colors"
            >
              <div className="relative flex items-center">
                <input
                  type="checkbox"
                  checked={selectedCategories.has(key)}
                  onChange={() => toggleCategory(key)}
                  className="sr-only"
                />
                <div
                  className={`w-3.5 h-3.5 rounded-sm border transition-colors ${
                    selectedCategories.has(key)
                      ? `${CATEGORY_BG_CLASSES[key]} border-transparent`
                      : "border-muted-foreground/40 bg-transparent"
                  }`}
                >
                  {selectedCategories.has(key) && (
                    <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 16 16" fill="none">
                      <path d="M4 8l3 3 5-5" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
              </div>
              <span className="text-sm text-foreground">{label}</span>
            </label>
          ))}
        </div>
      </div>
    </aside>
  );
}
