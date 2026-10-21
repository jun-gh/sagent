import axios from 'axios';
import { getSessionId } from './session';

// Base Axios instance
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 45000, // 45 seconds for LLM triage calls
});

// Request interceptor to attach active anonymous session ID and API key
apiClient.interceptors.request.use((config) => {
  const sessionId = getSessionId();
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId;
  }

  // Attach API key if configured via Vite environment variable, localStorage, or default master key
  const apiKey =
    import.meta.env.VITE_SAGENT_API_KEY ||
    (typeof window !== 'undefined' ? localStorage.getItem('sagent_api_key') : null) ||
    'sagent-sec-key-2026';

  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }

  return config;
});

// Response interceptor to normalize error handling
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    let normalizedError = {
      code: 'NETWORK_ERROR',
      message: 'Unable to connect to Sagent backend server. Please check your connection.',
      retries_attempted: 0,
      details: null,
      status: error.response?.status || 0,
    };

    if (error.response?.data?.error) {
      // Backend returned structured typed error envelope
      const beError = error.response.data.error;
      normalizedError = {
        code: beError.code || 'API_ERROR',
        message: beError.message || 'An error occurred during request processing.',
        retries_attempted: beError.retries_attempted || 0,
        details: beError.details || null,
        status: error.response.status,
      };
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      normalizedError = {
        code: 'TIMEOUT_ERROR',
        message: 'The AI triage engine took too long to respond. The request has timed out.',
        retries_attempted: 0,
        details: null,
        status: 408,
      };
    } else if (error.response?.data?.detail) {
      normalizedError = {
        code: 'BAD_REQUEST',
        message: String(error.response.data.detail),
        retries_attempted: 0,
        details: null,
        status: error.response.status,
      };
    }

    return Promise.reject(normalizedError);
  }
);

export const fetchSystemConfig = async () => {
  return apiClient.get('/api/v1/config');
};

export const submitTicketTriage = async (ticketData) => {
  return apiClient.post('/api/v1/tickets/triage', ticketData);
};

export const fetchTickets = async (limit = 20) => {
  return apiClient.get(`/api/v1/tickets?limit=${limit}`);
};

export const testHybridSearch = async (query, category = null, top_k = 4) => {
  return apiClient.post('/api/v1/kb/search', {
    query,
    category,
    top_k,
    dense_weight: 0.6,
    keyword_weight: 0.4,
  });
};

export const seedKnowledgeBase = async () => {
  return apiClient.post('/api/v1/kb/seed');
};

export const fetchKnowledgeRunbooks = async (category = null) => {
  const url = category ? `/api/v1/kb?category=${encodeURIComponent(category)}` : '/api/v1/kb';
  return apiClient.get(url);
};

export const createKnowledgeRunbook = async (runbookData) => {
  return apiClient.post('/api/v1/kb', runbookData);
};

export const deleteKnowledgeRunbook = async (chunkId) => {
  return apiClient.delete(`/api/v1/kb/${chunkId}`);
};

export default apiClient;

