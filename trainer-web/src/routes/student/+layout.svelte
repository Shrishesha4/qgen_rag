<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { StoredSession } from '$lib/api/client';
	import { session, currentUser } from '$lib/session';

	let isLoading = true;

	onMount(() => {
		const unsubscribe = session.subscribe((state: StoredSession | null) => {
			isLoading = false;
			if (!state) {
				goto('/login?redirect=' + encodeURIComponent($page.url.pathname));
				return;
			}

			const role = state.user?.role;
			if (role !== 'student') {
				if (role === 'teacher') {
					goto('/teacher');
				} else if (role === 'admin') {
					goto('/admin');
				} else {
					goto('/');
				}
			}
		});

		return () => unsubscribe();
	});

</script>

{#if isLoading}
	<div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
		<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-400"></div>
	</div>
{:else if $session && $currentUser?.role === 'student'}
	<slot />
{/if}
