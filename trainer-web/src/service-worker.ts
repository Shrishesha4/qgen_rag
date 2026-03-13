/// <reference types="@sveltejs/kit" />
import { build, files, version } from '$service-worker';

const CACHE = `qgen-cache-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event) => {
	self.skipWaiting();
	event.waitUntil(
		caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches.keys().then((keys) =>
			Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
		)
	);
});

self.addEventListener('fetch', (event) => {
	if (event.request.method !== 'GET') return;
	const url = new URL(event.request.url);
	if (url.origin !== self.location.origin) return;
	const pathname = url.pathname;

	if (ASSETS.includes(pathname)) {
		event.respondWith(caches.open(CACHE).then((cache) => cache.match(pathname)));
		return;
	}

	event.respondWith(
		fetch(event.request)
			.then((response) => response)
			.catch(() => caches.match(event.request))
	);
});
