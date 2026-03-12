/**
 * Session store — reactive user session state.
 */

import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';
import { getStoredSession, clearSession, type StoredSession } from '$lib/api/client';

function createSessionStore() {
	const initial = browser ? getStoredSession() : null;
	const { subscribe, set, update } = writable<StoredSession | null>(initial);

	return {
		subscribe,
		set(session: StoredSession | null) {
			set(session);
		},
		clear() {
			clearSession();
			set(null);
		},
		/** Re-read from localStorage (e.g. after login). */
		refresh() {
			const s = browser ? getStoredSession() : null;
			set(s);
		}
	};
}

export const session = createSessionStore();

export const isAuthenticated = derived(session, ($s) => $s !== null);

export const currentUser = derived(session, ($s) => $s?.user ?? null);

export const userRole = derived(session, ($s) => $s?.user?.role ?? null);
