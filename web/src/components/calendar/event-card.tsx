"use client";

import type { CalendarEvent, EventCategory } from "@/lib/types";
import { CATEGORY_LIGHT_BG } from "@/lib/types";
import { formatTime } from "@/lib/dates";

interface EventCardProps {
  event: CalendarEvent;
  style: React.CSSProperties;
  onClick: (event: CalendarEvent) => void;
}

const DEFAULT_STYLE = "bg-blue-50 border-blue-200";

export default function EventCard({ event, style, onClick }: EventCardProps) {
  const category = event.category as EventCategory | null;
  const colorClass = category ? CATEGORY_LIGHT_BG[category] ?? DEFAULT_STYLE : DEFAULT_STYLE;
  const start = new Date(event.start_time);
  const end = new Date(event.end_time);

  return (
    <button
      onClick={() => onClick(event)}
      className={`absolute left-0.5 right-0.5 rounded-md border px-2 py-1 text-left overflow-hidden cursor-pointer hover:shadow-md transition-shadow ${colorClass}`}
      style={style}
      title={`${event.title}\n${formatTime(start)} - ${formatTime(end)}`}
    >
      <p className="text-xs font-medium truncate text-foreground">
        {event.title}
      </p>
      <p className="text-[10px] text-muted truncate">
        {formatTime(start)} - {formatTime(end)}
      </p>
      {event.location && (
        <p className="text-[10px] text-muted truncate">{event.location}</p>
      )}
    </button>
  );
}
