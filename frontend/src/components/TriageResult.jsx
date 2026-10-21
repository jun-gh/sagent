import React, { useState } from 'react';
import {
  CheckCircle2,
  Copy,
  Check,
  AlertTriangle,
  BookOpen,
  GitBranch,
  Layers,
  Clock,
  Sparkles,
  ExternalLink,
  ChevronRight,
  X,
  FileText,
  Link as LinkIcon,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';

const URGENCY_CONFIG = {
  CRITICAL: {
    bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    dot: 'bg-rose-400',
    label: 'Critical / P0',
  },
  HIGH: {
    bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    dot: 'bg-amber-400',
    label: 'High Urgency',
  },
  MEDIUM: {
    bg: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
    dot: 'bg-sky-400',
    label: 'Medium Urgency',
  },
  LOW: {
    bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-400',
    label: 'Low Urgency',
  },
};

const CANONICAL_FALLBACK_URLS = {
  AUTH: 'https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application',
  BILLING: 'https://docs.stripe.com/refunds',
  TECHNICAL: 'https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS',
};

const resolveValidUrl = (url, category, title) => {
  if (!url || url.includes('sagent.internal') || url.includes('.internal')) {
    const t = (title || '').toLowerCase();
    if (t.includes('rate') || t.includes('429')) return 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429';
    if (t.includes('postgres') || t.includes('deadlock') || t.includes('lock')) {
      return 'https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS';
    }
    if (t.includes('stripe') || t.includes('refund') || t.includes('invoice') || t.includes('charge')) {
      return 'https://docs.stripe.com/refunds';
    }
    if (t.includes('sso') || t.includes('saml') || t.includes('okta') || t.includes('login') || t.includes('cert')) {
      return 'https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application';
    }
    if (t.includes('rbac') || t.includes('invite') || t.includes('permission')) {
      return 'https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories';
    }
    return CANONICAL_FALLBACK_URLS[category] || 'https://developer.mozilla.org';
  }
  return url;
};

// Converts raw RRF reciprocal fractions (max ~0.01639 for k=60) into intuitive 0-100% Relevance Match percentages
const formatRelevancePercentage = (rawRrfScore) => {
  if (!rawRrfScore || rawRrfScore <= 0) return '0% Match';
  const maxRrfScore = 1.0 / 61.0; // 0.0163934 (Rank 1 dense + Rank 1 sparse at k=60)

  if (rawRrfScore <= 0.05) {
    const ratio = Math.min(1.0, rawRrfScore / maxRrfScore);
    const percent = Math.max(10, Math.round(ratio * 100));
    return `${percent}% Match`;
  }

  const percent = Math.min(100, Math.round(rawRrfScore * 100));
  return `${percent}% Match`;
};

export default function TriageResult({ result }) {
  const [copiedReply, setCopiedReply] = useState(false);
  const [copiedModalUrl, setCopiedModalUrl] = useState(false);
  const [copiedModalText, setCopiedModalText] = useState(false);
  const [cardCopiedIdx, setCardCopiedIdx] = useState(null);
  const [checkedSteps, setCheckedSteps] = useState({});
  const [selectedRunbook, setSelectedRunbook] = useState(null);

  if (!result) return null;

  const urgency = URGENCY_CONFIG[result.urgency] || URGENCY_CONFIG.MEDIUM;

  const handleCopyReply = () => {
    navigator.clipboard.writeText(result.suggested_reply);
    setCopiedReply(true);
    setTimeout(() => setCopiedReply(false), 2000);
  };

  const handleCopyModalUrl = (url) => {
    if (!url) return;
    navigator.clipboard.writeText(url);
    setCopiedModalUrl(true);
    setTimeout(() => setCopiedModalUrl(false), 2000);
  };

  const handleCopyModalText = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedModalText(true);
    setTimeout(() => setCopiedModalText(false), 2000);
  };

  const handleCopyCardUrl = (e, url, idx) => {
    e.stopPropagation();
    if (!url) return;
    navigator.clipboard.writeText(url);
    setCardCopiedIdx(idx);
    setTimeout(() => setCardCopiedIdx(null), 2000);
  };

  const toggleStep = (idx) => {
    setCheckedSteps((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  const modalValidUrl = selectedRunbook
    ? resolveValidUrl(selectedRunbook.source_url, selectedRunbook.category, selectedRunbook.document_title)
    : '';

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      
      {/* Top Status & Metrics Card */}
      <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-xl backdrop-blur-md transition-colors duration-200">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className={`px-3 py-1 rounded-full border text-xs font-semibold flex items-center space-x-1.5 ${urgency.bg}`}>
              <span className={`w-2 h-2 rounded-full ${urgency.dot}`} />
              <span>{urgency.label}</span>
            </div>

            <span className="text-xs font-mono font-medium px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Category: {result.category}
            </span>

            <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Tier: <strong className="text-slate-900 dark:text-white capitalize">{result.customer_tier}</strong>
            </span>
          </div>

          <div className="flex items-center space-x-4 text-xs font-mono text-slate-500 dark:text-slate-400">
            <div className="flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-sky-500 dark:text-sky-400" />
              <span>Confidence:</span>
              <span className="text-sky-600 dark:text-sky-300 font-bold">{(result.confidence_score * 100).toFixed(0)}%</span>
            </div>

            {result.total_latency_ms > 0 && (
              <div className="flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5 text-slate-400 dark:text-slate-400" />
                <span>Latency:</span>
                <span className="text-slate-700 dark:text-slate-200">{result.total_latency_ms.toFixed(0)}ms</span>
              </div>
            )}
          </div>
        </div>

        {/* Triage Summary Note */}
        {result.triage_notes && (
          <p className="mt-3 text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-950/40 p-3 rounded-xl border border-slate-200 dark:border-slate-800/80">
            <strong className="text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider text-[10px] block mb-1">Agent Assessment Summary</strong>
            {result.triage_notes}
          </p>
        )}

        {/* Security & Privacy Guardrails Status */}
        {result.security_verdict && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl border bg-slate-50 dark:bg-slate-950/60 border-slate-200 dark:border-slate-800">
            <div className="flex items-center space-x-2">
              {result.security_verdict === 'QUARANTINED' ? (
                <ShieldAlert className="w-4 h-4 text-rose-500 dark:text-rose-400 shrink-0" />
              ) : result.security_verdict === 'REDACTED' ? (
                <Shield className="w-4 h-4 text-amber-500 dark:text-amber-400 shrink-0" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-emerald-500 dark:text-emerald-400 shrink-0" />
              )}
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Security Guardrails:
              </span>
              <span
                className={`text-xs font-mono font-medium px-2 py-0.5 rounded-full border ${
                  result.security_verdict === 'QUARANTINED'
                    ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                    : result.security_verdict === 'REDACTED'
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                    : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                }`}
              >
                {result.security_verdict === 'QUARANTINED'
                  ? 'Input Quarantined (Adversarial Prompt Intercepted)'
                  : result.security_verdict === 'REDACTED'
                  ? `PII Shield Active (${result.pii_redacted_count} item(s) sanitized)`
                  : 'Passed (Clean Input, 0 PII)'}
              </span>
            </div>

            {result.security_details?.entities_found?.length > 0 && (
              <div className="flex items-center space-x-1 text-[11px] text-slate-500 dark:text-slate-400">
                <span>Sanitized:</span>
                <span className="font-mono text-amber-600 dark:text-amber-300">
                  {result.security_details.entities_found.join(', ')}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Left: Customer Reply & Internal Checklist */}
        <div className="space-y-6">

          {/* Suggested Customer Reply */}
          <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-xl backdrop-blur-md transition-colors duration-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
                <span>Recommended Customer Response</span>
              </h3>
              <button
                onClick={handleCopyReply}
                className="flex items-center space-x-1 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition"
              >
                {copiedReply ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                    <span className="text-emerald-600 dark:text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy Reply</span>
                  </>
                )}
              </button>
            </div>
            <div className="bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800/80 rounded-xl p-4 text-xs font-mono text-slate-800 dark:text-slate-200 whitespace-pre-line leading-relaxed max-h-72 overflow-y-auto">
              {result.suggested_reply}
            </div>
          </div>

          {/* Internal Engineering Action Checklist */}
          <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-xl backdrop-blur-md transition-colors duration-200">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2 mb-3">
              <Layers className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
              <span>Internal Remediation Checklist (Tier-2)</span>
            </h3>
            <ul className="space-y-2">
              {result.internal_action_plan?.map((step, idx) => (
                <li
                  key={idx}
                  onClick={() => toggleStep(idx)}
                  className={`flex items-start space-x-3 p-3 rounded-xl border text-xs cursor-pointer select-none transition ${
                    checkedSteps[idx]
                      ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-300 line-through'
                      : 'bg-slate-50 dark:bg-slate-950/40 border-slate-200 dark:border-slate-800/70 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/40'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={!!checkedSteps[idx]}
                    onChange={() => {}}
                    className="mt-0.5 rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-emerald-500 focus:ring-0 w-3.5 h-3.5"
                  />
                  <span className="leading-relaxed">{step}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right: Hybrid RAG Grounding & Multi-Agent Steps */}
        <div className="space-y-6">

          {/* Grounding Citations */}
          <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-xl backdrop-blur-md transition-colors duration-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-sky-500 dark:text-sky-400" />
                <span>Grounding Runbooks (Hybrid RAG)</span>
              </h3>
              <span className="text-[10px] text-slate-400 dark:text-slate-400">Click card for preview</span>
            </div>

            {result.grounding_citations?.length === 0 ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">No matching knowledge articles retrieved.</p>
            ) : (
              <div className="space-y-3">
                {result.grounding_citations.map((cite, idx) => {
                  const validUrl = resolveValidUrl(cite.source_url, cite.category, cite.document_title);
                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedRunbook(cite)}
                      className="bg-slate-50 dark:bg-slate-950/50 hover:bg-slate-100 dark:hover:bg-slate-850 border border-slate-200 dark:border-slate-800 hover:border-sky-400 dark:hover:border-sky-500/40 rounded-xl p-3.5 text-xs space-y-2 cursor-pointer transition group"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-slate-800 dark:text-slate-200 group-hover:text-sky-600 dark:group-hover:text-sky-300 transition flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-sky-500 dark:text-sky-400 shrink-0" />
                          <span>{cite.document_title}</span>
                        </span>
                        <span
                          title={`Raw RRF Score: ${cite.score.toFixed(4)} (Reciprocal Rank Fusion k=60)`}
                          className="font-mono text-[10px] text-sky-600 dark:text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20 shrink-0 cursor-help"
                        >
                          {formatRelevancePercentage(cite.score)}
                        </span>
                      </div>

                      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal line-clamp-2">
                        {cite.content_snippet}
                      </p>

                      {/* Action Bar on Citation Card */}
                      <div className="pt-1.5 border-t border-slate-200 dark:border-slate-800/80 flex items-center justify-between text-[11px]">
                        <span className="text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300 transition">
                          View full runbook &rarr;
                        </span>

                        <div className="flex items-center space-x-2">
                          {/* Copy URL button */}
                          <button
                            type="button"
                            onClick={(e) => handleCopyCardUrl(e, validUrl, idx)}
                            title="Copy documentation link"
                            className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-200 dark:hover:text-white dark:hover:bg-slate-800 transition"
                          >
                            {cardCopiedIdx === idx ? (
                              <Check className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                            ) : (
                              <LinkIcon className="w-3.5 h-3.5" />
                            )}
                          </button>

                          {/* Direct Open in New Tab Link */}
                          <a
                            href={validUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            title="Open documentation in new tab"
                            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-200/80 hover:bg-sky-500/15 text-slate-700 hover:text-sky-600 border border-slate-300 dark:bg-slate-800 dark:hover:bg-sky-500/20 dark:text-slate-300 dark:hover:text-sky-300 dark:border-slate-700 transition text-[10px]"
                          >
                            <span>Open tab</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Multi-Agent Orchestration Timeline */}
          {result.agent_steps?.length > 0 && (
            <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-xl backdrop-blur-md transition-colors duration-200">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2 mb-3">
                <GitBranch className="w-4 h-4 text-purple-500 dark:text-purple-400" />
                <span>Multi-Agent Reasoning Timeline</span>
              </h3>

              <div className="space-y-3">
                {result.agent_steps.map((step, idx) => (
                  <div key={idx} className="flex items-start space-x-3 text-xs">
                    <div className="w-6 h-6 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center font-mono text-[10px] text-purple-600 dark:text-purple-300 shrink-0 mt-0.5">
                      {idx + 1}
                    </div>
                    <div className="flex-1 bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800/80 rounded-xl p-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-slate-800 dark:text-slate-200">{step.agent_name}</span>
                        <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500">{step.duration_ms.toFixed(0)}ms</span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal">
                        {step.thought}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Enhanced Runbook Preview Modal */}
      {selectedRunbook && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 dark:bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            
            {/* Modal Header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center space-x-2 mb-1.5">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 font-bold">
                    {selectedRunbook.category} RUNBOOK
                  </span>
                  <span
                    title={`Raw RRF Score: ${selectedRunbook.score.toFixed(4)}`}
                    className="text-[10px] font-mono text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/80 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 cursor-help"
                  >
                    Relevance: <strong className="text-sky-600 dark:text-sky-400 font-bold">{formatRelevancePercentage(selectedRunbook.score)}</strong> (RRF: {selectedRunbook.score.toFixed(4)})
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {selectedRunbook.document_title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedRunbook(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-white dark:hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Source URL Banner */}
            <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 p-2.5 rounded-xl text-xs">
              <div className="flex items-center space-x-2 truncate mr-3">
                <LinkIcon className="w-3.5 h-3.5 text-sky-500 dark:text-sky-400 shrink-0" />
                <span className="font-mono text-slate-600 dark:text-slate-400 truncate text-[11px]">
                  {modalValidUrl}
                </span>
              </div>

              <div className="flex items-center space-x-1.5 shrink-0">
                {/* Copy URL */}
                <button
                  onClick={() => handleCopyModalUrl(modalValidUrl)}
                  className="flex items-center space-x-1 px-2 py-1 rounded bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-[11px] text-slate-700 dark:text-slate-300 transition"
                >
                  {copiedModalUrl ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500 dark:text-emerald-400" />
                      <span className="text-emerald-600 dark:text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy URL</span>
                    </>
                  )}
                </button>

                {/* Open in New Window/Tab */}
                <a
                  href={modalValidUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 px-2.5 py-1 rounded bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-300 border border-sky-500/30 transition text-[11px] font-semibold"
                >
                  <span>Open in New Tab</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {/* Runbook Text Content */}
            <div className="bg-slate-50 dark:bg-slate-950/90 border border-slate-200 dark:border-slate-800 rounded-xl p-4 text-xs font-mono text-slate-800 dark:text-slate-200 leading-relaxed max-h-80 overflow-y-auto whitespace-pre-line">
              {selectedRunbook.content_snippet}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => handleCopyModalText(selectedRunbook.content_snippet)}
                className="flex items-center space-x-1.5 text-xs text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:text-slate-400 dark:hover:text-white dark:bg-slate-800/80 dark:hover:bg-slate-800 transition"
              >
                {copiedModalText ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                    <span className="text-emerald-600 dark:text-emerald-400">Copied Runbook Text</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy Runbook Content</span>
                  </>
                )}
              </button>

              <button
                onClick={() => setSelectedRunbook(null)}
                className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-semibold text-slate-800 dark:text-white rounded-xl transition"
              >
                Close Runbook
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
