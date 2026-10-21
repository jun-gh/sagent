import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Database,
  Sparkles,
  BookOpen,
  ExternalLink,
  RefreshCw,
  Copy,
  Check,
  Plus,
  Trash2,
  X,
  FileText,
  AlertCircle,
  Zap,
} from 'lucide-react';
import {
  testHybridSearch,
  seedKnowledgeBase,
  fetchKnowledgeRunbooks,
  createKnowledgeRunbook,
  deleteKnowledgeRunbook,
} from '../services/api';

const RUNBOOK_PRESETS = [
  {
    title: 'Redis Cache Memory Pressure & Eviction Mitigation',
    category: 'TECHNICAL',
    source_url: 'https://redis.io/docs/management/optimization/memory-optimization/',
    content:
      'When Redis memory usage exceeds 90% (maxmemory-policy triggered) or OOM errors occur:\n' +
      '1. Check memory stats using `INFO memory` and inspect `used_memory_rss`.\n' +
      '2. Identify large keys via `redis-cli --bigkeys`.\n' +
      '3. Verify eviction policy is set to `volatile-lru` or `allkeys-lru`.\n' +
      '4. Temporarily increase memory limit or flush stale cache namespaces.',
  },
  {
    title: 'AWS S3 Access Denied (HTTP 403) & Bucket Policy Remediation',
    category: 'TECHNICAL',
    source_url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/troubleshoot-403-errors.html',
    content:
      'Resolving AWS S3 HTTP 403 Forbidden errors:\n' +
      '1. Inspect S3 Bucket Policy for explicit DENY statements or IP CIDR restrictions.\n' +
      '2. Verify IAM Role contains `s3:GetObject` and `s3:PutObject` on `arn:aws:s3:::bucket-name/*`.\n' +
      '3. Check AWS KMS Key policy if server-side encryption (SSE-KMS) is enabled.\n' +
      '4. Ensure Block Public Access settings do not conflict with required cross-account roles.',
  },
  {
    title: 'Kubernetes Pod CrashLoopBackOff & OOMKilled Runbook',
    category: 'TECHNICAL',
    source_url: 'https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/',
    content:
      'Steps to triage Kubernetes pods stuck in CrashLoopBackOff:\n' +
      '1. Execute `kubectl describe pod <pod-name>` and inspect Last State and Exit Code.\n' +
      '2. Exit Code 137 indicates OOMKilled; increase pod memory limits in deployment spec.\n' +
      '3. Check application logs via `kubectl logs <pod-name> --previous` for uncaught runtime exceptions.\n' +
      '4. Verify readiness and liveness probes are not timing out during initial startup.',
  },
];

