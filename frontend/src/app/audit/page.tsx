import { AuditTrail } from "@/components/audit/audit-trail";

export default function AuditPage() {
  return (
    <div className="space-y-5">
      <section className="mb-6">
        <h2 className="text-3xl font-bold text-slate-900">Audit Trail</h2>
        <p className="mt-2 text-sm text-slate-500 max-w-xl leading-relaxed">
          Track workflow lifecycle events from generation through controlled FastMCP
          registration.
        </p>
      </section>
      <AuditTrail />
    </div>
  );
}

