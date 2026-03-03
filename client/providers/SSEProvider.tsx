/**
 * SSEProvider — global Server-Sent Events connection that:
 *
 *  1. Connects to ``/api/v1/events`` with the user's JWT.
 *  2. Reconnects automatically on errors / network drops (exponential back-off).
 *  3. Disconnects when the app goes to background, reconnects on foreground.
 *  4. Dispatches incoming ``table_change`` events to React Query, either
 *     invalidating queries or patching the cache directly.
 *
 * Wrap your authenticated app tree with ``<SSEProvider>`` — it reads the
 * access token from ``tokenStorage`` so it stays in sync with the axios
 * interceptor refresh flow.
 */

import React, { createContext, useCallback, useContext, useEffect, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import EventSource from 'react-native-sse';
import NetInfo, { type NetInfoState } from '@react-native-community/netinfo';

// Custom SSE event names that the backend sends.
type SSECustomEvents = 'connected' | 'table_change';

import { API_BASE_URL, tokenStorage } from '@/services/api';
import { queryClient } from '@/providers/QueryProvider';

// ── Types ────────────────────────────────────────────────────────────────

export interface TableChangeEvent {
  table: string;
  op: 'INSERT' | 'UPDATE' | 'DELETE';
  id: string;
  user_id: string | null;
  ts: number;
}

interface SSEContextValue {
  /** True once the SSE stream has received the ``connected`` event. */
  isConnected: boolean;
}

const SSEContext = createContext<SSEContextValue>({ isConnected: false });

export const useSSE = () => useContext(SSEContext);

// ── Query-key mapping ────────────────────────────────────────────────────
//
// Maps a PG table name to React Query query-key prefixes that should be
// invalidated when that table changes.  Add entries here as you add new
// queries throughout the app.
//
// For high-frequency tables you can instead do an optimistic ``setQueryData``
// inside ``handleTableChange`` below.

const TABLE_QUERY_KEY_MAP: Record<string, string[][]> = {
  documents:           [['documents']],
  questions:           [['questions'], ['sessions']],
  generation_sessions: [['sessions'], ['questions']],
  subjects:            [['subjects']],
  topics:              [['topics'], ['subjects']],
  rubrics:             [['rubrics']],
  tests:               [['tests']],
  test_questions:      [['tests']],
  test_submissions:    [['tests'], ['submissions']],
  enrollments:         [['enrollments'], ['learn']],
  student_progress:    [['progress'], ['learn'], ['leaderboard']],
};

// ── Event dispatcher ─────────────────────────────────────────────────────

function handleTableChange(event: TableChangeEvent) {
  const queryKeys = TABLE_QUERY_KEY_MAP[event.table];

  if (!queryKeys) {
    // Unknown table — nothing to invalidate.
    return;
  }

  // For DELETE operations we always invalidate so list queries drop the item.
  // For INSERT/UPDATE we can choose between invalidation (simple, extra
  // round-trip) or optimistic cache update (no round-trip but more code).
  //
  // The default strategy here is *smart invalidation*: mark matching queries
  // as stale and let React Query refetch only the ones that are currently
  // being observed (mounted on screen).  This avoids unnecessary fetches for
  // screens the user isn't looking at.

  for (const key of queryKeys) {
    queryClient.invalidateQueries({
      queryKey: key,
      // ``refetchType: 'active'`` means only queries with active observers
      // (i.e. mounted components) are refetched immediately.  Inactive
      // queries are marked stale and will refetch on next mount.
      refetchType: 'active',
    });
  }

  // ── Optimistic cache patches (optional, per-table) ──────────────────
  //
  // Example: remove a deleted item from a list cache instantly:
  //
  if (event.op === 'DELETE') {
    for (const key of queryKeys) {
      queryClient.setQueriesData<any[]>(
        { queryKey: key },
        (oldData) => {
          if (!Array.isArray(oldData)) return oldData;
          return oldData.filter((item: any) => item.id !== event.id);
        },
      );
    }
  }
}

// ── Provider component ───────────────────────────────────────────────────

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export function SSEProvider({ children }: { children: React.ReactNode }) {
  const esRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isConnected, setIsConnected] = React.useState(false);
  const mountedRef = useRef(true);
  const appStateRef = useRef<AppStateStatus>(AppState.currentState);

  // ── Connect / disconnect ──────────────────────────────────────────────

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(async () => {
    // Don't connect if already connected or unmounted
    if (esRef.current || !mountedRef.current) return;

    const token = await tokenStorage.getAccessToken();
    if (!token) {
      // No token → user is not authenticated, skip.
      return;
    }

    const url = `${API_BASE_URL}/events`;

    const es = new EventSource<SSECustomEvents>(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      // Polyfill option — keep the connection open
      pollingInterval: 0,
    });

    esRef.current = es;

    // ── SSE event handlers ────────────────────────────────────────────

    es.addEventListener('connected', (_msg: any) => {
      console.log('[SSE] Connected');
      setIsConnected(true);
      backoffRef.current = INITIAL_BACKOFF_MS; // reset back-off on success
    });

    es.addEventListener('table_change', (msg: any) => {
      if (!msg?.data) return;
      try {
        const event: TableChangeEvent = JSON.parse(msg.data);
        handleTableChange(event);
      } catch (err) {
        console.warn('[SSE] Failed to parse table_change:', err);
      }
    });

    es.addEventListener('error', (err: any) => {
      console.warn('[SSE] Error, will reconnect:', err);
      disconnect();
      scheduleReconnect();
    });

    es.addEventListener('close', () => {
      console.log('[SSE] Connection closed');
      disconnect();
      scheduleReconnect();
    });
  }, [disconnect]);

  // ── Reconnect with exponential back-off ───────────────────────────────

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectTimerRef.current) return; // already scheduled

    const delay = backoffRef.current;
    console.log(`[SSE] Reconnecting in ${delay}ms …`);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      connect();
    }, delay);
  }, [connect]);

  // ── AppState: disconnect on background, reconnect on foreground ───────

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState) => {
      const prev = appStateRef.current;
      appStateRef.current = nextState;

      if (nextState === 'active' && prev !== 'active') {
        // Came to foreground → reconnect
        console.log('[SSE] App foregrounded — reconnecting');
        connect();
      } else if (nextState.match(/inactive|background/) && prev === 'active') {
        // Going to background → tear down to save battery
        console.log('[SSE] App backgrounded — disconnecting');
        disconnect();
      }
    });
    return () => subscription.remove();
  }, [connect, disconnect]);

  // ── Network state: reconnect when connectivity is restored ────────────

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      if (state.isConnected && !esRef.current && mountedRef.current) {
        console.log('[SSE] Network restored — reconnecting');
        connect();
      }
    });
    return () => unsubscribe();
  }, [connect]);

  // ── Mount / unmount ───────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <SSEContext.Provider value={{ isConnected }}>
      {children}
    </SSEContext.Provider>
  );
}
