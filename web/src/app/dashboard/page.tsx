"use client";

import { useState, useCallback } from "react";
import Header from "@/components/header";
import Sidebar from "@/components/sidebar";
import WeekView from "@/components/calendar/week-view";
import EventModal from "@/components/calendar/event-modal";
import SettingsModal from "@/components/settings-modal";
import { useCalendar } from "@/lib/calendar-context";
import { useEvents } from "@/hooks/use-events";
import type { CalendarEvent } from "@/lib/types";

export default function DashboardPage() {
  const { viewType, sidebarOpen } = useCalendar();
  const { events, loading, error, createEvent, updateEvent, deleteEvent, refetch } =
    useEvents();

  // Modal state
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [defaultStart, setDefaultStart] = useState<Date | undefined>();
  const [showSettings, setShowSettings] = useState(false);

  const openNewEvent = useCallback((date?: Date, hour?: number) => {
    if (date && hour !== undefined) {
      const d = new Date(date);
      d.setHours(hour, 0, 0, 0);
      setDefaultStart(d);
    } else {
      setDefaultStart(undefined);
    }
    setEditingEvent(null);
    setShowEventModal(true);
  }, []);

  const openEditEvent = useCallback((event: CalendarEvent) => {
    setEditingEvent(event);
    setDefaultStart(undefined);
    setShowEventModal(true);
  }, []);

  const handleSave = async (data: {
    title: string;
    description: string;
    start_time: string;
    end_time: string;
    location: string;
    category: string;
    is_all_day: boolean;
  }) => {
    try {
      if (editingEvent) {
        await updateEvent(editingEvent.id, data);
      } else {
        await createEvent(data);
      }
      setShowEventModal(false);
      setEditingEvent(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save event");
    }
  };

  const handleDelete = async () => {
    if (!editingEvent) return;
    try {
      await deleteEvent(editingEvent.id);
      setShowEventModal(false);
      setEditingEvent(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete event");
    }
  };

  const renderView = () => {
    if (loading && events.length === 0) {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      );
    }

    switch (viewType) {
      case "day":
      case "agenda":
      case "month":
        // Placeholder until Phase 2 views are built
        return (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-lg font-medium capitalize">{viewType} view</p>
              <p className="text-sm mt-1">Coming soon. Switch to Week view for now.</p>
            </div>
          </div>
        );
      case "week":
      default:
        return (
          <WeekView
            events={events}
            onEventClick={openEditEvent}
            onSlotClick={(date, hour) => openNewEvent(date, hour)}
          />
        );
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <Header
        onNewEvent={() => openNewEvent()}
        onOpenSettings={() => setShowSettings(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        {sidebarOpen && <Sidebar />}

        <main className="flex-1 overflow-hidden">
          {error && (
            <div className="mx-4 mt-2 px-4 py-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
              {error}
              <button onClick={refetch} className="ml-2 underline">
                Retry
              </button>
            </div>
          )}
          {renderView()}
        </main>
      </div>

      {/* Modals */}
      {showEventModal && (
        <EventModal
          event={editingEvent}
          defaultStart={defaultStart}
          onSave={handleSave}
          onDelete={editingEvent ? handleDelete : undefined}
          onClose={() => {
            setShowEventModal(false);
            setEditingEvent(null);
          }}
        />
      )}

      {showSettings && (
        <SettingsModal onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}
