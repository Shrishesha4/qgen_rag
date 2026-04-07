/**
 * Theme definitions — 5 atmospheric presets with background images.
 * Each theme has an Unsplash background image and a CSS gradient fallback.
 */

export type ThemeName = 'aurora' | 'water' | 'fire' | 'earth' | 'night' | 'dusk' | 'sunset' | 'purplesands' | string;

export interface ThemeConfig {
	name: ThemeName;
	label: string;
	icon: string;
	/** Background image URL (Unsplash) */
	bgImage: string;
	/** Overlay painted on top of wallpaper */
	wallpaperOverlay: string;
	/** Rich atmospheric gradient fallback */
	bg: string;
	/** Solid fallback */
	bgColor: string;
	/** Accent */
	primary: string;
	primaryHover: string;
	accentGradient: string;
	/** "R, G, B" for rgba usage */
	primaryRgb: string;
	/** Light text for dark backgrounds */
	text: string;
	textMuted: string;
	textPrimary: string;
	textSecondary: string;
	glassBg: string;
	glassBorder: string;
	navGlass: string;
	/** Glass border tint */
	border: string;
	/** Accent glow */
	glow: string;
	/** Whether this is a built-in theme (from DB seed) */
	isBuiltin?: boolean;
	/** Whether this is a custom theme (not a built-in) */
	isCustom?: boolean;
}

