"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Lock, Mail, AlertCircle, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("DellAdmin@gmail.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        throw new Error("Invalid credentials");
      }

      const data = await response.json();
      if (data.token) {
        localStorage.setItem("dell_admin_token", data.token);
        localStorage.setItem("dell_admin_user", JSON.stringify(data.user));
        
        // Brief delay to show success state before redirecting
        setTimeout(() => {
          router.push("/");
        }, 300);
      }
    } catch (err) {
      setError((err as Error).message || "An error occurred during login.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto -mt-24">
      <div className="flex justify-center mb-8">
        <Image 
          src="/drake-logo.png?v=5" 
          alt="Drake Logo" 
          width={280} 
          height={88} 
          className="object-contain mix-blend-multiply ml-4" 
          priority 
        />
      </div>

      <Card className="border-slate-200 shadow-xl shadow-slate-200/50 rounded-2xl overflow-hidden relative">
        {/* Subtle top gradient bar */}
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-emerald-400 to-[rgb(var(--primary))]"></div>
        
        <CardHeader className="pt-8 pb-4 text-center">
          <h2 className="text-xl font-bold text-slate-900">Enterprise Access</h2>
          <p className="text-sm text-slate-500 mt-1">Sign in to manage MCP proxy governance.</p>
        </CardHeader>
        
        <CardContent className="px-8 pb-8 pt-2">
          <form onSubmit={handleLogin} className="space-y-5">
            {error && (
              <div className="flex items-center gap-2 p-3 text-sm text-rose-600 bg-rose-50 border border-rose-100 rounded-lg">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Admin Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-4 w-4 text-slate-400" />
                </div>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 h-11 border-slate-200 bg-slate-50 text-slate-900 focus-visible:ring-emerald-500 rounded-xl"
                  placeholder="admin@dell.com"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-4 w-4 text-slate-400" />
                </div>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 h-11 border-slate-200 bg-slate-50 text-slate-900 focus-visible:ring-emerald-500 rounded-xl"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-xl mt-2 transition-all shadow-md group"
            >
              {isLoading ? "Authenticating..." : "Sign In to Dashboard"}
              {!isLoading && <ArrowRight className="w-4 h-4 ml-2 opacity-70 group-hover:translate-x-1 transition-transform" />}
            </Button>
            
            <div className="mt-6 text-center text-xs text-slate-400 font-medium">
              Protected by Dell Secure Proxy Authentication
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
