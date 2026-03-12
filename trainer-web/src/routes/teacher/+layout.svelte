<script lang="ts">
	import { page } from '$app/stores';

	let { children } = $props();

	let isLoginPage = $derived($page.url.pathname.includes('/login'));
</script>

{#if isLoginPage}
	{@render children()}
{:else}
	{@render children()}
{/if}