export const themes: Record<ThemeName, ThemeConfig> = {
	aurora: {
		name: 'aurora',
		label: 'Aurora',
		icon: '🌌',
		bgImage: '/theme-pictures/auroranew.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(2,10,18,0.16) 0%, rgba(2,10,18,0.08) 50%, rgba(1,8,14,0.22) 100%)',
		bg: [
			'radial-gradient(ellipse at 72% 24%, rgba(73, 255, 148, 0.3) 0%, transparent 44%)',
			'radial-gradient(ellipse at 36% 62%, rgba(38, 214, 190, 0.24) 0%, transparent 52%)',
			'radial-gradient(ellipse at 18% 90%, rgba(68, 148, 214, 0.22) 0%, transparent 50%)',
			'linear-gradient(173deg, #04111d 0%, #0a2434 24%, #12384d 46%, #11495f 66%, #0e3147 82%, #081e2f 100%)'
		].join(', '),
		bgColor: '#0f3347',
		primary: '#006a45',
		primaryHover: '#0ea371',
		accentGradient: '#008b81',
		primaryRgb: '23, 166, 115',
		text: '#e7f6f4',
		textMuted: '#a5c8cd',
		textPrimary: '#0f2533',
		textSecondary: 'rgba(10, 28, 38, 0.64)',
		glassBg: 'rgba(245, 255, 254, 0.56)',
		glassBorder: 'rgba(224, 246, 245, 0.74)',
		navGlass: 'rgba(237, 252, 251, 0.48)',
		border: 'rgba(255,255,255,0.18)',
		glow: 'rgba(39, 212, 200, 0.36)'
	},
	water: {
		name: 'water',
		label: 'Ocean',
		icon: '🌊',
		bgImage: '/theme-pictures/deep-ocean-new.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.0) 50%, rgba(0,0,0,0.15) 100%)',
		bg: [
			'radial-gradient(ellipse at 30% 80%, rgba(20,80,160,0.35) 0%, transparent 50%)',
			'radial-gradient(ellipse at 70% 20%, rgba(30,100,180,0.25) 0%, transparent 45%)',
			'linear-gradient(175deg, #0a1e38 0%, #152e50 20%, #1f4268 40%, #2a5680 60%, #356a98 80%, #407eb0 100%)'
		].join(', '),
		bgColor: '#1f4268',
		primary: '#14619c',
		primaryHover: '#2888d4',
		accentGradient: '#2dd4bf',
		primaryRgb: '56, 152, 224',
		text: '#e0e8f4',
		textMuted: '#8aa8c8',
		textPrimary: '#1a1a2e',
		textSecondary: 'rgba(0,0,0,0.55)',
		glassBg: 'rgba(255, 255, 255, 0.55)',
		glassBorder: 'rgba(255, 255, 255, 0.7)',
		navGlass: 'rgba(255, 255, 255, 0.5)',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(56,152,224,0.35)'
	},
	fire: {
		name: 'fire',
		label: 'Landscape',
		icon: '🌄',
		bgImage: '/theme-pictures/landscape.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(20,10,6,0.12) 0%, rgba(12,8,10,0.06) 48%, rgba(16,10,12,0.2) 100%)',
		bg: [
			'radial-gradient(ellipse at 72% 18%, rgba(255, 112, 66, 0.26) 0%, transparent 46%)',
			'radial-gradient(ellipse at 22% 84%, rgba(121, 70, 184, 0.2) 0%, transparent 50%)',
			'linear-gradient(172deg, #261321 0%, #3b1834 22%, #5b2340 42%, #7f2f37 62%, #a4492f 80%, #cb6a2f 100%)'
		].join(', '),
		bgColor: '#7f2f37',
		primary: '#cf5a29',
		primaryHover: '#e57a48',
		accentGradient: '#ff9f43',
		primaryRgb: '207, 90, 41',
		text: '#f8efe8',
		textMuted: '#d8b9aa',
		textPrimary: '#2e1914',
		textSecondary: 'rgba(38, 20, 18, 0.66)',
		glassBg: 'rgba(255, 250, 247, 0.58)',
		glassBorder: 'rgba(255, 233, 223, 0.78)',
		navGlass: 'rgba(255, 244, 238, 0.5)',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(224, 105, 62, 0.38)'
	},
	earth: {
		name: 'earth',
		label: 'Forest',
		icon: '🌿',
		bgImage: '/theme-pictures/dark-forest.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.05) 50%, rgba(0,0,0,0.15) 100%)',
		bg: [
			'radial-gradient(ellipse at 25% 75%, rgba(40,120,50,0.25) 0%, transparent 50%)',
			'radial-gradient(ellipse at 75% 25%, rgba(50,140,60,0.2) 0%, transparent 40%)',
			'linear-gradient(175deg, #0e1c0e 0%, #1a3018 20%, #264624 40%, #325c30 60%, #3e723c 80%, #4a8848 100%)'
		].join(', '),
		bgColor: '#325c30',
		primary: '#0c7713',
		primaryHover: '#38b040',
		accentGradient: '#40916c',
		primaryRgb: '72, 192, 80',
		text: '#e4f4e6',
		textMuted: '#90b894',
		textPrimary: '#1b2e1b',
		textSecondary: 'rgba(0,0,0,0.55)',
		glassBg: 'rgba(255, 255, 255, 0.55)',
		glassBorder: 'rgba(255, 255, 255, 0.7)',
		navGlass: 'rgba(255, 255, 255, 0.5)',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(72,192,80,0.35)'
	},
	night: {
		name: 'night',
		label: 'Midnight',
		icon: '🌙',
		bgImage: '/theme-pictures/midnight.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.2) 100%)',
		bg: [
			'radial-gradient(ellipse at 20% 60%, rgba(80,40,140,0.25) 0%, transparent 50%)',
			'radial-gradient(ellipse at 80% 80%, rgba(40,20,100,0.2) 0%, transparent 45%)',
			'linear-gradient(175deg, #08081a 0%, #0e0e2a 20%, #14143a 40%, #1a1a4a 60%, #12123a 80%, #181842 100%)'
		].join(', '),
		bgColor: '#14143a',
		primary: '#981e32',
		primaryHover: '#d83550',
		accentGradient: '#560bad',
		primaryRgb: '233, 69, 96',
		text: '#e8e8f4',
		textMuted: '#9a9ac0',
		textPrimary: '#1a1a2e',
		textSecondary: 'rgba(0,0,0,0.5)',
		glassBg: 'rgba(255, 255, 255, 0.45)',
		glassBorder: 'rgba(255, 255, 255, 0.6)',
		navGlass: 'rgba(255, 255, 255, 0.4)',
		border: 'rgba(255,255,255,0.12)',
		glow: 'rgba(233,69,96,0.35)'
	},
	dusk: {
		name: 'dusk',
		label: 'Dusk',
		icon: '🌆',
		bgImage: '/theme-pictures/dusk.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(16,10,42,0.16) 0%, rgba(12,8,28,0.08) 50%, rgba(12,8,26,0.22) 100%)',
		bg: [
			'radial-gradient(ellipse at 74% 22%, rgba(255, 108, 168, 0.3) 0%, transparent 45%)',
			'radial-gradient(ellipse at 22% 78%, rgba(138, 109, 255, 0.24) 0%, transparent 52%)',
			'linear-gradient(174deg, #1b1944 0%, #2a2f6f 24%, #444199 46%, #6f4aa8 66%, #99509c 82%, #cf6f9f 100%)'
		].join(', '),
		bgColor: '#444199',
		primary: '#c15175',
		primaryHover: '#f07cbc',
		accentGradient: '#8b6cff',
		primaryRgb: '225, 90, 167',
		text: '#f5edff',
		textMuted: '#cfb8ec',
		textPrimary: '#251a36',
		textSecondary: 'rgba(38, 30, 58, 0.62)',
		glassBg: 'rgba(252, 246, 255, 0.54)',
		glassBorder: 'rgba(242, 223, 255, 0.72)',
		navGlass: 'rgba(246, 234, 255, 0.46)',
		border: 'rgba(255,255,255,0.12)',
		glow: 'rgba(225, 90, 167, 0.36)'
	},
	sunset: {
		name: 'sunset',
		label: 'Sunset',
		icon: '🌅',
		bgImage: '/theme-pictures/sunset.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(22,14,8,0.12) 0%, rgba(18,14,18,0.06) 52%, rgba(14,10,12,0.2) 100%)',
		bg: [
			'radial-gradient(ellipse at 16% 18%, rgba(255, 199, 71, 0.4) 0%, transparent 40%)',
			'radial-gradient(ellipse at 78% 82%, rgba(36, 145, 219, 0.22) 0%, transparent 48%)',
			'linear-gradient(172deg, #173761 0%, #1f4f7a 20%, #3c6f8e 38%, #d1783e 58%, #f09d3e 77%, #ffd172 100%)'
		].join(', '),
		bgColor: '#d1783e',
		primary: '#de7a2a',
		primaryHover: '#ee9546',
		accentGradient: '#3ea0d8',
		primaryRgb: '222, 122, 42',
		text: '#fff4e2',
		textMuted: '#e7cba7',
		textPrimary: '#2f1d11',
		textSecondary: 'rgba(43, 27, 16, 0.64)',
		glassBg: 'rgba(255, 250, 240, 0.58)',
		glassBorder: 'rgba(255, 236, 208, 0.76)',
		navGlass: 'rgba(255, 246, 230, 0.5)',
		border: 'rgba(255,255,255,0.12)',
		glow: 'rgba(222, 122, 42, 0.36)'
	},
	purplesands: {
		name: 'purplesands',
		label: 'Purple Sands',
		icon: '🏜️',
		bgImage: '/theme-pictures/purple-sands.webp',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(15,12,40,0.16) 0%, rgba(12,10,34,0.08) 50%, rgba(9,8,24,0.24) 100%)',
		bg: [
			'radial-gradient(ellipse at 55% 24%, rgba(255, 123, 196, 0.28) 0%, transparent 45%)',
			'radial-gradient(ellipse at 80% 70%, rgba(104, 108, 255, 0.25) 0%, transparent 50%)',
			'linear-gradient(174deg, #121532 0%, #1e2a5a 24%, #38438a 44%, #6f5ea5 62%, #9f63a5 80%, #d67cb5 100%)'
		].join(', '),
		bgColor: '#38438a',
		primary: '#c35bb5',
		primaryHover: '#d77ac7',
		accentGradient: '#5d7dff',
		primaryRgb: '195, 91, 181',
		text: '#f2ecff',
		textMuted: '#c5b8e8',
		textPrimary: '#231d3d',
		textSecondary: 'rgba(33, 26, 56, 0.62)',
		glassBg: 'rgba(247, 242, 255, 0.54)',
		glassBorder: 'rgba(229, 220, 255, 0.72)',
		navGlass: 'rgba(236, 228, 255, 0.46)',
		border: 'rgba(255,255,255,0.12)',
		glow: 'rgba(195, 91, 181, 0.36)'
	}
};

