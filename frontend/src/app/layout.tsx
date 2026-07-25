import type { Metadata } from "next";
import type {  } from "react";

import "@/app/globals.css";
import { Providers } from "@/components/providers";
import { LayoutWrapper } from "@/components/shell/layout-wrapper";

export const metadata: Metadata = {
  title: "Dell MCP Proxy Governance",
  description: "Human-in-the-loop workflow governance and observability",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>
          <div className="flex h-screen bg-gradient-to-br from-black to-[#2a3c1f] p-4 md:p-8 overflow-hidden">
            <LayoutWrapper>
              {children}
            </LayoutWrapper>
          </div>
        </Providers>
      </body>
    </html>
  );
}
