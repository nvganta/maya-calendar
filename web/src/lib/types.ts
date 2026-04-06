export interface CalendarEvent {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  location: string | null;
  is_all_day: boolean;
  recurrence: string | null;
  tags: string[] | null;
  category: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  location?: string;
  is_all_day?: boolean;
  recurrence?: string;
  tags?: string[];
  category?: string;
}

export interface EventUpdate {
  title?: string;
  description?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  is_all_day?: boolean;
  recurrence?: string;
  tags?: string[];
  category?: string;
}

export interface Reminder {
  id: string;
  message: string;
  remind_at: string;
  is_sent: boolean;
  event_id: string | null;
  created_at: string;
}

export interface UserSettings {
  timezone: string | null;
  working_hours_start: number;
  working_hours_end: number;
  preferences: Record<string, unknown> | null;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  timezone: string | null;
}

export type EventCategory = "work" | "personal" | "focus" | "health";

export const CATEGORY_COLORS: Record<EventCategory, string> = {
  work: "var(--category-work)",
  personal: "var(--category-personal)",
  focus: "var(--category-focus)",
  health: "var(--category-health)",
};

export const CATEGORY_BG_CLASSES: Record<EventCategory, string> = {
  work: "bg-blue-500",
  personal: "bg-purple-500",
  focus: "bg-amber-500",
  health: "bg-green-500",
};

export const CATEGORY_TEXT_CLASSES: Record<EventCategory, string> = {
  work: "text-blue-600",
  personal: "text-purple-600",
  focus: "text-amber-600",
  health: "text-green-600",
};

export const CATEGORY_LIGHT_BG: Record<EventCategory, string> = {
  work: "bg-blue-50 border-blue-200",
  personal: "bg-purple-50 border-purple-200",
  focus: "bg-amber-50 border-amber-200",
  health: "bg-green-50 border-green-200",
};
