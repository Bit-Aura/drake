import { AlertCircle } from "lucide-react";

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
      <AlertCircle className="mx-auto mb-3 h-8 w-8 text-red-500" />
      <div className="text-sm font-semibold text-red-900">Unable to load data</div>
      <p className="mx-auto mt-1 max-w-xl text-sm text-red-700">{message}</p>
      {onRetry ? (
        <button
          className="mt-3 text-sm font-medium text-red-900 underline hover:text-red-800"
          onClick={onRetry}
          type="button"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

