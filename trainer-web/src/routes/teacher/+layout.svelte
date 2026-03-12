<script lang="ts">
	import { page } from '$app/stores';
	import DashboardLayout from '$lib/components/DashboardLayout.svelte';

	let { children } = $props();

	let isLoginPage = $derived($page.url.pathname.includes('/login'));
</script>

{#if isLoginPage}
	{@render children()}
{:else}
	<DashboardLayout>
		{@render children()}
	</DashboardLayout>
{/if}
