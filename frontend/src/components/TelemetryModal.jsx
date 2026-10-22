import React, { useState, useEffect } from 'react';
import {
  X,
  RefreshCw,
  Activity,
  Zap,
  Clock,
  Coins,
  ShieldCheck,
  ShieldAlert,
  EyeOff,
  CheckCircle2,
  Server,
} from 'lucide-react';
import { fetchSystemMetrics } from '../services/api';

export default function TelemetryModal({ isOpen, onClose }) {
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadMetrics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchSystemMetrics();
      setMetrics(data);
    } catch (err) {
      setError(err?.message || 'Unable to retrieve system metrics');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadMetrics();
    }
  }, [isOpen]);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const formatUptime = (seconds) => {
    if (!seconds && seconds !== 0) return 'N/A';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <span>Operational Telemetry &amp; System Health</span>
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Live</span>
                </span>
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Live latency percentiles, token usage, and security guardrail counters
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={loadMetrics}
              disabled={isLoading}
              title="Refresh live metrics"
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800 transition"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-sky-500' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {/* 4 Core Telemetry Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* 1. Latency */}
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between text-slate-400 mb-1.5">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Avg Latency</span>
                <Clock className="w-3.5 h-3.5 text-sky-500" />
              </div>
              <div className="text-lg font-bold font-mono text-slate-900 dark:text-white">
                {metrics?.latency?.avg_ms ? `${metrics.latency.avg_ms.toFixed(0)}ms` : '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 font-mono">
                p50: {metrics?.latency?.p50_ms ?? 0}ms &middot; p95: {metrics?.latency?.p95_ms ?? 0}ms
              </div>
            </div>

            {/* 2. Total Tokens */}
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between text-slate-400 mb-1.5">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Total Tokens</span>
                <Zap className="w-3.5 h-3.5 text-amber-500" />
              </div>
              <div className="text-lg font-bold font-mono text-slate-900 dark:text-white">
                {metrics?.tokens?.total_tokens ? metrics.tokens.total_tokens.toLocaleString() : '0'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 font-mono">
                {metrics?.tokens?.prompt_tokens?.toLocaleString() ?? 0} in / {metrics?.tokens?.completion_tokens?.toLocaleString() ?? 0} out
              </div>
            </div>

            {/* 3. Cumulative Cost */}
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between text-slate-400 mb-1.5">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Total AI Cost</span>
                <Coins className="w-3.5 h-3.5 text-emerald-500" />
              </div>
              <div className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
                ${metrics?.tokens?.cumulative_cost_usd !== undefined ? metrics.tokens.cumulative_cost_usd.toFixed(4) : '0.0000'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
                Gemini 2.5 Flash Pricing
              </div>
            </div>

            {/* 4. Requests & Uptime */}
            <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between text-slate-400 mb-1.5">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Requests</span>
                <Server className="w-3.5 h-3.5 text-purple-500" />
              </div>
              <div className="text-lg font-bold font-mono text-slate-900 dark:text-white">
                {metrics?.total_requests ?? 0}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 font-mono">
                Uptime: {formatUptime(metrics?.uptime_seconds)}
              </div>
            </div>
          </div>

          {/* Security Guardrail Incident Counters */}
          <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-3">
            <h4 className="text-xs font-bold text-slate-800 dark:text-slate-300 flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-sky-500" />
              <span>Security Guardrail Statistics</span>
            </h4>
            <div className="grid grid-cols-3 gap-2.5">
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
                <div className="flex items-center justify-center space-x-1 text-emerald-600 dark:text-emerald-400 text-xs mb-0.5 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Clean</span>
                </div>
                <div className="text-base font-bold font-mono text-slate-900 dark:text-white">
                  {metrics?.security?.clean_tickets ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400">Passed Unaltered</div>
              </div>

              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center">
                <div className="flex items-center justify-center space-x-1 text-amber-600 dark:text-amber-400 text-xs mb-0.5 font-semibold">
                  <EyeOff className="w-3.5 h-3.5" />
                  <span>PII Redacted</span>
                </div>
                <div className="text-base font-bold font-mono text-slate-900 dark:text-white">
                  {metrics?.security?.sanitized_pii_tickets ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400">Secrets Masked</div>
              </div>

              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-center">
                <div className="flex items-center justify-center space-x-1 text-rose-600 dark:text-rose-400 text-xs mb-0.5 font-semibold">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Quarantined</span>
                </div>
                <div className="text-base font-bold font-mono text-slate-900 dark:text-white">
                  {metrics?.security?.quarantined_attacks ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400">Jailbreaks Blocked</div>
              </div>
            </div>
          </div>

          {/* Category & Urgency Distribution */}
          {metrics?.distribution && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-2">Category Breakdown</span>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(metrics.distribution.categories || {}).length === 0 ? (
                    <span className="text-slate-400 text-[11px]">No requests recorded yet</span>
                  ) : (
                    Object.entries(metrics.distribution.categories).map(([cat, count]) => (
                      <span
                        key={cat}
                        className="px-2 py-0.5 rounded-md bg-slate-200/80 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono text-[10px] text-slate-700 dark:text-slate-300"
                      >
                        {cat}: <strong>{count}</strong>
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-2">Urgency Distribution</span>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(metrics.distribution.urgencies || {}).length === 0 ? (
                    <span className="text-slate-400 text-[11px]">No requests recorded yet</span>
                  ) : (
                    Object.entries(metrics.distribution.urgencies).map(([urg, count]) => (
                      <span
                        key={urg}
                        className="px-2 py-0.5 rounded-md bg-slate-200/80 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono text-[10px] text-slate-700 dark:text-slate-300"
                      >
                        {urg}: <strong>{count}</strong>
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60 flex items-center justify-between text-xs text-slate-500">
          <span>Endpoint: <code className="font-mono text-sky-600 dark:text-sky-400">GET /api/v1/metrics</code></span>
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 text-xs font-medium hover:opacity-90 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
