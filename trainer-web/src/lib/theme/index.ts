/**
 * Theme store — manages global theme selection and applies CSS variables.
 * Persists choice to localStorage under `qgen-trainer-theme`.
 */

import { writable, derived } from 'svelte/store';
import { themes, themeNames, type ThemeName, type ThemeConfig } from './themes';
import { browser } from '$app/environment';

const STORAGE_KEY = 'qgen-trainer-theme';

function getInitialTheme(): ThemeName {
	if (browser) {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored && themeNames.includes(stored as ThemeName)) {
			return stored as ThemeName;
		}
	}
	return 'fire';
}

export const currentThemeName = writable<ThemeName>(getInitialTheme());

export const currentTheme = derived(currentThemeName, ($name) => themes[$name]);

/** Apply CSS custom properties to :root */
function applyTheme(config: ThemeConfig) {
	if (!browser) return;
	const root = document.documentElement;
	root.style.setProperty('--theme-bg', config.bg);
	root.style.setProperty('--theme-bg-color', config.bgColor);
	root.style.setProperty('--theme-bg-image', `url(${config.bgImage})`);
	root.style.setProperty('--theme-wallpaper-overlay', config.wallpaperOverlay);
	root.style.setProperty('--theme-primary', config.primary);
	root.style.setProperty('--theme-primary-hover', config.primaryHover);
	root.style.setProperty('--theme-accent-gradient', config.accentGradient);
	root.style.setProperty('--theme-primary-rgb', config.primaryRgb);
	root.style.setProperty('--theme-text', config.text);
	root.style.setProperty('--theme-text-muted', config.textMuted);
	root.style.setProperty('--theme-text-primary', config.textPrimary);
	root.style.setProperty('--theme-text-secondary', config.textSecondary);
	root.style.setProperty('--theme-glass-bg', config.glassBg);
	root.style.setProperty('--theme-glass-border', config.glassBorder);
	root.style.setProperty('--theme-nav-glass', config.navGlass);
	root.style.setProperty('--theme-border', config.border);
	root.style.setProperty('--theme-glow', config.glow);
	root.setAttribute('data-theme', config.name);
}

/** Set a new theme by name. */
export function setTheme(name: ThemeName) {
	currentThemeName.set(name);
	if (browser) {
		localStorage.setItem(STORAGE_KEY, name);
	}
	applyTheme(themes[name]);
}

/** Cycle to the next theme in order. */
export function cycleTheme() {
	currentThemeName.update((current) => {
		const idx = themeNames.indexOf(current);
		const next = themeNames[(idx + 1) % themeNames.length];
		if (browser) localStorage.setItem(STORAGE_KEY, next);
		applyTheme(themes[next]);
		return next;
	});
}

/** Initialize theme on app mount. */
export function initTheme() {
	const name = getInitialTheme();
	applyTheme(themes[name]);
}
