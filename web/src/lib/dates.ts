/** Get the Monday of the week containing the given date. */
export function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday = 1
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Get Sunday end-of-day for the week containing the given date. */
export function endOfWeek(date: Date): Date {
  const start = startOfWeek(date);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return end;
}

/** Get all 7 days of the week as Date objects (Mon-Sun). */
export function getWeekDays(date: Date): Date[] {
  const start = startOfWeek(date);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
}

/** Format a date as "Mon 7" or "Tue 8". */
export function formatDayShort(date: Date): string {
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  return `${days[date.getDay()]} ${date.getDate()}`;
}

/** Format time as "9:00 AM". */
export function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/** Format date as "April 7, 2026". */
export function formatDateLong(date: Date): string {
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/** Format date range for the week header: "Apr 6 - 12, 2026". */
export function formatWeekRange(date: Date): string {
  const start = startOfWeek(date);
  const end = endOfWeek(date);
  const sameMonth = start.getMonth() === end.getMonth();

  const startStr = start.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
  const endStr = sameMonth
    ? end.getDate().toString()
    : end.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const year = end.getFullYear();

  return `${startStr} - ${endStr}, ${year}`;
}

/** Check if two dates are the same calendar day. */
export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** Check if a date is today. */
export function isToday(date: Date): boolean {
  return isSameDay(date, new Date());
}

/** Generate hour labels for the time grid (0-23). */
export function getHourLabels(): string[] {
  return Array.from({ length: 24 }, (_, i) => {
    if (i === 0) return "12 AM";
    if (i < 12) return `${i} AM`;
    if (i === 12) return "12 PM";
    return `${i - 12} PM`;
  });
}

/** Calculate top position (%) for a time within a day grid. */
export function timeToPercent(date: Date): number {
  const hours = date.getHours() + date.getMinutes() / 60;
  return (hours / 24) * 100;
}

/** Calculate the pixel top and height for an event in the time grid. */
export function eventPosition(
  startTime: Date,
  endTime: Date,
  hourHeight: number
): { top: number; height: number } {
  const startHours = startTime.getHours() + startTime.getMinutes() / 60;
  const endHours = endTime.getHours() + endTime.getMinutes() / 60;
  const duration = Math.max(endHours - startHours, 0.25); // min 15 min display
  return {
    top: startHours * hourHeight,
    height: duration * hourHeight,
  };
}

// ── Month utilities ──

/** Get the first day of the month. */
export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

/** Get the last day of the month. */
export function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59, 999);
}

/** Format as "April 2026". */
export function formatMonthYear(date: Date): string {
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

/** Format as "Monday, April 6, 2026". */
export function formatDayLong(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/** Add N days to a date. */
export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** Add N months to a date. */
export function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

/**
 * Build a 6x7 grid of dates for a month calendar view.
 * Rows start on Monday. Includes leading/trailing days from adjacent months.
 */
export function getMonthGrid(date: Date): Date[][] {
  const first = startOfMonth(date);
  // Shift so Monday=0, Sunday=6
  const startDay = (first.getDay() + 6) % 7;
  const gridStart = addDays(first, -startDay);

  const grid: Date[][] = [];
  for (let week = 0; week < 6; week++) {
    const row: Date[] = [];
    for (let day = 0; day < 7; day++) {
      row.push(addDays(gridStart, week * 7 + day));
    }
    grid.push(row);
  }
  return grid;
}

/** Check if two dates are in the same month and year. */
export function isSameMonth(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}
