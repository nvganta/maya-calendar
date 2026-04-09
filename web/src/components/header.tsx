"use client";

import { useAuth } from "@/lib/auth";
import { useCalendar, type ViewType } from "@/lib/calendar-context";
import {
  formatWeekRange,
  formatMonthYear,
  formatDayLong,
  formatDateLong,
} from "@/lib/dates";
import { Button } from "@/components/ui/button";

const VIEW_OPTIONS: { value: ViewType; label: string }[] = [
  { value: "agenda", label: "Agenda" },
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
];

interface HeaderProps {
  onNewEvent: () => void;
  onOpenSettings: () => void;
}

export default function Header({ onNewEvent, onOpenSettings }: HeaderProps) {
  const { user, logout } = useAuth();
  const {
    currentDate,
    viewType,
    setViewType,
    goToPrev,
    goToNext,
    goToToday,
    sidebarOpen,
    setSidebarOpen,
  } = useCalendar();

  const dateLabel = (() => {
    switch (viewType) {
      case "day":
        return formatDayLong(currentDate);
      case "week":
        return formatWeekRange(currentDate);
      case "month":
        return formatMonthYear(currentDate);
      case "agenda":
        return formatDateLong(currentDate);
    }
  })();

  return (
    <header className="sticky top-0 z-30 bg-background border-b border-border">
      <div className="flex items-center justify-between px-4 h-14">
        {/* Left: sidebar toggle + logo + nav */}
        <div className="flex items-center gap-3">
          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-md hover:bg-surface transition-colors hidden md:flex"
            title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          >
            <svg className="w-5 h-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>

          {/* Logo */}
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 text-primary"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
              />
            </svg>
            <span className="font-semibold text-sm">Calendar</span>
          </div>

          {/* Navigation */}
          <div className="flex items-center gap-1 ml-1">
            <button
              onClick={goToPrev}
              className="p-1.5 rounded-md hover:bg-surface transition-colors"
              title="Previous"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
              </svg>
            </button>
            <button
              onClick={goToNext}
              className="p-1.5 rounded-md hover:bg-surface transition-colors"
              title="Next"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
              </svg>
            </button>
            <Button
              variant="outline"
              size="sm"
              onClick={goToToday}
              className="ml-1 h-7 text-xs"
            >
              Today
            </Button>
            <span className="text-sm font-medium ml-3">{dateLabel}</span>
          </div>
        </div>

        {/* Center: view switcher */}
        <div className="hidden sm:flex items-center bg-surface rounded-lg p-0.5">
          {VIEW_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setViewType(value)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                viewType === value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={onNewEvent} className="h-8 gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span className="hidden sm:inline">New event</span>
          </Button>
          <button
            onClick={onOpenSettings}
            className="p-1.5 rounded-md hover:bg-surface transition-colors"
            title="Settings"
          >
            <svg className="w-5 h-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
            </svg>
          </button>
          <div className="flex items-center gap-2 ml-2 pl-2 border-l border-border">
            <span className="text-sm text-muted-foreground hidden sm:inline">
              {user?.name || user?.email}
            </span>
            <button
              onClick={logout}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
