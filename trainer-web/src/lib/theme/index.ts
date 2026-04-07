/**
 * Theme store — manages global theme selection and applies CSS variables.
 * Persists choice to localStorage under `qgen-trainer-theme`.
 */

import { writable, derived, get } from 'svelte/store';
import { themes, themeNamesStore, builtInThemeNames, registerCustomThemes, type ThemeName, type ThemeConfig } from './themes';
import { browser } from '$app/environment';
import { apiUrl, getStoredSession, apiFetch } from '$lib/api/client';

const STORAGE_KEY = 'qgen-trainer-theme';
const COLOR_MODE_STORAGE_KEY = 'qgen-trainer-color-mode';
export type ColorMode = 'light' | 'dark';

/** Store for custom themes list */
export const customThemes = writable<ThemeConfig[]>([]);

/** Debounce timer for saving preferences */
let savePreferencesTimeout: ReturnType<typeof setTimeout> | null = null;

function getInitialTheme(): ThemeName {
	if (browser) {
		const stored = localStorage.getItem(STORAGE_KEY);
		// Check built-in themes first, custom themes loaded later
		if (stored && (builtInThemeNames.includes(stored as ThemeName) || themes[stored as ThemeName])) {
			return stored as ThemeName;
		}
	}
	return 'fire';
}

function getInitialColorMode(): ColorMode {
	if (browser) {
		const stored = localStorage.getItem(COLOR_MODE_STORAGE_KEY);
		if (stored === 'light' || stored === 'dark') {
			return stored;
		}
	}

	return 'light';
}

export const currentThemeName = writable<ThemeName>(getInitialTheme());
export const currentColorMode = writable<ColorMode>(getInitialColorMode());

export const currentTheme = derived(currentThemeName, ($name) => themes[$name]);

/** Apply CSS custom properties to :root */
function applyTheme(config: ThemeConfig, mode: ColorMode) {
	if (!browser) return;
	const root = document.documentElement;
	const isDark = mode === 'dark';

	const resolvedTextPrimary = isDark ? '#f2eadb' : config.textPrimary;
	const resolvedTextSecondary = isDark ? 'rgba(235, 225, 207, 0.78)' : config.textSecondary;
	const resolvedGlassBg = isDark ? 'rgba(38, 41, 48, 0.74)' : config.glassBg;
	const resolvedGlassBorder = isDark ? 'rgba(108, 113, 124, 0.54)' : config.glassBorder;
	const resolvedNavGlass = isDark ? 'rgba(34, 37, 44, 0.78)' : config.navGlass;
	const resolvedBorder = isDark ? 'rgba(255,255,255,0.22)' : config.border;
	const resolvedInputBg = isDark ? 'rgba(30, 33, 39, 0.86)' : 'rgba(255, 255, 255, 0.08)';
	const resolvedMobileFrostGradient = isDark
		? 'linear-gradient(180deg, rgba(36, 39, 46, 0.9) 0%, rgba(34, 37, 44, 0.86) 38%, rgba(31, 34, 40, 0.83) 100%)'
		: 'linear-gradient(180deg, rgba(255, 255, 255, 0.62) 0%, rgba(255, 255, 255, 0.56) 38%, rgba(255, 255, 255, 0.52) 100%)';
	const resolvedMobileGlassBg = isDark ? 'rgba(35, 38, 45, 0.72)' : 'rgba(255, 255, 255, 0.08)';
	const resolvedMobileGlassBgHeavy = isDark ? 'rgba(40, 43, 50, 0.8)' : 'rgba(255, 255, 255, 0.12)';
	const resolvedMobileInputBg = isDark ? 'rgba(30, 33, 39, 0.84)' : 'rgba(255, 255, 255, 0.06)';
	const resolvedModalSurface = isDark
		? 'linear-gradient(155deg, rgba(25, 28, 35, 0.96) 0%, rgba(var(--theme-primary-rgb), 0.16) 48%, rgba(20, 24, 31, 0.95) 100%)'
		: 'linear-gradient(155deg, rgba(12, 18, 30, 0.9) 0%, rgba(var(--theme-primary-rgb), 0.14) 48%, rgba(10, 18, 32, 0.92) 100%)';

	root.style.setProperty('--theme-bg', config.bg);
	root.style.setProperty('--theme-bg-color', config.bgColor);
	root.style.setProperty('--theme-bg-image', `url(${config.bgImage})`);
	root.style.setProperty('--theme-wallpaper-overlay', config.wallpaperOverlay);
	root.style.setProperty('--theme-primary', config.primary);
	root.style.setProperty('--theme-primary-hover', config.primaryHover);
	root.style.setProperty('--theme-accent-gradient', config.accentGradient);
	root.style.setProperty('--theme-primary-rgb', config.primaryRgb);
	root.style.setProperty('--theme-text', resolvedTextPrimary);
	root.style.setProperty('--theme-text-muted', resolvedTextSecondary);
	root.style.setProperty('--theme-text-primary', resolvedTextPrimary);
	root.style.setProperty('--theme-text-secondary', resolvedTextSecondary);
	root.style.setProperty('--theme-glass-bg', resolvedGlassBg);
	root.style.setProperty('--theme-glass-border', resolvedGlassBorder);
	root.style.setProperty('--theme-nav-glass', resolvedNavGlass);
	root.style.setProperty('--theme-border', resolvedBorder);
	root.style.setProperty('--theme-input-bg', resolvedInputBg);
	root.style.setProperty('--theme-mobile-frost-gradient', resolvedMobileFrostGradient);
	root.style.setProperty('--theme-mobile-glass-bg', resolvedMobileGlassBg);
	root.style.setProperty('--theme-mobile-glass-bg-heavy', resolvedMobileGlassBgHeavy);
	root.style.setProperty('--theme-mobile-input-bg', resolvedMobileInputBg);
	root.style.setProperty('--theme-modal-surface', resolvedModalSurface);
	root.style.setProperty('--theme-glow', config.glow);
	root.setAttribute('data-theme', config.name);
	root.setAttribute('data-color-mode', mode);
}

