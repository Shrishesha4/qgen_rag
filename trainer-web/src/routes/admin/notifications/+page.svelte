<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		listAdminNotifications,
		markAdminNotificationRead,
		markAllAdminNotificationsRead,
		type AdminNotificationSummary,
	} from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let success = $state('');
	let filterMode = $state<'all' | 'unread' | 'read'>('unread');
	let notifications = $state<AdminNotificationSummary[]>([]);
	let unreadCount = $state(0);
	let busyByNotification = $state<Record<string, boolean>>({});
	let markAllBusy = $state(false);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void loadNotifications();
		return unsub;
	});

	async function loadNotifications() {
		loading = true;
		error = '';
		try {
			const response = await listAdminNotifications({ limit: 200 });
			notifications = response.notifications;
			unreadCount = response.unread_count;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load notifications';
		} finally {
			loading = false;
		}
	}

	async function setFilterMode(nextMode: 'all' | 'unread' | 'read') {
		if (filterMode === nextMode) return;
		filterMode = nextMode;
		await loadNotifications();
	}

	function getFilteredNotifications(): AdminNotificationSummary[] {
		if (filterMode === 'unread') {
			return notifications.filter((n) => !n.is_read);
		} else if (filterMode === 'read') {
			return notifications.filter((n) => n.is_read);
		}
		return notifications;
	}

	async function markRead(notification: AdminNotificationSummary) {
		if (notification.is_read || busyByNotification[notification.id]) return;
		busyByNotification = { ...busyByNotification, [notification.id]: true };
		error = '';
		try {
			const updated = await markAdminNotificationRead(notification.id);
			notifications = notifications.map((item) => (item.id === updated.id ? updated : item));
			unreadCount = Math.max(0, unreadCount - 1);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update notification';
		} finally {
			busyByNotification = { ...busyByNotification, [notification.id]: false };
		}
	}

	async function viewNotification(notification: AdminNotificationSummary) {
		if (!notification.action_url || busyByNotification[notification.id]) return;
		if (!notification.is_read) {
			await markRead(notification);
		}
		goto(notification.action_url);
	}

	async function markAllRead() {
		if (markAllBusy || unreadCount === 0) return;
		markAllBusy = true;
		error = '';
		success = '';
		try {
			const response = await markAllAdminNotificationsRead();
			notifications = notifications.map((notification) => ({
				...notification,
				is_read: true,
			}));
			unreadCount = 0;
			success = response.message;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to mark notifications as read';
		} finally {
			markAllBusy = false;
		}
	}

	function notificationMethod(notification: AdminNotificationSummary): string {
		if (notification.notification_type === 'user_registration_requested') {
			return 'Registration';
		}
		const selfServiceEnabled = Boolean(notification.payload?.self_service_enabled ?? true);
		if (!selfServiceEnabled) return 'Admin Approval';
		const method = String(notification.payload?.method ?? '');
		if (method === 'security_question') return 'Security Question';
		if (method === 'smtp') return 'SMTP';
		return 'Alert';
	}

	function formatDate(value: string | null): string {
		if (!value) return 'Unknown';
		return new Date(value).toLocaleString();
	}
</script>

<svelte:head>
	<title>Notifications — Admin</title>
</svelte:head>

