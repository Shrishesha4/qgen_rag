/**
 * Theme definitions — 5 atmospheric presets with background images.
 * Each theme has an Unsplash background image and a CSS gradient fallback.
 */

export type ThemeName = 'ice' | 'water' | 'fire' | 'earth' | 'night';

export interface ThemeConfig {
	name: ThemeName;
	label: string;
	icon: string;
	/** Background image URL (Unsplash) */
	bgImage: string;
	/** Rich atmospheric gradient fallback */
	bg: string;
	/** Solid fallback */
	bgColor: string;
	/** Accent */
	primary: string;
	primaryHover: string;
	/** "R, G, B" for rgba usage */
	primaryRgb: string;
	/** Light text for dark backgrounds */
	text: string;
	textMuted: string;
	/** Glass border tint */
	border: string;
	/** Accent glow */
	glow: string;
}

export const themes: Record<ThemeName, ThemeConfig> = {
	ice: {
		name: 'ice',
		label: 'Aurora',
		icon: '❄️',
		bgImage: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=2694&auto=format&fit=crop',
		bg: [
			'radial-gradient(ellipse at 25% 70%, rgba(180,200,230,0.25) 0%, transparent 50%)',
			'radial-gradient(ellipse at 75% 30%, rgba(150,185,220,0.2) 0%, transparent 40%)',
			'radial-gradient(ellipse at 50% 100%, rgba(200,218,235,0.15) 0%, transparent 45%)',
			'linear-gradient(175deg, #4a5e72 0%, #5c7289 15%, #6e869e 30%, #7f98b0 50%, #8ba8be 65%, #7d96ad 80%, #8fafc5 100%)'
		].join(', '),
		bgColor: '#7a94ac',
		primary: '#48b8e8',
		primaryHover: '#32a8dc',
		primaryRgb: '72, 184, 232',
		text: '#eaf0f6',
		textMuted: '#a8bccf',
		border: 'rgba(255,255,255,0.18)',
		glow: 'rgba(72,184,232,0.35)'
	},
	water: {
		name: 'water',
		label: 'Deep Ocean',
		icon: '🌊',
		bgImage: 'https://images.unsplash.com/photo-1582967788606-a171c1080cb0?q=80&w=2564&auto=format&fit=crop',
		bg: [
			'radial-gradient(ellipse at 30% 80%, rgba(20,80,160,0.35) 0%, transparent 50%)',
			'radial-gradient(ellipse at 70% 20%, rgba(30,100,180,0.25) 0%, transparent 45%)',
			'linear-gradient(175deg, #0a1e38 0%, #152e50 20%, #1f4268 40%, #2a5680 60%, #356a98 80%, #407eb0 100%)'
		].join(', '),
		bgColor: '#1f4268',
		primary: '#3898e0',
		primaryHover: '#2888d4',
		primaryRgb: '56, 152, 224',
		text: '#e0e8f4',
		textMuted: '#8aa8c8',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(56,152,224,0.35)'
	},
	fire: {
		name: 'fire',
		label: 'Abstract Glass',
		icon: '🔥',
		bgImage: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2564&auto=format&fit=crop',
		bg: [
			'radial-gradient(ellipse at 40% 80%, rgba(200,60,20,0.2) 0%, transparent 50%)',
			'radial-gradient(ellipse at 60% 20%, rgba(220,100,40,0.15) 0%, transparent 45%)',
			'linear-gradient(175deg, #1a0e08 0%, #2e1810 20%, #44241a 40%, #5c3224 60%, #74422e 80%, #8c5238 100%)'
		].join(', '),
		bgColor: '#5c3224',
		primary: '#f07030',
		primaryHover: '#e06020',
		primaryRgb: '240, 112, 48',
		text: '#f4ece4',
		textMuted: '#c0a898',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(240,112,48,0.35)'
	},
	earth: {
		name: 'earth',
		label: 'Dark Forest',
		icon: '🌿',
		bgImage: 'https://images.unsplash.com/photo-1511497584788-876760111969?q=80&w=2689&auto=format&fit=crop',
		bg: [
			'radial-gradient(ellipse at 25% 75%, rgba(40,120,50,0.25) 0%, transparent 50%)',
			'radial-gradient(ellipse at 75% 25%, rgba(50,140,60,0.2) 0%, transparent 40%)',
			'linear-gradient(175deg, #0e1c0e 0%, #1a3018 20%, #264624 40%, #325c30 60%, #3e723c 80%, #4a8848 100%)'
		].join(', '),
		bgColor: '#325c30',
		primary: '#48c050',
		primaryHover: '#38b040',
		primaryRgb: '72, 192, 80',
		text: '#e4f4e6',
		textMuted: '#90b894',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(72,192,80,0.35)'
	},
	night: {
		name: 'night',
		label: 'Midnight',
		icon: '🌙',
		bgImage: 'https://images.unsplash.com/photo-1475274047050-1d0c55b0033f?q=80&w=2672&auto=format&fit=crop',
		bg: [
			'radial-gradient(ellipse at 20% 60%, rgba(80,40,140,0.25) 0%, transparent 50%)',
			'radial-gradient(ellipse at 80% 80%, rgba(40,20,100,0.2) 0%, transparent 45%)',
			'linear-gradient(175deg, #08081a 0%, #0e0e2a 20%, #14143a 40%, #1a1a4a 60%, #12123a 80%, #181842 100%)'
		].join(', '),
		bgColor: '#14143a',
		primary: '#e94560',
		primaryHover: '#d83550',
		primaryRgb: '233, 69, 96',
		text: '#e8e8f4',
		textMuted: '#9a9ac0',
		border: 'rgba(255,255,255,0.12)',
		glow: 'rgba(233,69,96,0.35)'
	}
};

export const themeNames: ThemeName[] = ['ice', 'water', 'fire', 'earth', 'night'];
