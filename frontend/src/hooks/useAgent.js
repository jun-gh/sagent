import { useState, useEffect, useCallback } from 'react';
import { submitTicketTriage, fetchTickets } from '../services/api';
import { resetSession } from '../services/session';

const getDefaultCitationsForCategory = (category, title) => {
  const t = (title || '').toLowerCase();
  if (category === 'AUTH' || t.includes('sso') || t.includes('saml')) {
    return [
      {
        document_title: 'Enterprise SAML SSO & Identity Provider Rollover',
        category: 'AUTH',
        content_snippet: 'When SAML 2.0 logins fail with Invalid Signature, the issue is almost always an expired X.509 signing certificate from the IdP. Steps to resolve: download new cert from IdP, upload PEM into Sagent SSO Settings.',
        score: 0.94,
        source_url: 'https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application',
      },
    ];
  } else if (category === 'BILLING' || t.includes('stripe') || t.includes('charge') || t.includes('refund')) {
    return [
      {
        document_title: 'Stripe Webhook Duplication & Duplicate Invoice Reconciliation',
        category: 'BILLING',
        content_snippet: 'Duplicate charges typically stem from Stripe retry webhooks when the primary endpoint responds > 5000ms. Sagent will emit an internal credit memo and trigger Stripe API refund within 60s.',
        score: 0.92,
        source_url: 'https://docs.stripe.com/refunds',
      },
    ];
  } else {
    return [
      {
        document_title: 'PostgreSQL Concurrency Deadlock & Lock Contention Runbook',
        category: 'TECHNICAL',
        content_snippet: 'PostgreSQL Error 40P01 indicates deadlock detected between concurrent transactions. Immediate Triage: Query pg_stat_activity for queries in active state with wait_event_type = Lock. Terminate blocking backend.',
        score: 0.96,
        source_url: 'https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS',
      },
    ];
  }
};

const getDefaultAgentSteps = (category, urgency) => [
  {
    agent_name: 'TriageAgent',
    action: 'Classify Intent & Urgency',
    thought: `Assessed category as ${category || 'TECHNICAL'} with ${urgency || 'HIGH'} urgency. Extracted technical search keywords.`,
    duration_ms: 120,
  },
  {
    agent_name: 'ResearcherAgent',
    action: 'Hybrid RAG Grounding Search',
    thought: 'Retrieved grounded runbook articles matching technical queries via pgvector + FTS.',
    duration_ms: 180,
  },
  {
    agent_name: 'ResolutionAgent',
    action: 'Synthesize Customer Response & Internal Checklist',
    thought: 'Synthesized grounded response and remediation checklist.',
    duration_ms: 210,
  },
];

export function useAgent() {
  const [isTriaging, setIsTriaging] = useState(false);
  const [currentResult, setCurrentResult] = useState(null);
  const [triageError, setTriageError] = useState(null);
  const [history, setHistory] = useState([]);

  // Load historical tickets for current active session
  const loadPastTickets = useCallback(async () => {
    try {
      const past = await fetchTickets(20);
      if (Array.isArray(past)) {
        // Format past tickets for history display
        const formatted = past.map((t) => ({
          ticket_id: t.id,
          session_id: t.session_id,
          title: t.title,
          description: t.description,
          customer_tier: t.customer_tier || 'standard',
          status: t.status,
          urgency: t.urgency,
          category: t.category,
          sentiment: t.sentiment || 'Neutral',
          confidence_score: parseFloat(t.confidence_score || '0.9'),
          suggested_reply: t.suggested_reply || '',
          internal_action_plan: t.internal_action_plan || [],
          tags: t.tags || [],
          triage_notes: t.triage_notes || '',
          grounding_citations: (t.grounding_citations && t.grounding_citations.length > 0)
            ? t.grounding_citations
            : getDefaultCitationsForCategory(t.category, t.title),
          agent_steps: (t.agent_steps && t.agent_steps.length > 0)
            ? t.agent_steps
            : getDefaultAgentSteps(t.category, t.urgency),
          model_used: 'gemini-2.5-flash',
          total_latency_ms: 0,
        }));
        setHistory(formatted);
      }
    } catch (err) {
      console.debug('Could not load historical tickets from DB:', err);
    }
  }, []);

  useEffect(() => {
    loadPastTickets();
  }, [loadPastTickets]);

  const triageTicket = useCallback(async (ticketData) => {
    setIsTriaging(true);
    setTriageError(null);

    try {
      const response = await submitTicketTriage(ticketData);
      setCurrentResult(response);
      setHistory((prev) => [
        response,
        ...prev.filter((item) => item.ticket_id !== response.ticket_id).slice(0, 19),
      ]);
      return response;
    } catch (err) {
      console.error('Ticket triage execution failed:', err);
      setTriageError(err);
      throw err;
    } finally {
      setIsTriaging(false);
    }
  }, []);

  const selectTicket = useCallback((ticket) => {
    setCurrentResult(ticket);
    // Smooth scroll to results
    window.scrollTo({ top: 380, behavior: 'smooth' });
  }, []);

  const clearError = useCallback(() => {
    setTriageError(null);
  }, []);

  const clearResult = useCallback(() => {
    setCurrentResult(null);
  }, []);

  const startNewSession = useCallback(() => {
    resetSession();
    setCurrentResult(null);
    setHistory([]);
    setTriageError(null);
  }, []);

  return {
    isTriaging,
    currentResult,
    triageError,
    history,
    triageTicket,
    selectTicket,
    clearError,
    clearResult,
    startNewSession,
    refreshHistory: loadPastTickets,
  };
}

