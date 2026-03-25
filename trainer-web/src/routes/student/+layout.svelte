<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { StoredSession } from '$lib/api/client';
	import { session, currentUser } from '$lib/session';
	import { logout } from '$lib/api/auth';
	import { Book, ClipboardCheck, History, User, LogOut, Home, BarChart3 } from 'lucide-svelte';

	let isLoading = true;

	onMount(() => {
		const unsubscribe = session.subscribe((state: StoredSession | null) => {
			// Loading finishes as soon as we have evaluated the current session state
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

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/login');
	}

	$: currentPath = $page.url.pathname;
	$: user = $currentUser;

	const navItems = [
		{ href: '/student', label: 'Dashboard', icon: Home },
		{ href: '/student/assignments', label: 'Assignments', icon: ClipboardCheck },
		{ href: '/student/history', label: 'History', icon: History },
		{ href: '/student/progress', label: 'Progress', icon: BarChart3 },
		{ href: '/student/profile', label: 'Profile', icon: User },
	];
</script>

{#if isLoading}
	<div class="flex items-center justify-center min-h-screen">
		<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
	</div>
{:else if $session && $currentUser?.role === 'student'}
	<div class="min-h-screen bg-gray-50 dark:bg-gray-900">
		<!-- Top Navigation -->
		<nav class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
			<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
				<div class="flex justify-between h-16">
					<div class="flex items-center">
						<a href="/student" class="flex items-center space-x-2">
							<Book class="h-8 w-8 text-primary-600" />
							<span class="text-xl font-bold text-gray-900 dark:text-white">GELTrain</span>
						</a>
					</div>

					<div class="hidden md:flex items-center space-x-4">
						{#each navItems as item}
							<a
								href={item.href}
								class="flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors
									{currentPath === item.href
									? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
									: 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
							>
								<svelte:component this={item.icon} class="h-4 w-4" />
								<span>{item.label}</span>
							</a>
						{/each}
					</div>

					<div class="flex items-center space-x-4">
						<span class="text-sm text-gray-600 dark:text-gray-300">
							{user?.full_name || user?.username}
						</span>
						<button
							on:click={handleLogout}
							class="flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
						>
							<LogOut class="h-4 w-4" />
							<span class="hidden sm:inline">Logout</span>
						</button>
					</div>
				</div>
			</div>
		</nav>

		<!-- Mobile Navigation -->
		<div class="md:hidden bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
			<div class="flex overflow-x-auto px-4 py-2 space-x-2">
				{#each navItems as item}
					<a
						href={item.href}
						class="flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap
							{currentPath === item.href
							? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
							: 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}"
					>
						<svelte:component this={item.icon} class="h-4 w-4" />
						<span>{item.label}</span>
					</a>
				{/each}
			</div>
		</div>

		<!-- Main Content -->
		<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
			<slot />
		</main>
	</div>
{/if}
