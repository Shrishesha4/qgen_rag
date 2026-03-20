import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import sass from 'sass';

export default defineConfig({
	server: {
		allowedHosts: true,
		// Speed up CSS serving by using faster transforms
		middlewareMode: false,
	},
	// Optimize CSS generation
	css: {
		postcss: {},
		preprocessorOptions: {
			scss: {
				implementation: sass,
			},
		},
		devSourcemap: false, // Disable source maps in dev for speed
	},
	build: {
		cssCodeSplit: true,
		cssMinify: true,
	},
	plugins: [tailwindcss(), sveltekit()],
});

