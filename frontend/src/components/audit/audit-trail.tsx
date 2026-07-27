"use client";

import { useMemo, useState } from "react";
import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, Filter } from "lucide-react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useAuditEvents } from "@/hooks/use-audit";
import type { AuditEvent } from "@/lib/types";

const eventTypes = [
  "all",
  "workflow_generated",
  "workflow_reviewed",
  "workflow_approved",
  "workflow_rejected",
  "workflow_updated",
  "mcp_registered",
] as const;

function matchesSearch(event: AuditEvent, query: string) {
  const haystack = [
    event.eventType,
    event.status,
    event.workflowName,
    event.description,
    event.actor,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

export function AuditTrail() {
  const { data, isLoading, error } = useAuditEvents();
  const [eventFilter, setEventFilter] = useState<(typeof eventTypes)[number]>("all");
  const [search, setSearch] = useState("");

  const handleExportCSV = () => {
    const headers = ["Date/Time", "Event Type", "Status", "Workflow", "Description", "Actor"];
    const rows = filteredEvents.map(event => [
      new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(event.timestamp)),
      event.eventType,
      event.status,
      event.workflowName || "",
      event.description,
      event.actor
    ]);

    const escapeCSV = (val: any) => {
      if (val === null || val === undefined) return '';
      const formatted = val.toString().replace(/"/g, '""');
      if (formatted.includes(',') || formatted.includes('"') || formatted.includes('\n') || formatted.includes('\r')) {
        return `"${formatted}"`;
      }
      return formatted;
    };

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(escapeCSV).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "audit_trail_export.csv");
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    return data.filter((event) => {
      const matchesType =
        eventFilter === "all" ||
        event.eventType.toLowerCase() === eventFilter.replaceAll("_", " ") ||
        event.eventType.toLowerCase() === eventFilter ||
        event.eventType.toLowerCase().includes(eventFilter.replaceAll("_", " "));
      const matchesQuery = !search.trim() || matchesSearch(event, search.trim());
      return matchesType && matchesQuery;
    });
  }, [data, eventFilter, search]);

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton className="h-20" key={index} />
        ))}
      </div>
    );
  }

  if (!data?.length) {
    return (
      <EmptyState
        title="No audit events"
        description="Workflow generation, review, approval, and MCP registration events will be listed here."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Input
          aria-label="Search audit events"
          className="max-w-md"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by workflow, actor, or description"
          value={search}
        />
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Select.Root
            value={eventFilter}
            onValueChange={(value) => setEventFilter(value as (typeof eventTypes)[number])}
          >
            <Select.Trigger className="flex h-10 w-[220px] items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-slate-400" />
                <Select.Value />
              </div>
              <Select.Icon>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </Select.Icon>
            </Select.Trigger>

            <Select.Portal>
              <Select.Content
                position="popper"
                sideOffset={4}
                className="z-50 w-[220px] overflow-hidden rounded-xl border border-slate-100 bg-white text-slate-700 shadow-lg"
              >
                <Select.Viewport className="p-1">
                  {eventTypes.map((type) => (
                    <Select.Item
                      key={type}
                      value={type}
                      className="relative flex w-full cursor-pointer select-none items-center rounded-lg py-2.5 pl-3 pr-9 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-slate-100 data-[highlighted]:text-slate-900 transition-colors"
                    >
                      <Select.ItemText>
                        <span className="capitalize">
                          {type === "all" ? "All events" : type.replaceAll("_", " ")}
                        </span>
                      </Select.ItemText>
                      <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
                        <Select.ItemIndicator>
                          <Check className="h-4 w-4" />
                        </Select.ItemIndicator>
                      </span>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>
          <Button onClick={handleExportCSV}>Export CSV</Button>
        </div>
      </div>

      {!filteredEvents.length ? (
        <EmptyState
          title="No matching audit events"
          description="Adjust the search query or event filter to view lifecycle records."
        />
      ) : (
        <div className="space-y-3">
          {filteredEvents.map((event) => {
            const statusColor = 
              event.status === "success" ? "bg-emerald-500" :
              event.status === "error" || event.status === "failed" ? "bg-rose-500" :
              event.status === "pending" ? "bg-amber-500" : "bg-slate-400";
              
            return (
              <Card className="relative p-5 rounded-xl border-slate-200 bg-white transition-all duration-300 hover:shadow-md hover:-translate-y-0.5 hover:shadow-slate-200/50 overflow-hidden group" key={event.id}>
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${statusColor} opacity-80 transition-all duration-300 group-hover:w-1.5 group-hover:opacity-100`} />
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between pl-2">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className="text-base font-bold text-slate-900 tracking-tight capitalize">
                        {event.eventType.replaceAll("_", " ")}
                      </h3>
                      <Badge tone={event.status === "success" ? "success" : event.status === "error" || event.status === "failed" ? "danger" : event.status === "pending" ? "warning" : "neutral"} className="uppercase text-[10px] font-bold tracking-wider px-2 py-0.5">
                        {event.status}
                      </Badge>
                      {event.workflowName ? (
                        <Badge tone="default" className="text-xs bg-slate-100 text-slate-700 font-mono">
                          {event.workflowName}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-slate-600 leading-relaxed max-w-3xl">{event.description}</p>
                    <div className="mt-3 flex items-center gap-4">
                      <p className="text-xs font-medium text-slate-500 flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-100">
                        <span className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
                        Actor: <span className="text-slate-700 font-semibold">{event.actor}</span>
                      </p>
                    </div>
                  </div>
                  <time className="text-xs font-medium text-slate-500 flex items-center bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100 mt-2 sm:mt-0 whitespace-nowrap" dateTime={event.timestamp}>
                    {new Intl.DateTimeFormat(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(event.timestamp))}
                  </time>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
