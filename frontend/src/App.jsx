import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ErrorBanner from './components/ErrorBanner';
import TicketForm from './components/TicketForm';
import TriageResult from './components/TriageResult';
import KnowledgeBaseView from './components/KnowledgeBaseView';
import TelemetryModal from './components/TelemetryModal';
import { useConfig } from './hooks/useConfig';
import { useAgent } from './hooks/useAgent';
import { Inbox, Database, History, Sparkles, Terminal, ChevronRight } from 'lucide-react';

export default function App() {
  const { config, isLoading: isConfigLoading, error: configError, refreshConfig } = useConfig();
  const {
    isTriaging,
    currentResult,
    triageError,
    history,
    triageTicket,
    selectTicket,
    clearError,
    startNewSession,
  } = useAgent();

  const [activeTab, setActiveTab] = useState('triage'); // 'triage' | 'kb'
  const [showTelemetry, setShowTelemetry] = useState(false);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('sagent_theme') || 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      document.body.classList.add('dark');
    } else {
      root.classList.remove('dark');
      document.body.classList.remove('dark');
    }
    localStorage.setItem('sagent_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const activeError = triageError || configError;
  const maxTickets = config.max_tickets_per_session || 10;
  const expiryDays = config.session_expiry_days || 7;

  return (
    <div className={`min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white transition-colors duration-200 ${theme === 'dark' ? 'dark' : ''}`}>
      {/* Top Header with dynamic model badge, session tracker, and theme toggle */}
      <Header
        config={config}
        isLoading={isConfigLoading}
        onRefresh={refreshConfig}
        ticketCount={history.length}
        onNewSession={startNewSession}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenTelemetry={() => setShowTelemetry(true)}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        
        {/* Navigation Tabs */}
        <div className="flex items-center space-x-2 border-b border-slate-200 dark:border-slate-800 pb-3">
          <button
            onClick={() => setActiveTab('triage')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
              activeTab === 'triage'
                ? 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/30 shadow-lg shadow-sky-500/5'
                : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Inbox className="w-4 h-4" />
            <span>Ticket Triage</span>
          </button>

          <button
            onClick={() => setActiveTab('kb')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
              activeTab === 'kb'
                ? 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/30 shadow-lg shadow-sky-500/5'
                : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>Knowledge Base Search</span>
          </button>
        </div>

        {/* Global Error Alert Banner */}
        <ErrorBanner error={activeError} onDismiss={clearError} />

        {/* Tab 1: Ticket Triage View */}
        {activeTab === 'triage' && (
          <div className="space-y-8">
            <TicketForm
              onSubmit={triageTicket}
              isTriaging={isTriaging}
              ticketCount={history.length}
              maxTickets={maxTickets}
              sessionExpiryDays={expiryDays}
              onNewSession={startNewSession}
            />

            {/* Results Presentation */}
            {currentResult && <TriageResult result={currentResult} />}

            {/* History of triaged tickets */}
            {history.length > 0 && (
              <div className="bg-white dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm dark:shadow-lg transition-colors">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2 text-xs font-bold text-slate-800 dark:text-slate-300">
                    <History className="w-4 h-4 text-sky-500 dark:text-sky-400" />
                    <span>
                      Session Ticket History ({history.length}/{maxTickets} used &middot; {expiryDays}-day retention)
                    </span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="hidden sm:inline text-[10px] text-slate-400 dark:text-slate-500">Click any ticket to inspect resolution</span>
                    <button
                      onClick={startNewSession}
                      className="text-[11px] font-medium text-sky-600 dark:text-sky-400 hover:text-sky-500 dark:hover:text-sky-300 transition hover:underline"
                    >
                      Start New Session
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  {history.map((h, i) => {
                    const isSelected = currentResult?.ticket_id === h.ticket_id;
                    return (
                      <div
                        key={h.ticket_id || i}
                        onClick={() => selectTicket(h)}
                        className={`p-3 rounded-xl border text-xs flex items-center justify-between cursor-pointer transition ${
                          isSelected
                            ? 'bg-sky-50 border-sky-300 text-sky-950 dark:bg-sky-950/30 dark:border-sky-500/40 dark:text-white shadow-sm dark:shadow-inner'
                            : 'bg-slate-50 hover:bg-slate-100 border-slate-200 hover:border-slate-300 text-slate-700 dark:bg-slate-950/40 dark:hover:bg-slate-850 dark:border-slate-800/80 dark:hover:border-slate-700 dark:text-slate-300'
                        }`}
                      >
                        <div className="flex items-center space-x-3 truncate pr-4">
                          <span className="font-mono text-[10px] text-slate-500 bg-slate-200/80 dark:bg-slate-900 px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-800">
                            {h.ticket_id.slice(0, 8)}
                          </span>
                          <span className="font-medium truncate">{h.title}</span>
                        </div>
                        <div className="flex items-center space-x-2.5 shrink-0">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                            {h.urgency}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {h.category}
                          </span>
                          <ChevronRight className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Knowledge Base & Hybrid RAG Explorer */}
        {activeTab === 'kb' && <KnowledgeBaseView />}
      </main>

      {/* Modern Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800/80 bg-white/80 dark:bg-slate-950/80 py-4 text-center text-xs text-slate-500 transition-colors">
        <p className="flex items-center justify-center flex-wrap gap-x-2 gap-y-1">
          <span>Smart Autonomous Gateway for Enterprise Network Ticketing {new Date().getFullYear()}</span>
          <span>&middot;</span>
          <button
            type="button"
            onClick={() => setShowTelemetry(true)}
            className="inline-flex items-center space-x-1 hover:underline text-slate-500 hover:text-sky-600 dark:text-slate-400 dark:hover:text-sky-300 transition"
            title="Inspect Phase 3 operational metrics & latency percentiles"
          >
            <span>Model: </span>
            <span className="font-mono font-medium text-sky-600 dark:text-sky-300">
              {config.gemini_model || 'Detecting...'}
            </span>
          </button>
        </p>
      </footer>

      {/* Live System Telemetry & Ops Observability Modal */}
      <TelemetryModal
        isOpen={showTelemetry}
        onClose={() => setShowTelemetry(false)}
      />
    </div>
  );
}
