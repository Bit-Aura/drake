"use client";

import { Play, RefreshCw, User, Send } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useOverview } from "@/hooks/use-overview";
import { useRunPipeline, usePublishPipeline } from "@/hooks/use-workflows";

function getRelativeTimeString(timestamp: number) {
  if (!timestamp) return "Connecting...";
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return "Updated just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `Updated ${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Updated ${hours} hr${hours === 1 ? "" : "s"} ago`;
  return "Updated more than a day ago";
}

export function Topbar() {
  const pathname = usePathname();
  const { isFetching, refetch, dataUpdatedAt } = useOverview();
  const runPipelineMutation = useRunPipeline();
  const publishPipelineMutation = usePublishPipeline();
  const [timeAgo, setTimeAgo] = useState("Updated just now");

  useEffect(() => {
    if (!dataUpdatedAt) {
      setTimeAgo("Connecting...");
      return;
    }
    const updateTime = () => setTimeAgo(getRelativeTimeString(dataUpdatedAt));
    updateTime();
    const interval = setInterval(updateTime, 10000);
    return () => clearInterval(interval);
  }, [dataUpdatedAt]);

  // Create a simple breadcrumb from pathname
  const pageName = pathname === "/" ? "Overview" : pathname.substring(1).charAt(0).toUpperCase() + pathname.substring(2);

  return (
    <header className="flex min-h-16 items-center justify-between px-8 py-4 bg-[rgb(var(--card))] rounded-tr-3xl border-b border-[rgb(var(--border))]">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-bold text-[rgb(var(--foreground))]">{pageName}</h2>
        <div className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${isFetching ? "bg-amber-400 animate-pulse" : "bg-emerald-500"} ring-2 ${isFetching ? "ring-amber-400/20" : "ring-emerald-500/20"}`} />
          <span className="text-xs text-[rgb(var(--muted-foreground))]">{timeAgo}</span>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        {/* Admin Profile */}
        <div className="flex items-center gap-2 mr-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 shadow-sm cursor-default">
          <div className="relative flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-200">
            <User className="h-3 w-3 text-slate-600" />
            <span className="absolute bottom-0 right-0 h-1.5 w-1.5 rounded-full bg-emerald-500 ring-1 ring-white" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-none">Admin</span>
          </div>
        </div>

        <Button
          aria-label="Refresh overview data"
          disabled={isFetching || runPipelineMutation.isPending || publishPipelineMutation.isPending}
          onClick={() => refetch()}
          size="sm"
          variant="secondary"
          className="rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 border-none shadow-none font-semibold text-xs"
        >
          <RefreshCw className={isFetching ? "mr-2 h-3 w-3 animate-spin" : "mr-2 h-3 w-3"} />
          Refresh
        </Button>
        
        <Button
          aria-label="Run ingestion and clustering pipeline"
          disabled={isFetching || runPipelineMutation.isPending || publishPipelineMutation.isPending}
          onClick={() => runPipelineMutation.mutate()}
          size="sm"
          variant="secondary"
          className="rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 border-none shadow-none font-semibold text-xs"
        >
          {runPipelineMutation.isPending ? (
            <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
          ) : (
            <Play className="mr-2 h-3 w-3" />
          )}
          Run Once
        </Button>
        
        <Button
          aria-label="Publish approved workflows to MCP runtime"
          disabled={isFetching || runPipelineMutation.isPending || publishPipelineMutation.isPending}
          onClick={() => publishPipelineMutation.mutate()}
          size="sm"
          className="rounded-full bg-[rgb(var(--primary))] hover:bg-[#a5cc5f] text-black font-semibold text-xs shadow-sm border-none"
        >
          {publishPipelineMutation.isPending ? (
            <RefreshCw className="mr-2 h-3 w-3 animate-spin text-black" />
          ) : (
            <Send className="mr-2 h-3 w-3 text-black" />
          )}
          Publish
        </Button>
      </div>
    </header>
  );
}
