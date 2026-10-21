import React from 'react';
import { AlertTriangle, Clock, XCircle, X, ShieldAlert, WifiOff } from 'lucide-react';

export default function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;

  const isRateLimit = error.code === 'RATE_LIMIT_EXCEEDED' || error.status === 429;
  const isNetwork = error.code === 'NETWORK_ERROR' || error.status === 0;
  const isValidation = error.code === 'VALIDATION_ERROR' || error.status === 422;

  let borderColor = 'border-rose-300 dark:border-rose-500/30';
  let bgColor = 'bg-rose-50 dark:bg-rose-950/40';
  let iconColor = 'text-rose-600 dark:text-rose-400';
  let badgeLabel = 'System Error';
  let Icon = XCircle;

  if (isRateLimit) {
    borderColor = 'border-amber-300 dark:border-amber-500/40';
    bgColor = 'bg-amber-50 dark:bg-amber-950/30';
    iconColor = 'text-amber-600 dark:text-amber-400';
    badgeLabel = 'Rate Limit / Quota Exceeded (HTTP 429)';
    Icon = Clock;
  } else if (isNetwork) {
    borderColor = 'border-orange-300 dark:border-orange-500/40';
    bgColor = 'bg-orange-50 dark:bg-orange-950/30';
    iconColor = 'text-orange-600 dark:text-orange-400';
    badgeLabel = 'Network Connection Error';
    Icon = WifiOff;
  } else if (isValidation) {
    borderColor = 'border-blue-300 dark:border-blue-500/40';
    bgColor = 'bg-blue-50 dark:bg-blue-950/30';
    iconColor = 'text-blue-600 dark:text-blue-400';
    badgeLabel = 'Input Validation Error';
    Icon = ShieldAlert;
  }

  return (
    <div className={`rounded-xl border ${borderColor} ${bgColor} p-4 mb-6 shadow-sm dark:shadow-xl backdrop-blur-md transition-all animate-in fade-in slide-in-from-top-2 duration-200`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3.5">
          <div className={`p-2 rounded-lg bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/50 mt-0.5 ${iconColor}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <span className={`text-xs font-mono font-semibold uppercase px-2 py-0.5 rounded-full bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-700/60 ${iconColor}`}>
                {badgeLabel}
              </span>
              {error.retries_attempted > 0 && (
                <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                  ({error.retries_attempted} retries attempted with exponential backoff)
                </span>
              )}
            </div>
            
            <p className="mt-1.5 text-sm font-medium text-slate-900 dark:text-slate-200 leading-relaxed">
              {error.message}
            </p>

            {isRateLimit && (
              <p className="mt-2 text-xs text-amber-800/80 dark:text-amber-300/80">
                💡 <span className="font-semibold">Actionable Tip:</span> The backend exponential backoff policy automatically attempted 3 retries with random jitter before surfacing this alert. Check your Gemini API quota or switch to <code>gemini-2.5-flash</code> in <code>.env</code>.
              </p>
            )}

            {isNetwork && (
              <p className="mt-2 text-xs text-orange-800/80 dark:text-orange-300/80">
                💡 <span className="font-semibold">Actionable Tip:</span> Ensure the FastAPI backend is running locally at <code>http://127.0.0.1:8000</code> via native virtualenv or Docker.
              </p>
            )}

            {error.details && typeof error.details === 'object' && (
              <pre className="mt-2 text-[11px] font-mono p-2 rounded bg-slate-100 dark:bg-slate-950/60 text-slate-700 dark:text-slate-400 border border-slate-200 dark:border-slate-800 overflow-x-auto max-h-24">
                {JSON.stringify(error.details, null, 2)}
              </pre>
            )}
          </div>
        </div>

        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800/60 transition ml-4"
          title="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