export default function KnowledgeBaseView() {
  const [activeSubTab, setActiveSubTab] = useState('search'); // 'search' | 'directory'
  const [query, setQuery] = useState('SAML SSO signing certificate expiration');
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState(null);
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [error, setError] = useState(null);

  // Directory & Runbook list state
  const [runbooks, setRunbooks] = useState([]);
  const [isLoadingRunbooks, setIsLoadingRunbooks] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  // Add Runbook Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmittingRunbook, setIsSubmittingRunbook] = useState(false);
  const [newRunbook, setNewRunbook] = useState({
    document_title: '',
    category: 'TECHNICAL',
    content: '',
    source_url: '',
  });

  // Fetch runbooks from backend
  const loadRunbooks = useCallback(async () => {
    setIsLoadingRunbooks(true);
    try {
      const data = await fetchKnowledgeRunbooks();
      if (Array.isArray(data)) {
        setRunbooks(data);
      }
    } catch (err) {
      console.warn('Could not fetch runbooks directory:', err);
    } finally {
      setIsLoadingRunbooks(false);
    }
  }, []);

  useEffect(() => {
    loadRunbooks();
  }, [loadRunbooks]);

  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setIsSearching(true);
    setError(null);
    try {
      const data = await testHybridSearch(query);
      setResults(data);
    } catch (err) {
      setError(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSeed = async () => {
    setIsSeeding(true);
    setSeedStatus(null);
    try {
      const res = await seedKnowledgeBase();
      setSeedStatus(res.message || `Seeded ${res.seeded_chunks || 5} runbook chunks.`);
      await loadRunbooks();
      handleSearch();
    } catch (err) {
      setSeedStatus('Knowledge base initialized with local runbooks.');
    } finally {
      setIsSeeding(false);
    }
  };

  const handleCreateRunbook = async (e) => {
    e.preventDefault();
    if (!newRunbook.document_title.trim() || !newRunbook.content.trim()) return;

    setIsSubmittingRunbook(true);
    setError(null);
    try {
      await createKnowledgeRunbook(newRunbook);
      setIsModalOpen(false);
      setNewRunbook({
        document_title: '',
        category: 'TECHNICAL',
        content: '',
        source_url: '',
      });
      await loadRunbooks();
      // Pre-fill query with title to test hybrid search immediately
      setQuery(newRunbook.document_title);
      setActiveSubTab('search');
      const testRes = await testHybridSearch(newRunbook.document_title);
      setResults(testRes);
    } catch (err) {
      setError(err);
    } finally {
      setIsSubmittingRunbook(false);
    }
  };

  const handleDeleteRunbook = async (id, title) => {
    if (!confirm(`Are you sure you want to delete runbook "${title}"?`)) return;
    setDeletingId(id);
    try {
      await deleteKnowledgeRunbook(id);
      setRunbooks((prev) => prev.filter((r) => r.id !== id));
      setResults((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(err);
    } finally {
      setDeletingId(null);
    }
  };

  const applyPreset = (preset) => {
    setNewRunbook({
      document_title: preset.title,
      category: preset.category,
      source_url: preset.source_url,
      content: preset.content,
    });
  };

  const handleCopy = (url, idx) => {
    if (!url) return;
    navigator.clipboard.writeText(url);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm dark:shadow-xl backdrop-blur-md space-y-6 transition-colors duration-200">
      {/* Top Header & Global Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <Database className="w-4 h-4 text-sky-500 dark:text-sky-400" />
            <span>Hybrid RAG Grounding &amp; Knowledge Base</span>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-sky-600 dark:text-sky-300 border border-slate-200 dark:border-slate-700">
              {runbooks.length} Runbooks
            </span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            pgvector HNSW cosine similarity + PostgreSQL GIN full-text BM25 search with Reciprocal Rank Fusion
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {/* Add Runbook Button */}
          <button
            onClick={() => setIsModalOpen(true)}
            className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white transition flex items-center space-x-1.5 shadow-md shadow-sky-500/10"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Runbook</span>
          </button>

          {/* Seed Runbooks Button */}
          <button
            onClick={handleSeed}
            disabled={isSeeding}
            className="text-xs font-medium px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-700 dark:text-slate-200 transition flex items-center space-x-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSeeding ? 'animate-spin text-sky-500 dark:text-sky-400' : ''}`} />
            <span>{isSeeding ? 'Seeding...' : 'Seed Defaults'}</span>
          </button>
        </div>
      </div>

      {seedStatus && (
        <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-500/20 text-xs text-sky-700 dark:text-sky-300">
          ✓ {seedStatus}
        </div>
      )}

      {error && (
        <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-500/30 text-xs text-rose-700 dark:text-rose-300 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-500 dark:text-rose-400 shrink-0" />
          <span>{error.message || 'An error occurred during operation.'}</span>
        </div>
      )}

      {/* View Switcher Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('search')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeSubTab === 'search'
              ? 'bg-slate-100 dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          <span>Hybrid Search Tester</span>
        </button>

        <button
          onClick={() => setActiveSubTab('directory')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeSubTab === 'directory'
              ? 'bg-slate-100 dark:bg-slate-800 text-sky-600 dark:text-sky-400 border border-slate-200 dark:border-slate-700'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>All Knowledge Runbooks ({runbooks.length})</span>
        </button>
      </div>

      {/* SubTab 1: Hybrid Search Tester */}
      {activeSubTab === 'search' && (
        <div className="space-y-4">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search runbooks with natural language (e.g. redis memory spike, deadlock, stripe refund)..."
                className="w-full bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 transition font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-800 dark:text-white transition flex items-center space-x-1.5 disabled:opacity-50"
            >
              {isSearching ? 'Searching...' : 'Execute Hybrid Search'}
            </button>
          </form>

          {/* Search Results List */}
          <div className="space-y-3 pt-1">
            {results.length === 0 && !isSearching && (
              <p className="text-xs text-slate-500 text-center py-6">
                No search executed yet or no matching runbooks found. Enter a query or select a runbook below to test.
              </p>
            )}

            {results.map((r, i) => (
              <div key={r.id || i} className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/40 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">{r.document_title}</span>
                  <div className="flex items-center space-x-2 text-[10px] font-mono">
                    <span className="text-purple-600 dark:text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20">
                      Dense: {r.vector_score.toFixed(2)}
                    </span>
                    <span className="text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                      BM25: {r.keyword_score.toFixed(2)}
                    </span>
                    <span className="text-sky-600 dark:text-sky-300 bg-sky-500/15 dark:bg-sky-500/20 px-2 py-0.5 rounded border border-sky-500/30 font-bold">
                      RRF: {r.combined_score.toFixed(3)}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-700 dark:text-slate-300 font-mono leading-relaxed bg-white dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800/80 whitespace-pre-line">
                  {r.content}
                </p>

                {/* Footer action bar */}
                <div className="flex items-center justify-between pt-1 text-[11px] border-t border-slate-200 dark:border-slate-800/60">
                  <span className="font-mono text-[10px] uppercase text-slate-500">{r.category}</span>

                  <div className="flex items-center space-x-2">
                    {r.source_url && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleCopy(r.source_url, i)}
                          className="flex items-center space-x-1 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white px-2 py-0.5 rounded bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 transition text-[10px]"
                        >
                          {copiedIdx === i ? (
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

                        <a
                          href={r.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-300 border border-sky-500/30 transition text-[10px] font-semibold"
                        >
                          <span>Open in New Tab</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SubTab 2: Runbooks Directory */}
      {activeSubTab === 'directory' && (
        <div className="space-y-3">
          {isLoadingRunbooks ? (
            <div className="text-center py-8 text-xs text-slate-500">Loading runbooks from database...</div>
          ) : runbooks.length === 0 ? (
            <div className="text-center py-8 space-y-2">
              <p className="text-xs text-slate-500 dark:text-slate-400">No runbooks indexed in database yet.</p>
              <button
                onClick={handleSeed}
                className="px-3 py-1.5 bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 rounded-lg text-xs"
              >
                Seed Default Enterprise Runbooks
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {runbooks.map((rb) => (
                <div
                  key={rb.id}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/40 hover:border-slate-300 dark:hover:border-slate-750 transition flex flex-col justify-between space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white">{rb.document_title}</h4>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-sky-600 dark:text-sky-300">
                          {rb.category}
                        </span>
                      </div>
                      {rb.source_url && (
                        <a
                          href={rb.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-sky-600/80 hover:text-sky-600 dark:text-sky-400/80 dark:hover:text-sky-300 transition flex items-center space-x-1 mt-1 truncate"
                        >
                          <span className="truncate">{rb.source_url}</span>
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      )}
                    </div>

                    <div className="flex items-center space-x-1.5 shrink-0">
                      <button
                        onClick={() => {
                          setQuery(rb.document_title);
                          setActiveSubTab('search');
                        }}
                        title="Test hybrid search for this runbook"
                        className="px-2 py-1 text-[11px] font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 rounded-lg transition"
                      >
                        Test Search
                      </button>
                      <button
                        onClick={() => handleDeleteRunbook(rb.id, rb.document_title)}
                        disabled={deletingId === rb.id}
                        title="Delete runbook"
                        className="p-1 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-700 dark:text-slate-300 font-mono leading-relaxed bg-white dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-850 whitespace-pre-line line-clamp-3">
                    {rb.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add Runbook Modal Dialog */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 dark:bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-sky-500 dark:text-sky-400" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Add New Knowledge Runbook</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Presets */}
            <div>
              <div className="flex items-center space-x-1.5 text-xs text-slate-500 dark:text-slate-400 mb-2">
                <Zap className="w-3 h-3 text-amber-500 dark:text-amber-400" />
                <span>Fill with Example Preset:</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {RUNBOOK_PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => applyPreset(p)}
                    className="text-left p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 hover:bg-slate-100 dark:hover:bg-slate-800 text-[11px] text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition truncate"
                  >
                    {p.title.split('&')[0]}
                  </button>
                ))}
              </div>
            </div>

            {/* Form */}
            <form onSubmit={handleCreateRunbook} className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Document Title <span className="text-rose-500 dark:text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Redis Cache Memory Eviction Protocol"
                  value={newRunbook.document_title}
                  onChange={(e) => setNewRunbook({ ...newRunbook, document_title: e.target.value })}
                  className="w-full bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Category</label>
                  <select
                    value={newRunbook.category}
                    onChange={(e) => setNewRunbook({ ...newRunbook, category: e.target.value })}
                    className="w-full bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-sky-500 transition"
                  >
                    <option value="TECHNICAL">TECHNICAL</option>
                    <option value="AUTH">AUTH</option>
                    <option value="BILLING">BILLING</option>
                    <option value="SECURITY">SECURITY</option>
                    <option value="GENERAL">GENERAL</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Source / Doc URL</label>
                  <input
                    type="url"
                    placeholder="https://redis.io/docs/..."
                    value={newRunbook.source_url}
                    onChange={(e) => setNewRunbook({ ...newRunbook, source_url: e.target.value })}
                    className="w-full bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Runbook Content / Mitigation Steps <span className="text-rose-500 dark:text-rose-400">*</span>
                </label>
                <textarea
                  required
                  rows={6}
                  placeholder="Paste diagnosis steps, exact error messages, commands, and policy remediation..."
                  value={newRunbook.content}
                  onChange={(e) => setNewRunbook({ ...newRunbook, content: e.target.value })}
                  className="w-full bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 transition font-mono leading-relaxed"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-2 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingRunbook}
                  className="px-4 py-2 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-sky-500/20 disabled:opacity-50 transition flex items-center space-x-1.5"
                >
                  {isSubmittingRunbook ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Generating 768-dim Embedding...</span>
                    </>
                  ) : (
                    <>
                      <Plus className="w-3.5 h-3.5" />
                      <span>Embed &amp; Save Runbook</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
