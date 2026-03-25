<script lang="ts">
	import { page } from '$app/stores';
	import { ClipboardList, Users, BarChart3, Settings } from 'lucide-svelte';

	$: currentPath = $page.url.pathname;

	const tabs = [
		{ href: '/teacher/gel', label: 'Assignments', icon: ClipboardList },
		{ href: '/teacher/gel/items', label: 'Evaluation Items', icon: ClipboardList },
		{ href: '/teacher/gel/students', label: 'Students', icon: Users },
		{ href: '/teacher/gel/analytics', label: 'Analytics', icon: BarChart3 },
		{ href: '/teacher/gel/settings', label: 'Settings', icon: Settings },
	];
</script>

<div class="space-y-6">
	<div class="glass-panel px-4 py-3 border border-white/10 shadow-lg">
		<nav class="flex space-x-6 text-sm font-medium" aria-label="Tabs">
			{#each tabs as tab}
				<a
					href={tab.href}
					class={`flex items-center space-x-2 px-2 py-2 rounded-lg transition-colors duration-150
						${currentPath === tab.href
							? 'text-rose-200 border border-rose-400/60 bg-white/5 shadow-md'
							: 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'}`}
				>
					<svelte:component this={tab.icon} class="h-4 w-4" />
					<span>{tab.label}</span>
				</a>
			{/each}
		</nav>
	</div>

	<slot />
</div>
