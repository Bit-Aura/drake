"use client";

import {
  Activity,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
  LogOut,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

import { isActiveRoute, navItems } from "@/components/shell/nav-items";
import { cn } from "@/lib/utils";

const navIcons = {
  "/": LayoutDashboard,
  "/workflows": ListChecks,
  "/graph": GitBranch,
  "/metrics": Activity,
  "/audit": ScrollText,
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 bg-white lg:flex flex-col border-r border-[rgb(var(--border))] rounded-l-3xl">
      <div className="px-6 pt-3 pb-6">
        <Link href="/" className="inline-block transition-transform hover:scale-105 active:scale-95">
          <Image 
            src="/drake-logo.png" 
            alt="Drake Logo" 
            width={240} 
            height={74} 
            style={{ height: "auto" }}
            className="object-contain mix-blend-multiply -ml-4 -mt-2" 
            priority 
          />
        </Link>
      </div>
      <nav aria-label="Primary navigation" className="space-y-1.5 px-4 flex-1">
        {navItems.map((item) => {
          const active = isActiveRoute(pathname, item.href);
          const Icon = navIcons[item.href as keyof typeof navIcons];
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-4 rounded-xl px-4 py-3 text-[14px] font-medium transition-all mb-1",
                active
                  ? "bg-[rgb(var(--primary))] text-[rgb(var(--foreground))] shadow-sm"
                  : "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-gray-50",
              )}
              href={item.href}
              key={item.href}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 mt-auto flex flex-col gap-1">
        <button
          onClick={() => {
            localStorage.removeItem("dell_admin_token");
            localStorage.removeItem("dell_admin_user");
            window.location.href = "/login";
          }}
          className="flex items-center gap-4 rounded-xl px-4 py-3 text-[14px] font-medium transition-all text-[rgb(var(--muted-foreground))] hover:text-rose-600 hover:bg-rose-50 cursor-pointer w-full text-left"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
        <Link
          href="/settings"
          className={cn(
            "flex items-center gap-4 rounded-xl px-4 py-3 text-[14px] font-medium transition-all",
            pathname === "/settings"
              ? "bg-[rgb(var(--primary))] text-[rgb(var(--foreground))] shadow-sm"
              : "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-gray-50",
          )}
        >
          <Settings className="w-4 h-4" />
          Settings
        </Link>
      </div>
    </aside>
  );
}
