"use client";

import { AuthProvider } from "@/lib/auth";
import { CalendarProvider } from "@/lib/calendar-context";

// TODO: Re-enable AuthGate before production
// Auth bypass for local preview — remove this and restore AuthGate

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <CalendarProvider>
        {children}
      </CalendarProvider>
    </AuthProvider>
  );
}
