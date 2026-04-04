/**
 * Theme store — manages global theme selection and applies CSS variables.
 * Persists choice to localStorage under `qgen-trainer-theme`.
 */

import { writable, derived, get } from 'svelte/store';
import { themes, themeNames, type ThemeName, type ThemeConfig } from './themes';
import { browser } from '$app/environment';

const STORAGE_KEY = 'qgen-trainer-theme';
const COLOR_MODE_STORAGE_KEY = 'qgen-trainer-color-mode';
export type ColorMode = 'light' | 'dark';

function getInitialTheme(): ThemeName {
	if (browser) {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored && themeNames.includes(stored as ThemeName)) {
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
	currentThemeName.set(name);
	if (browser) {
		localStorage.setItem(STORAGE_KEY, name);
	}
	applyTheme(themes[name], get(currentColorMode));
}

/** Set global color mode. */
export function setColorMode(mode: ColorMode) {
	currentColorMode.set(mode);
	if (browser) {
		localStorage.setItem(COLOR_MODE_STORAGE_KEY, mode);
	}
	const themeName = get(currentThemeName);
	applyTheme(themes[themeName], mode);
}

/** Toggle color mode light <-> dark. */
export function toggleColorMode() {
	const current = get(currentColorMode);
	setColorMode(current === 'dark' ? 'light' : 'dark');
}

/** Cycle to the next theme in order. */
export function cycleTheme() {
	currentThemeName.update((current) => {
		const idx = themeNames.indexOf(current);
		const next = themeNames[(idx + 1) % themeNames.length];
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
		return next;
	});
}

/** Set zen mode explicitly */
export function setZenMode(enabled: boolean) {
	zenMode.set(enabled);
	if (browser) localStorage.setItem(ZEN_MODE_STORAGE_KEY, String(enabled));
	applyZenMode(enabled);
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
}