/** Set a new theme by name. */
export function setTheme(name: ThemeName) {
	const theme = themes[name];
	if (!theme) {
		console.warn(`Theme "${name}" not found, falling back to fire`);
		name = 'fire';
	}
	currentThemeName.set(name);
	if (browser) {
		localStorage.setItem(STORAGE_KEY, name);
	}
	applyTheme(themes[name], get(currentColorMode));
	savePreferencesToBackend();
}

/** Set global color mode. */
export function setColorMode(mode: ColorMode) {
	currentColorMode.set(mode);
	if (browser) {
		localStorage.setItem(COLOR_MODE_STORAGE_KEY, mode);
	}
	const themeName = get(currentThemeName);
	applyTheme(themes[themeName], mode);
	savePreferencesToBackend();
}

/** Toggle color mode light <-> dark. */
export function toggleColorMode() {
	const current = get(currentColorMode);
	setColorMode(current === 'dark' ? 'light' : 'dark');
}

/** Cycle to the next theme in order. */
export function cycleTheme() {
	currentThemeName.update((current) => {
		const names = get(themeNamesStore);
		const idx = names.indexOf(current);
		const next = names[(idx + 1) % names.length];
		if (browser) localStorage.setItem(STORAGE_KEY, next);
		applyTheme(themes[next], get(currentColorMode));
		return next;
	});
}

// ==================== ZEN MODE ====================
const ZEN_MODE_STORAGE_KEY = 'qgen-trainer-zen-mode';

function getInitialZenMode(): boolean {
	if (browser) {
		const stored = localStorage.getItem(ZEN_MODE_STORAGE_KEY);
		return stored === 'true';
	}
	return false;
}

export const zenMode = writable<boolean>(getInitialZenMode());

function applyZenMode(enabled: boolean) {
	if (!browser) return;
	const root = document.documentElement;
	if (enabled) {
		root.setAttribute('data-zen-mode', 'true');
	} else {
		root.removeAttribute('data-zen-mode');
	}
}

/** Toggle zen mode on/off */
export function toggleZenMode() {
	zenMode.update((current) => {
		const next = !current;
		if (browser) localStorage.setItem(ZEN_MODE_STORAGE_KEY, String(next));
		applyZenMode(next);
		savePreferencesToBackend();
		return next;
	});
}

/** Set zen mode explicitly */
export function setZenMode(enabled: boolean) {
	zenMode.set(enabled);
	if (browser) localStorage.setItem(ZEN_MODE_STORAGE_KEY, String(enabled));
	applyZenMode(enabled);
	savePreferencesToBackend();
}

/** Save preferences to backend (debounced) */
function savePreferencesToBackend() {
	if (!browser) return;
	const session = getStoredSession();
	if (!session?.access_token) return;

	if (savePreferencesTimeout) {
		clearTimeout(savePreferencesTimeout);
	}

	savePreferencesTimeout = setTimeout(async () => {
		try {
			await apiFetch('/settings/preferences', {
				method: 'PUT',
				body: JSON.stringify({
					theme: get(currentThemeName),
					color_mode: get(currentColorMode),
					zen_mode: get(zenMode),
				}),
			});
		} catch (err) {
			console.warn('Failed to save preferences to backend:', err);
		}
	}, 500);
}

