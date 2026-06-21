"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Treemap,
} from "recharts";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMetrics } from "@/hooks/use-metrics";

// Enterprise Theme Colors
const THEME = {
  primary: "#bde56c", // Approved & Main charts
  slate: "#64748b",   // Pending
  rose: "#f43f5e",    // Rejected
};

const APPROVAL_COLORS = {
  Approved: THEME.primary,
  Rejected: THEME.rose,
  Pending: THEME.slate,
};

function truncateLabel(value: string, max = 18) {
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

const TREEMAP_COLORS = [
  "#064e3b", // Deepest Emerald
  "#047857", // Dark Emerald
  "#059669", // Emerald
  "#4c1d95", // Deep Purple
  "#5b21b6", // Dark Purple
  "#6d28d9", // Purple
  "#1e293b", // Slate 800
  "#334155", // Slate 700
  "#475569", // Slate 600
];

// Custom Treemap Content to render beautiful boxes with text
const CustomTreemapContent = (props: unknown) => {
  const { depth, x, y, width, height, name, value, onMouseEnter, onMouseLeave, onMouseMove, index } = props;
  
  if (depth === 1) {
    const bgColor = TREEMAP_COLORS[(index || 0) % TREEMAP_COLORS.length];
    
    return (
      <g
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onMouseMove={onMouseMove}
      >
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          style={{
            fill: bgColor,
            stroke: "#ffffff",
            strokeWidth: 2,
            strokeOpacity: 0.2,
          }}
          className="transition-all duration-300 hover:opacity-85 hover:stroke-emerald-400 hover:stroke-[3px] cursor-pointer"
        />
        {width > 60 && height > 35 ? (
          <text
            x={x + 8}
            y={y + 20}
            fill="#fff"
            fontSize={13}
            className="font-medium tracking-tight"
          >
            {truncateLabel(name || "", Math.floor(width / 7))}
          </text>
        ) : null}
        {width > 60 && height > 55 ? (
          <text
            x={x + 8}
            y={y + 40}
            fill="#e2e8f0"
            fontSize={14}
            className="font-bold font-mono"
          >
            {value}
          </text>
        ) : null}
      </g>
    );
  }
  return null;
};

export function MetricsDashboard() {
  const { data, isLoading, error } = useMetrics();

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton className="h-32 rounded-xl" key={index} />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="Metrics unavailable"
        description="Operational metrics will appear once the backend metrics endpoint is available."
      />
    );
  }

  const stats = [
    { label: "Endpoint Reduction", value: `${data.endpointReductionRatio}:1`, trend: "up", change: "Optimized" },
    { label: "Exposed Workflows", value: data.workflowCount, trend: "neutral", change: "Stable" },
    { label: "Token Savings", value: `${data.tokenSavingsPercent}%`, trend: "up", change: "Efficient" },
    { label: "Clustering Coverage", value: `${data.clusteringCoveragePercent}%`, trend: "up", change: "Broad" },
    { label: "Approved Posture", value: data.approvedCount, trend: "up", change: "Ready" },
    { label: "Rejected Posture", value: data.rejectedCount, trend: "down", change: "Blocked" },
    { label: "Pending Posture", value: data.pendingCount, trend: "neutral", change: "Action Req" },
    { label: "Raw Endpoints", value: data.rawEndpointCount, trend: "neutral", change: "Total" },
  ];

  const distributionData = data.workflowDistribution.map((entry) => ({
    name: entry.workflowName,
    size: entry.endpointCount,
  }));

  const approvalData = [
    { name: "Approved", value: data.approvedCount },
    { name: "Pending", value: data.pendingCount },
    { name: "Rejected", value: data.rejectedCount },
  ].filter((item) => item.value > 0);
  
  // Total workflows for the center of the Doughnut chart
  const totalWorkflows = approvalData.reduce((acc, curr) => acc + curr.value, 0);

  // Top 12 Workflows for the Bar Chart
  const topWorkflowsData = [...distributionData]
    .sort((a, b) => b.size - a.size)
    .slice(0, 12)
    .map(d => ({
      ...d,
      shortName: truncateLabel(d.name, 18)
    }));

  return (
    <div className="space-y-6">
      {/* Top KPI Row */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, trend, change }) => (
          <Card 
            key={label} 
            className="group relative overflow-hidden rounded-xl border-slate-200 bg-white transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-slate-200/50"
          >
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-lime-400 to-lime-600 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium tracking-tight text-slate-500">{label}</p>
                <div className={`flex items-center space-x-1 rounded-full px-2 py-0.5 text-xs font-semibold
                  ${trend === 'up' ? 'bg-lime-50 text-lime-700' : 
                    trend === 'down' ? 'bg-rose-50 text-rose-700' : 
                    'bg-slate-50 text-slate-700'}`}
                >
                  {trend === 'up' && <ArrowUpRight className="h-3 w-3" />}
                  {trend === 'down' && <ArrowDownRight className="h-3 w-3" />}
                  {trend === 'neutral' && <Minus className="h-3 w-3" />}
                  <span>{change}</span>
                </div>
              </div>
              <p className="mt-4 font-mono text-3xl font-bold tracking-tight text-slate-900">
                {value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Charts Row */}
      <div className="grid gap-6 xl:grid-cols-3">
        {/* Treemap for Distribution */}
        <Card className="xl:col-span-2 rounded-xl shadow-sm border-slate-200 overflow-hidden">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-900">Workflow Consolidation Map</CardTitle>
            <p className="text-sm text-slate-500">Raw endpoints clustered into unified MCP workflows by volume.</p>
          </CardHeader>
          <CardContent className="h-[380px] p-0 px-6 pb-6">
            <ResponsiveContainer height="100%" width="100%" style={{ outline: 'none' }}>
              <Treemap
                style={{ outline: 'none' }}
                data={distributionData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="#fff"
                content={<CustomTreemapContent />}
              >
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg z-50">
                          <p className="mb-1 font-semibold text-slate-900">{data.name || 'Workflow'}</p>
                          <p className="text-sm text-slate-600">
                            <span className="font-medium text-emerald-600">{data.value || data.size}</span> endpoints
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
              </Treemap>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Doughnut for Approval Posture */}
        <Card className="rounded-xl shadow-sm border-slate-200 overflow-hidden">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-900">Approval Posture</CardTitle>
            <p className="text-sm text-slate-500">Current status of exposed workflows.</p>
          </CardHeader>
          <CardContent className="h-[380px] relative p-0 px-6 pb-6">
            <ResponsiveContainer height="100%" width="100%" style={{ outline: 'none' }}>
              <PieChart style={{ outline: 'none' }}>
                <Pie
                  data={approvalData}
                  cx="50%"
                  cy="50%"
                  innerRadius={100}
                  outerRadius={140}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {approvalData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={APPROVAL_COLORS[entry.name as keyof typeof APPROVAL_COLORS]} 
                      className="transition-all duration-300 hover:opacity-80 outline-none"
                    />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)" }}
                  itemStyle={{ fontWeight: 600 }}
                />
              </PieChart>
            </ResponsiveContainer>
            
            {/* Absolute center label */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-6">
              <span className="text-5xl font-mono font-bold text-slate-900">{totalWorkflows}</span>
              <span className="text-sm font-medium tracking-wide text-slate-500 uppercase mt-1">Workflows</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Workflows Bar Chart */}
      <Card className="rounded-xl shadow-sm border-slate-200 overflow-hidden">
        <CardHeader>
          <CardTitle className="text-lg font-bold text-slate-900">Top 12 Workflows by Endpoint Volume</CardTitle>
          <p className="text-sm text-slate-500">Visualizing the number of endpoints packed into the highest density exposed workflows.</p>
        </CardHeader>
        <CardContent className="h-80 pt-4 px-2 outline-none focus:outline-none">
          <ResponsiveContainer height="100%" width="100%" style={{ outline: 'none' }}>
            <BarChart data={topWorkflowsData} margin={{ top: 10, right: 30, left: 0, bottom: 40 }} style={{ outline: 'none' }}>
              <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#f1f5f9" />
              <XAxis 
                dataKey="shortName" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 12, fontWeight: 600, fill: "#334155" }}
                dy={15}
                angle={-25}
                textAnchor="end"
                height={60}
              />
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 12, fill: "#94a3b8", fontWeight: 500 }}
                dx={-10}
              />
              <Tooltip 
                cursor={{ fill: "#f8fafc" }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg z-50">
                        <p className="mb-1 font-semibold text-slate-900">{data.name}</p>
                        <p className="text-sm text-slate-600">
                          <span className="font-medium text-lime-600">{data.size}</span> endpoints
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar 
                dataKey="size" 
                fill={THEME.primary} 
                radius={[4, 4, 0, 0]} 
                barSize={32}
              />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
