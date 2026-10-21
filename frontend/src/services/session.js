// Anonymous session management service for Sagent
const SESSION_ID_KEY = 'sagent_session_id';
const SESSION_CREATED_AT_KEY = 'sagent_session_created_at';

/**
 * Generate a UUID v4
 */
function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Check if the active session has exceeded its expiry window in days
 */
export function isSessionExpired(expiryDays = 7) {
  const createdAtStr = localStorage.getItem(SESSION_CREATED_AT_KEY);
  if (!createdAtStr) return true;

  const createdAt = parseInt(createdAtStr, 10);
  if (isNaN(createdAt)) return true;

  const maxAgeMs = expiryDays * 24 * 60 * 60 * 1000;
  return Date.now() - createdAt > maxAgeMs;
}

/**
 * Retrieve or automatically initialize a valid session ID
 */
export function getSessionId(expiryDays = 7) {
  let sessionId = localStorage.getItem(SESSION_ID_KEY);

  if (!sessionId || isSessionExpired(expiryDays)) {
    return resetSession();
  }

  return sessionId;
}

/**
 * Reset session and initialize a fresh UUID
 */
export function resetSession() {
  const newSessionId = generateUUID();
  localStorage.setItem(SESSION_ID_KEY, newSessionId);
  localStorage.setItem(SESSION_CREATED_AT_KEY, Date.now().toString());
  return newSessionId;
}

/**
 * Get timestamp when session was initialized
 */
export function getSessionCreatedAt() {
  const ts = localStorage.getItem(SESSION_CREATED_AT_KEY);
  return ts ? new Date(parseInt(ts, 10)) : new Date();
}
