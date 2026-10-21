import React from 'react';
import { RefreshCw, Sparkles, Sun, Moon } from 'lucide-react';

export default function Header({ config = {}, isLoading, onRefresh, theme = 'dark', onToggleTheme }) {

  return (
    <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/60 backdrop-blur-md sticky top-0 z-40 transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand / Logo */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 via-indigo-500 to-purple-500 p-[1.5px] shadow-lg shadow-sky-500/10">
            <div className="w-full h-full bg-slate-900 dark:bg-slate-950 rounded-[10px] flex items-center justify-center">
              <span className="font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white via-slate-100 to-slate-300 text-xl tracking-wider">
                S
              </span>
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">Sagent</span>
              <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20">
                Phase 1
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Autonomous Ticket Triage & Hybrid RAG</p>
          </div>
        </div>

        {/* Active Model Indicator, Theme Toggle & Refresh */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          
          {/* Active Model Indicator (Fetched from GET /api/v1/config) */}
          <div className="flex items-center space-x-2 bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/80 px-3 py-1.5 rounded-lg text-xs shadow-inner">
            <Sparkles className="w-3.5 h-3.5 text-sky-500 dark:text-sky-400" />
            <span className="text-slate-500 dark:text-slate-400">Model:</span>
            <span className="font-mono font-medium text-sky-600 dark:text-sky-300">
              {config.gemini_model || 'Detecting...'}
            </span>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={onToggleTheme}
            type="button"
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800 transition border border-slate-200 dark:border-transparent dark:hover:border-slate-700"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400 transition transform hover:rotate-45" />
            ) : (
              <Moon className="w-4 h-4 text-indigo-600 transition transform hover:-rotate-12" />
            )}
          </button>

          {/* Refresh config button */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            title="Refresh model config from backend"
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800 transition border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-sky-500 dark:text-sky-400' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
}
