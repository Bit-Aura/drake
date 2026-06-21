"use client";

import { Activity, Database, GitBranch, ServerCog } from "lucide-react";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOverview } from "@/hooks/use-overview";
import type { PipelineStatus } from "@/lib/types";

const cards = [
  { key: "endpointCount", label: "Raw Endpoints", icon: Database },
  { key: "workflowCount", label: "Discovered Workflows", icon: GitBranch },
  { key: "pendingReviewCount", label: "Pending Review", icon: Activity },
  { key: "registeredWorkflowCount", label: "Registered MCP Tools", icon: ServerCog },
] as const;

const pipelineStages = [
  { key: "ingestionStatus", label: "OpenAPI ingestion" },
  { key: "graphStatus", label: "NetworkX graph" },
  { key: "clusteringStatus", label: "Leiden clustering" },
  { key: "mcpRuntimeStatus", label: "FastMCP runtime" },
] as const;

function statusTone(
  value?: PipelineStatus,
): "success" | "warning" | "danger" | "neutral" {
  switch (value) {
    case "complete":
      return "success";
    case "running":
      return "warning";
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

export default function OverviewPage() {
  const { data, isLoading, error } = useOverview();

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto relative">
      <section className="flex justify-between items-end relative">
        <div>
          <h2 className="text-3xl font-bold text-[rgb(var(--foreground))]">Overview</h2>
          <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))] max-w-xl">
            Monitor ingestion, graph clustering, approval posture, and MCP runtime registration from one governed surface.
          </p>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const CardContentComponent = (
            <>
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-400 to-emerald-600 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
              <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500 opacity-[0.03] rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
              <CardContent className="flex flex-col pt-6 relative z-10 p-6">
                <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center border border-emerald-100 mb-4 transition-colors group-hover:bg-emerald-100">
                  <card.icon className="h-6 w-6 text-emerald-600" />
                </div>
                <p className="text-sm font-medium tracking-tight text-slate-500">{card.label}</p>
                {isLoading ? (
                  <Skeleton className="mt-2 h-10 w-20 rounded-lg" />
                ) : (
                  <p className="mt-2 font-mono text-4xl font-bold tracking-tight text-slate-900">
                    {data?.[card.key] ?? 0}
                  </p>
                )}
              </CardContent>
            </>
          );

          if (card.key === "registeredWorkflowCount") {
            return (
              <div key={card.key} className="relative">
                <Card className="relative overflow-hidden group border-slate-200 bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-slate-200/50">
                  {CardContentComponent}
                </Card>
              </div>
            );
          }

          return (
            <Card key={card.key} className="relative overflow-hidden group border-slate-200 bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-slate-200/50">
              {CardContentComponent}
            </Card>
          );
        })}
      </section>

      <Card className="overflow-hidden mb-8">
        <CardHeader className="bg-gray-50/50 border-b border-[rgb(var(--border))]">
          <CardTitle className="text-lg">Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="grid md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-[rgb(var(--border))]">
            {pipelineStages.map((stage) => {
              const value = data?.[stage.key];
              return (
                <div className="p-6 flex flex-col justify-between hover:bg-gray-50/50 transition-colors" key={stage.key}>
                  <div className="text-xs font-semibold text-[rgb(var(--muted-foreground))] uppercase tracking-wider">{stage.label}</div>
                  <div className="mt-4">
                    {isLoading ? (
                      <Skeleton className="h-6 w-24 rounded-full" />
                    ) : (
                      <Badge tone={statusTone(value)}>{value ?? "unknown"}</Badge>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
