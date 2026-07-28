import { Suspense } from "react";
import { WorkflowReviewTable } from "@/components/workflows/workflow-review-table";

export default function WorkflowReviewPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-950">Workflow Review</h2>
      <Suspense fallback={<div>Loading workflows...</div>}>
        <WorkflowReviewTable />
      </Suspense>
    </div>
  );
}

