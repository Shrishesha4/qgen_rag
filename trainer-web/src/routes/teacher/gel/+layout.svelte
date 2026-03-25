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
	<div class="border-b border-gray-200 dark:border-gray-700">
		<nav class="flex space-x-8" aria-label="Tabs">
			{#each tabs as tab}
				<a
					href={tab.href}
					class="flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors
						{currentPath === tab.href
						? 'border-primary-500 text-primary-600 dark:text-primary-400'
						: 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'}"
				>
					<svelte:component this={tab.icon} class="h-4 w-4" />
					<span>{tab.label}</span>
				</a>
			{/each}
		</nav>
	</div>

	<slot />
</div>
