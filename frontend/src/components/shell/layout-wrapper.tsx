"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";

export function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isClient, setIsClient] = useState(false);
  
  useEffect(() => {
    setIsClient(true);
    // Simple auth check
    const isLoginPage = pathname === "/login";
    const token = localStorage.getItem("dell_admin_token");
    
    if (!token && !isLoginPage) {
      router.push("/login");
    } else if (token && isLoginPage) {
      router.push("/");
    }
  }, [pathname, router]);

  const isLoginPage = pathname === "/login";

  // Prevent hydration mismatch flashes
  if (!isClient) return null;

  if (isLoginPage) {
    return (
      <div className="flex flex-1 overflow-hidden bg-[rgb(var(--background))] rounded-3xl shadow-2xl relative items-center justify-center">
        {children}
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden bg-[rgb(var(--background))] rounded-3xl shadow-2xl">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Topbar />
        <main className="flex-1 p-6 lg:p-10 relative">
          {children}
        </main>
      </div>
    </div>
  );
}
