"use client";

import { useMemo, useState, useEffect } from "react";
import type { CalendarEvent } from "@/lib/types";
import {
  getWeekDays,
  formatDayShort,
  getHourLabels,
  isToday,
  isSameDay,
  eventPosition,
} from "@/lib/dates";
import { useCalendar } from "@/lib/calendar-context";
import EventCard from "./event-card";

const HOUR_HEIGHT = 60; // px per hour

interface WeekViewProps {
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  onSlotClick: (date: Date, hour: number) => void;
}

export default function WeekView({
  events,
  onEventClick,
  onSlotClick,
}: WeekViewProps) {
  const { currentDate } = useCalendar();
  const days = useMemo(() => getWeekDays(currentDate), [currentDate]);
  const hours = getHourLabels();

  // Group events by day
  const eventsByDay = useMemo(() => {
    const map = new Map<number, CalendarEvent[]>();
    for (let i = 0; i < 7; i++) map.set(i, []);

    for (const event of events) {
      const start = new Date(event.start_time);
      for (let i = 0; i < days.length; i++) {
        if (isSameDay(start, days[i])) {
          map.get(i)!.push(event);
          break;
        }
      }
    }
    return map;
  }, [events, days]);

  return (
    <div className="flex flex-col h-full">
      {/* Day headers */}
      <div className="flex border-b border-border sticky top-0 z-10 bg-background">
        {/* Time gutter */}
        <div className="w-16 shrink-0" />
        {/* Day columns */}
        {days.map((day, i) => (
          <div
            key={i}
            className={`flex-1 text-center py-2 border-l border-border ${
              isToday(day) ? "bg-primary/5" : ""
            }`}
          >
            <span
              className={`text-xs font-medium ${
                isToday(day) ? "text-primary" : "text-muted"
              }`}
            >
              {formatDayShort(day)}
            </span>
            {isToday(day) && (
              <div className="mx-auto mt-1 w-6 h-6 rounded-full bg-primary text-white text-xs flex items-center justify-center font-semibold">
                {day.getDate()}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Time grid */}
      <div className="flex flex-1 overflow-y-auto">
        {/* Time labels */}
        <div className="w-16 shrink-0">
          {hours.map((label, i) => (
            <div
              key={i}
              className="border-b border-border relative"
              style={{ height: HOUR_HEIGHT }}
            >
              <span className="absolute -top-2 right-2 text-[10px] text-muted">
                {i > 0 ? label : ""}
              </span>
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day, dayIndex) => (
          <div
            key={dayIndex}
            className={`flex-1 border-l border-border relative ${
              isToday(day) ? "bg-primary/[0.02]" : ""
            }`}
          >
            {/* Hour slots */}
            {hours.map((_, hourIndex) => (
              <div
                key={hourIndex}
                className="border-b border-border hover:bg-surface/50 cursor-pointer transition-colors"
                style={{ height: HOUR_HEIGHT }}
                onClick={() => onSlotClick(day, hourIndex)}
              />
            ))}

            {/* Events */}
            {eventsByDay.get(dayIndex)?.map((event) => {
              const start = new Date(event.start_time);
              const end = new Date(event.end_time);
              const pos = eventPosition(start, end, HOUR_HEIGHT);
              return (
                <EventCard
                  key={event.id}
                  event={event}
                  style={{ top: pos.top, height: Math.max(pos.height, 24) }}
                  onClick={onEventClick}
                />
              );
            })}

            {/* Current time indicator */}
            {isToday(day) && <CurrentTimeIndicator />}
          </div>
        ))}
      </div>
    </div>
  );
}

function CurrentTimeIndicator() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const top = (now.getHours() + now.getMinutes() / 60) * HOUR_HEIGHT;

  return (
    <div
      className="absolute left-0 right-0 z-20 pointer-events-none"
      style={{ top }}
    >
      <div className="flex items-center">
        <div className="w-2 h-2 rounded-full bg-red-500 -ml-1" />
        <div className="flex-1 h-[2px] bg-red-500" />
      </div>
    </div>
  );
}
