"use client";

import { useState, useEffect } from "react";
import { Save, Server, AlertOctagon, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSettings, useUpdateSettings } from "@/hooks/use-workflows";

export default function SettingsPage() {
  const { data: settingsData, isLoading } = useSettings();
  const updateSettingsMutation = useUpdateSettings();
  const [executor, setExecutor] = useState("prism");
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (settingsData?.executor) {
      setExecutor(settingsData.executor);
    }
  }, [settingsData]);

  const handleSave = () => {
    updateSettingsMutation.mutate(executor, {
      onSuccess: () => {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      },
    });
  };

  const isSaving = updateSettingsMutation.isPending;


  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      <section className="flex justify-between items-end relative mb-8">
        <div>
          <h2 className="text-3xl font-bold text-slate-900">Platform Settings</h2>
          <p className="mt-2 text-sm text-slate-500 max-w-2xl leading-relaxed">
            Configure Dell MCP proxy execution environments, manage API keys, and control governance runtime parameters.
          </p>
        </div>
        
        <Button 
          onClick={handleSave} 
          disabled={isSaving}
          className={`h-10 px-6 rounded-xl font-semibold transition-all shadow-sm ${
            saveSuccess 
              ? "bg-emerald-500 hover:bg-emerald-600 text-white" 
              : "bg-slate-900 hover:bg-slate-800 text-white"
          }`}
        >
          {isSaving ? (
            <span className="flex items-center gap-2">Saving...</span>
          ) : saveSuccess ? (
            <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> Saved Successfully</span>
          ) : (
            <span className="flex items-center gap-2"><Save className="w-4 h-4" /> Save Changes</span>
          )}
        </Button>
      </section>

      <div className="grid gap-6">
        
        {/* Execution Engine Settings */}
        <Card className="rounded-xl border-slate-200 shadow-sm overflow-hidden">
          <CardHeader className="bg-slate-50 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <Server className="w-5 h-5 text-emerald-700" />
              </div>
              <div>
                <CardTitle className="text-lg text-slate-900">Execution Engine</CardTitle>
                <CardDescription className="mt-1">
                  Select the backend adapter used for routing approved FastMCP workflows to hardware.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid gap-4 md:grid-cols-3">
              <div 
                onClick={() => setExecutor("prism")}
                className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
                  executor === "prism" 
                    ? "border-emerald-500 bg-emerald-50" 
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-semibold text-slate-900">Prism Simulation</h3>
                  {executor === "prism" && <Badge tone="success">Active</Badge>}
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Routes all requests to a local Prism mock server. Safest for testing OpenAPI spec integrity without real hardware.
                </p>
              </div>

              <div 
                onClick={() => setExecutor("omsdk")}
                className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
                  executor === "omsdk" 
                    ? "border-emerald-500 bg-emerald-50" 
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-semibold text-slate-900">Live iDRAC (OMSDK)</h3>
                  {executor === "omsdk" && <Badge tone="success">Active</Badge>}
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Routes directly to live Dell PowerEdge servers via the OpenManage SDK. Requires network line-of-sight.
                </p>
              </div>

              <div 
                onClick={() => setExecutor("mock")}
                className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
                  executor === "mock" 
                    ? "border-emerald-500 bg-emerald-50" 
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-semibold text-slate-900">Unit Test Mock</h3>
                  {executor === "mock" && <Badge tone="success">Active</Badge>}
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Static JSON response mocks. Used primarily during the CI/CD pipeline integration testing phase.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>


        {/* Danger Zone */}
        <Card className="rounded-xl border-rose-200 shadow-sm overflow-hidden">
          <CardHeader className="bg-rose-50 border-b border-rose-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-rose-100 rounded-lg">
                <AlertOctagon className="w-5 h-5 text-rose-700" />
              </div>
              <div>
                <CardTitle className="text-lg text-rose-900">Danger Zone</CardTitle>
                <CardDescription className="mt-1 text-rose-700/80">
                  Destructive actions that cannot be reversed.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <div className="flex items-center justify-between p-4 border border-rose-100 rounded-xl">
              <div>
                <h4 className="font-semibold text-slate-900">Purge Governance Database</h4>
                <p className="text-sm text-slate-500 mt-1 max-w-md">
                  Permanently deletes all clustered workflows, execution history, and audit trail events. The proxy will require a full OpenAPI re-ingestion.
                </p>
              </div>
              <Button 
                variant="destructive" 
                className="bg-rose-600 hover:bg-rose-700 rounded-lg font-medium whitespace-nowrap px-6"
                onClick={() => {
                  if (window.confirm("Are you absolutely sure you want to purge the governance database? This action is irreversible.")) {
                    window.alert("Database purge initiated.");
                  }
                }}
              >
                Purge Database
              </Button>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