<div class="page">
	<div class="header glass-panel">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title">Notifications</h1>
			<p class="subtitle">Review admin alerts, including password reset requests that need attention.</p>
		</div>
		<div class="header-meta">
			<span class="count-pill">{unreadCount} unread</span>
			{#if filterMode === 'unread' && unreadCount > 0}
				<button class="action-btn" onclick={markAllRead} disabled={markAllBusy}>
					{markAllBusy ? 'Updating...' : 'Mark All Read'}
				</button>
			{/if}
		</div>
	</div>

	<div class="toolbar glass-panel">
		<div class="filter-tabs" role="tablist" aria-label="Notification filters">
			<button class="filter-tab" class:active={filterMode === 'all'} onclick={() => setFilterMode('all')}>All</button>
			<button class="filter-tab" class:active={filterMode === 'unread'} onclick={() => setFilterMode('unread')}>Unread</button>
			<button class="filter-tab" class:active={filterMode === 'read'} onclick={() => setFilterMode('read')}>Read</button>
		</div>
		<button class="action-btn secondary" onclick={loadNotifications} disabled={loading}>
			{loading ? 'Refreshing...' : 'Refresh'}
		</button>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if success}
		<div class="success-banner" role="status">{success}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading notifications...</p>
		</div>
	{:else if notifications.length === 0}
		<div class="center-state glass-panel">
			<p>No notifications to show.</p>
		</div>
	{:else if getFilteredNotifications().length === 0}
		<div class="center-state glass-panel">
			<p>No {filterMode} notifications.</p>
		</div>
	{:else}
		<div class="notification-list">
			{#each getFilteredNotifications() as notification}
				<section class="notification-card glass-panel" class:is-read={notification.is_read}>
					<div class="notification-top">
						<div class="notification-copy">
							<div class="notification-heading">
								<h2>{notification.title}</h2>
								<span class="method-pill">{notificationMethod(notification)}</span>
								{#if notification.is_read}
									<span class="read-pill">Read</span>
								{/if}
							</div>
							<p class="notification-message">{notification.message}</p>
							<div class="notification-meta">
								<span>{formatDate(notification.created_at)}</span>
								{#if notification.target_user_email}
									<span>{notification.target_user_email}</span>
								{/if}
							</div>
						</div>
						<div class="notification-actions">
							{#if notification.action_url && notification.action_label}
								<button class="action-btn" onclick={() => viewNotification(notification)} disabled={busyByNotification[notification.id]}>
									{busyByNotification[notification.id] ? 'Opening...' : notification.action_label}
								</button>
							{/if}
							{#if !notification.is_read}
								<button class="action-btn secondary" onclick={() => markRead(notification)} disabled={busyByNotification[notification.id]}>
									Mark Read
								</button>
							{/if}
						</div>
					</div>
				</section>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.25rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.header,
	.toolbar,
	.notification-card,
	.center-state {
		padding: 1rem;
		border-radius: 1rem;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.title {
		margin: 0.3rem 0 0;
		font-size: 1.55rem;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.4rem 0 0;
		color: var(--theme-text-muted);
	}

	.header-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.count-pill,
	.method-pill,
	.read-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.3rem 0.6rem;
		border-radius: 999px;
		font-size: 0.76rem;
		font-weight: 700;
	}

	.count-pill,
	.method-pill {
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		border: 1px solid color-mix(in srgb, var(--theme-primary) 36%, var(--theme-glass-border));
		color: var(--theme-text);
	}

	.read-pill {
		background: rgba(34, 197, 94, 0.14);
		border: 1px solid rgba(34, 197, 94, 0.3);
		color: #86efac;
	}

	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.filter-tabs {
		display: flex;
		gap: 0.55rem;
		flex-wrap: wrap;
	}

	.filter-tab,
	.action-btn {
		padding: 0.55rem 0.85rem;
		border-radius: 0.75rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 36%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 12%, var(--theme-input-bg));
		color: var(--theme-text);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.filter-tab.active {
		background: color-mix(in srgb, var(--theme-primary) 20%, var(--theme-input-bg));
	}

	.action-btn.secondary {
		background: color-mix(in srgb, var(--theme-input-bg) 88%, transparent);
		border-color: var(--theme-glass-border);
	}

	.error-banner,
	.success-banner {
		padding: 0.85rem 0.95rem;
		border-radius: 0.8rem;
	}

	.error-banner {
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.success-banner {
		background: rgba(34, 197, 94, 0.12);
		border: 1px solid rgba(34, 197, 94, 0.28);
		color: #86efac;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.6rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 1.5rem;
		height: 1.5rem;
		border: 2px solid rgba(255, 255, 255, 0.18);
		border-top-color: var(--theme-primary);
		border-radius: 999px;
		animation: spin 1s linear infinite;
	}

	.notification-list {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.notification-card.is-read {
		opacity: 0.82;
	}

	.notification-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.notification-copy {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		min-width: 0;
	}

	.notification-heading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.notification-heading h2 {
		margin: 0;
		font-size: 1rem;
		color: var(--theme-text);
	}

	.notification-message {
		margin: 0;
		color: var(--theme-text);
		line-height: 1.5;
	}

	.notification-meta {
		display: flex;
		gap: 0.65rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.notification-actions {
		display: flex;
		gap: 0.55rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 768px) {
		.header,
		.toolbar,
		.notification-top {
			flex-direction: column;
		}

		.header-meta,
		.notification-actions {
			justify-content: flex-start;
		}
	}
</style>