import { writable, get } from 'svelte/store';

/** Built-in theme names (cannot be overwritten by custom themes) */
export const builtInThemeNames: ThemeName[] = ['aurora', 'water', 'fire', 'earth', 'night', 'dusk', 'sunset', 'purplesands'];

/** Reactive store for all theme names (built-in + custom) */
export const themeNamesStore = writable<ThemeName[]>([...builtInThemeNames]);

/** Legacy export for backward compatibility - use themeNamesStore for reactivity */
export function getThemeNames(): ThemeName[] {
	return get(themeNamesStore);
}

/** Merge themes from database into the themes registry */
export function registerCustomThemes(dbThemes: ThemeConfig[]) {
	// When themes come from DB (after seeding), they include both builtin and custom
	// Override the hardcoded themes with DB versions, add any new custom themes
	
	// Build new theme list starting fresh
	const newNames: ThemeName[] = [];
	
	// Add/update themes from database
	for (const theme of dbThemes) {
		const config: ThemeConfig = {
			...theme,
			name: theme.name as ThemeName,
		};
		themes[theme.name as ThemeName] = config;
		if (!newNames.includes(theme.name)) {
			newNames.push(theme.name);
		}
	}
	
	// If no themes from DB, use hardcoded builtin themes as fallback
	if (newNames.length === 0) {
		newNames.push(...builtInThemeNames);
	}
	
	// Update the store - triggers reactivity in all subscribers
	themeNamesStore.set(newNames);
}