/** Load user preferences from backend */
export async function loadUserPreferences(): Promise<void> {
	if (!browser) return;
	const session = getStoredSession();
	if (!session?.access_token) return;

	try {
		const prefs = await apiFetch<{ theme: string; color_mode: string; zen_mode: boolean }>('/settings/preferences');
		if (prefs) {
			// Apply from backend, update local stores and storage
			if (prefs.theme && (builtInThemeNames.includes(prefs.theme as ThemeName) || themes[prefs.theme as ThemeName])) {
				currentThemeName.set(prefs.theme as ThemeName);
				localStorage.setItem(STORAGE_KEY, prefs.theme);
			}
			if (prefs.color_mode === 'light' || prefs.color_mode === 'dark') {
				currentColorMode.set(prefs.color_mode);
				localStorage.setItem(COLOR_MODE_STORAGE_KEY, prefs.color_mode);
			}
			if (typeof prefs.zen_mode === 'boolean') {
				zenMode.set(prefs.zen_mode);
				localStorage.setItem(ZEN_MODE_STORAGE_KEY, String(prefs.zen_mode));
			}
			// Apply the loaded preferences
			applyTheme(themes[get(currentThemeName)], get(currentColorMode));
			applyZenMode(get(zenMode));
		}
	} catch (err) {
		console.warn('Failed to load preferences from backend:', err);
	}
}

/** Load custom themes from API and register them. */
export async function loadCustomThemes(): Promise<void> {
	if (!browser) return;
	
	try {
		const session = getStoredSession();
		const headers: HeadersInit = {};
		if (session?.access_token) {
			headers['Authorization'] = `Bearer ${session.access_token}`;
		}
		
		const response = await fetch(apiUrl('/themes'), { headers });
		if (!response.ok) {
			console.warn('Failed to load custom themes:', response.status);
			return;
		}
		
		const data = await response.json();
		const fetchedThemes: ThemeConfig[] = (data.themes || []).map((t: Record<string, unknown>) => ({
			name: t.name as string,
			label: t.label as string,
			icon: t.icon as string || '🎨',
			bgImage: t.bgImage as string || '',
			wallpaperOverlay: t.wallpaperOverlay as string || '',
			bg: t.bg as string || '',
			bgColor: t.bgColor as string || '#1a1a2e',
			primary: t.primary as string || '#6366f1',
			primaryHover: t.primaryHover as string || '#818cf8',
			accentGradient: t.accentGradient as string || '#a855f7',
			primaryRgb: t.primaryRgb as string || '99, 102, 241',
			text: t.text as string || '#f8fafc',
			textMuted: t.textMuted as string || '#94a3b8',
			textPrimary: t.textPrimary as string || '#1e293b',
			textSecondary: t.textSecondary as string || 'rgba(0,0,0,0.55)',
			glassBg: t.glassBg as string || 'rgba(255, 255, 255, 0.55)',
			glassBorder: t.glassBorder as string || 'rgba(255, 255, 255, 0.7)',
			navGlass: t.navGlass as string || 'rgba(255, 255, 255, 0.5)',
			border: t.border as string || 'rgba(255,255,255,0.14)',
			glow: t.glow as string || 'rgba(99,102,241,0.35)',
			isBuiltin: t.isBuiltin as boolean ?? false,
			isCustom: t.isCustom as boolean ?? !t.isBuiltin,
		}));
		
		registerCustomThemes(fetchedThemes);
		customThemes.set(fetchedThemes);
		
		// Re-apply current theme if it was a custom one that just loaded
		const storedTheme = localStorage.getItem(STORAGE_KEY);
		if (storedTheme && themes[storedTheme as ThemeName]) {
			currentThemeName.set(storedTheme as ThemeName);
			applyTheme(themes[storedTheme as ThemeName], get(currentColorMode));
		}
	} catch (err) {
		console.warn('Error loading custom themes:', err);
	}
}

/** Initialize theme on app mount. */
export function initTheme() {
	const name = getInitialTheme();
	const mode = getInitialColorMode();
	const zen = getInitialZenMode();
	currentThemeName.set(name);
	currentColorMode.set(mode);
	zenMode.set(zen);
	applyTheme(themes[name], mode);
	applyZenMode(zen);
	
	// Load custom themes asynchronously
	loadCustomThemes();
	
	// Load user preferences from backend (will override localStorage if logged in)
	loadUserPreferences();
}
