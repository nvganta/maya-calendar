"use client";

import { useMemo } from "react";
import {
  getMonthGrid,
  addMonths,
  formatMonthYear,
  isSameDay,
  isSameMonth,
  isToday,
} from "@/lib/dates";

interface MiniCalendarProps {
  currentDate: Date;
  onSelectDate: (date: Date) => void;
  displayMonth: Date;
  onChangeMonth: (date: Date) => void;
}

export default function MiniCalendar({
  currentDate,
  onSelectDate,
  displayMonth,
  onChangeMonth,
}: MiniCalendarProps) {
  const grid = useMemo(() => getMonthGrid(displayMonth), [displayMonth]);

  return (
    <div className="select-none">
      {/* Month header */}
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => onChangeMonth(addMonths(displayMonth, -1))}
          className="p-1 rounded hover:bg-surface transition-colors"
        >
          <svg className="w-3.5 h-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
          </svg>
        </button>
        <span className="text-xs font-medium text-foreground">
          {formatMonthYear(displayMonth)}
        </span>
        <button
          onClick={() => onChangeMonth(addMonths(displayMonth, 1))}
          className="p-1 rounded hover:bg-surface transition-colors"
        >
          <svg className="w-3.5 h-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 mb-1">
        {["M", "T", "W", "T", "F", "S", "S"].map((day, i) => (
          <div
            key={i}
            className="text-[10px] font-medium text-muted-foreground text-center py-0.5"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Date grid */}
      <div className="grid grid-cols-7">
        {grid.flat().map((date, i) => {
          const inMonth = isSameMonth(date, displayMonth);
          const selected = isSameDay(date, currentDate);
          const today = isToday(date);

          return (
            <button
              key={i}
              onClick={() => onSelectDate(date)}
              className={`
                text-[11px] w-7 h-7 rounded-full flex items-center justify-center transition-colors
                ${!inMonth ? "text-muted-foreground/40" : "text-foreground"}
                ${selected ? "bg-primary text-primary-foreground font-semibold" : ""}
                ${today && !selected ? "font-bold text-primary" : ""}
                ${!selected ? "hover:bg-surface" : ""}
              `}
            >
              {date.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
