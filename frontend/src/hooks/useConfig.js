import { useState, useEffect, useCallback } from 'react';
import { fetchSystemConfig } from '../services/api';

export function useConfig() {
  const [config, setConfig] = useState({
    gemini_model: 'Loading...',
    embedding_model: 'Loading...',
    provider: 'Google Gemini',
    environment: 'development',
    status: 'checking',
    max_tickets_per_session: 10,
    session_expiry_days: 7,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadConfig = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await fetchSystemConfig();
      setConfig(data);
    } catch (err) {
      console.warn('Could not fetch backend config:', err);
      setError(err);
      setConfig((prev) => ({
        ...prev,
        gemini_model: 'gemini-2.5-flash (offline)',
        status: 'disconnected',
      }));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  return { config, isLoading, error, refreshConfig: loadConfig };
}
