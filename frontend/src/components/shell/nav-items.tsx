import Link from "next/link";

import { cn } from "@/lib/utils";
import { usePendingWorkflows } from "@/hooks/use-workflows";

export const navItems = [
  { href: "/", label: "Overview" },
  { href: "/workflows", label: "Workflow Review" },
  { href: "/graph", label: "Graph Visualization" },
  { href: "/metrics", label: "Metrics" },
  { href: "/audit", label: "Audit Trail" },
  { href: "/agent", label: "AI Agent" },
] as const;

export function isActiveRoute(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function NavLinks({
  pathname,
  onNavigate,
  className,
}: {
  pathname: string;
  onNavigate?: () => void;
  className?: string;
}) {
  const { data: pendingWorkflows } = usePendingWorkflows();
  const pendingCount = pendingWorkflows?.length || 0;

  return (
    <nav aria-label="Primary navigation" className={cn("space-y-1", className)}>
      {navItems.map((item) => {
        const active = isActiveRoute(pathname, item.href);
        const isWorkflowReview = item.href === "/workflows";
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-sky-50 text-sky-900"
                : "text-slate-700 hover:bg-slate-100",
            )}
            href={item.href}
            key={item.href}
            onClick={onNavigate}
          >
            {item.label}
            {isWorkflowReview && pendingCount > 0 && (
              <span className="bg-amber-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ml-auto">
                {pendingCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
