<script lang="ts">
	import { page } from '$app/stores';
	import { BarChart3, ClipboardCheck, ClipboardList, Settings, Users } from 'lucide-svelte';

	$: currentPath = $page.url.pathname;

	const tabs = [
		{ href: '/teacher/gel', label: 'Assignments', icon: ClipboardList },
		{ href: '/teacher/gel/items', label: 'Evaluation Items', icon: ClipboardCheck },
		{ href: '/teacher/gel/students', label: 'Students', icon: Users },
		{ href: '/teacher/gel/analytics', label: 'Analytics', icon: BarChart3 },
		{ href: '/teacher/gel/settings', label: 'Settings', icon: Settings }
	];
</script>

<div class="gel-shell">
	<section class="gel-shell__nav">
		<nav class="gel-tabs" aria-label="GEL sections">
			{#each tabs as tab}
				<a
					href={tab.href}
					class:active={currentPath === tab.href}
					class="gel-tab"
					aria-current={currentPath === tab.href ? 'page' : undefined}
				>
					<svelte:component this={tab.icon} class="h-4 w-4" />
					<span>{tab.label}</span>
				</a>
			{/each}
		</nav>
	</section>

	<slot />
</div>

<style>
	.gel-shell {
		--gel-panel-bg: color-mix(in srgb, var(--theme-nav-glass) 94%, rgba(15, 20, 28, 0.2));
		--gel-panel-bg-strong: color-mix(in srgb, var(--theme-surface) 92%, rgba(14, 18, 26, 0.28));
		--gel-panel-border: color-mix(in srgb, var(--theme-glass-border) 86%, rgba(255, 255, 255, 0.08));
		--gel-text: var(--theme-text-primary);
		--gel-muted: var(--theme-text-secondary);
		--gel-accent: var(--theme-primary);
		--gel-accent-rgb: var(--theme-primary-rgb);
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: clamp(0.9rem, 1.4vw, 1.25rem);
		min-height: 100%;
		box-sizing: border-box;
		color: var(--gel-text);
	}

	.gel-shell__nav {
		padding: 1.05rem 1.15rem;
		border-radius: 1.35rem;
		border: 1px solid var(--gel-panel-border);
		background:
			radial-gradient(circle at top right, rgba(var(--gel-accent-rgb), 0.14), transparent 34%),
			linear-gradient(180deg, color-mix(in srgb, var(--gel-panel-bg) 86%, white 14%), var(--gel-panel-bg));
		box-shadow: 0 22px 54px rgba(7, 12, 19, 0.18);
		backdrop-filter: blur(16px);
		-webkit-backdrop-filter: blur(16px);
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.gel-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.65rem;
	}

	.gel-tab {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.7rem 0.95rem;
		border-radius: 0.95rem;
		border: 1px solid transparent;
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 76%, transparent);
		color: var(--gel-muted);
		text-decoration: none;
		font-size: 0.92rem;
		font-weight: 700;
		transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease, transform 0.18s ease;
	}

	.gel-tab:hover {
		color: var(--gel-text);
		border-color: color-mix(in srgb, rgba(var(--gel-accent-rgb), 0.22) 72%, var(--gel-panel-border));
		transform: translateY(-1px);
	}

	.gel-tab.active {
		color: var(--gel-text);
		border-color: color-mix(in srgb, rgba(var(--gel-accent-rgb), 0.32) 75%, var(--gel-panel-border));
		background: linear-gradient(180deg, rgba(var(--gel-accent-rgb), 0.18), rgba(var(--gel-accent-rgb), 0.08));
		box-shadow: 0 10px 24px rgba(var(--gel-accent-rgb), 0.16);
	}

	:global(.gel-page) {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		color: var(--gel-text);
	}

	:global(.gel-panel) {
		background: var(--gel-panel-bg);
		border: 1px solid var(--gel-panel-border);
		border-radius: 1.25rem;
		box-shadow: 0 22px 54px rgba(7, 12, 19, 0.16);
		backdrop-filter: blur(16px);
		-webkit-backdrop-filter: blur(16px);
	}

	:global(.gel-page__hero) {
		padding: 1.35rem 1.45rem;
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		flex-wrap: wrap;
		background:
			radial-gradient(circle at top right, rgba(var(--gel-accent-rgb), 0.12), transparent 34%),
			linear-gradient(180deg, color-mix(in srgb, var(--gel-panel-bg-strong) 86%, white 14%), var(--gel-panel-bg));
	}

	:global(.gel-page__eyebrow) {
		margin: 0;
		font-size: 0.76rem;
		text-transform: uppercase;
		letter-spacing: 0.18em;
		color: var(--gel-muted);
	}

	:global(.gel-page__title) {
		margin: 0.2rem 0 0;
		font-size: clamp(1.5rem, 1.9vw, 2.15rem);
		font-weight: 800;
		line-height: 1.1;
		color: var(--gel-text);
	}

	:global(.gel-page__copy) {
		margin: 0.4rem 0 0;
		max-width: 56rem;
		color: var(--gel-muted);
		line-height: 1.55;
	}

	:global(.gel-page__actions) {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex-wrap: wrap;
	}

	:global(.gel-toolbar) {
		padding: 1rem 1.1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	:global(.gel-toolbar--single-row) {
		align-items: stretch;
	}

	:global(.gel-toolbar__grow) {
		flex: 1 1 20rem;
		min-width: 16rem;
	}

	:global(.gel-toolbar__filters) {
		flex: 1 1 30rem;
		min-width: 24rem;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
		align-items: end;
	}

	:global(.gel-toolbar__controls) {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 0 0 auto;
		flex-wrap: nowrap;
	}

	:global(.gel-toolbar__controls .gel-select) {
		width: clamp(11rem, 14vw, 13rem);
		min-width: 11rem;
		flex: 0 0 auto;
	}

	:global(.gel-toolbar__controls .gel-button),
	:global(.gel-toolbar__controls > a.gel-button) {
		flex: 0 0 auto;
		white-space: nowrap;
	}

	:global(.gel-input),
	:global(.gel-select),
	:global(.gel-textarea) {
		width: 100%;
		padding: 0.82rem 0.95rem;
		border-radius: 0.95rem;
		border: 1px solid var(--gel-panel-border);
		background: color-mix(in srgb, var(--theme-input-bg) 72%, var(--theme-surface) 28%);
		color: var(--gel-text);
		font: inherit;
	}

	:global(.gel-input::placeholder),
	:global(.gel-textarea::placeholder) {
		color: var(--gel-muted);
	}

	:global(.gel-input:focus),
	:global(.gel-select:focus),
	:global(.gel-textarea:focus) {
		outline: none;
		border-color: rgba(var(--gel-accent-rgb), 0.42);
		box-shadow: 0 0 0 3px rgba(var(--gel-accent-rgb), 0.14);
	}

	:global(.gel-search) {
		position: relative;
	}

	:global(.gel-search svg) {
		position: absolute;
		left: 0.9rem;
		top: 50%;
		transform: translateY(-50%);
		color: var(--gel-muted);
	}

	:global(.gel-search .gel-input) {
		padding-left: 2.8rem;
	}

	:global(.gel-button) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.82rem 1rem;
		border-radius: 0.95rem;
		border: 1px solid transparent;
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 78%, transparent);
		color: var(--gel-text);
		font: inherit;
		font-weight: 700;
		text-decoration: none;
		cursor: pointer;
		transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
	}

	:global(.gel-button:hover:not(:disabled)) {
		transform: translateY(-1px);
	}

	:global(.gel-button:disabled) {
		opacity: 0.6;
		cursor: not-allowed;
	}

	:global(.gel-button--primary) {
		background: linear-gradient(180deg, color-mix(in srgb, rgba(var(--gel-accent-rgb), 0.92) 84%, white 16%), rgba(var(--gel-accent-rgb), 0.92));
		color: #fff;
		box-shadow: 0 14px 28px rgba(var(--gel-accent-rgb), 0.24);
	}

	:global(.gel-button--ghost) {
		border-color: var(--gel-panel-border);
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 68%, transparent);
	}

	:global(.gel-button--quiet) {
		padding: 0.55rem 0.8rem;
		background: transparent;
		border-color: var(--gel-panel-border);
	}

	:global(.gel-button--sm) {
		padding: 0.6rem 0.78rem;
		font-size: 0.88rem;
	}

	:global(.gel-alert) {
		padding: 0.95rem 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(248, 113, 113, 0.26);
		background: rgba(127, 29, 29, 0.14);
		color: #fecaca;
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	:global(.gel-loading),
	:global(.gel-empty) {
		padding: 3rem 1.5rem;
		display: grid;
		place-items: center;
		gap: 0.75rem;
		text-align: center;
	}

	:global(.gel-empty h3),
	:global(.gel-empty h2) {
		margin: 0;
		font-size: 1.15rem;
		color: var(--gel-text);
	}

	:global(.gel-empty p),
	:global(.gel-loading p) {
		margin: 0;
		color: var(--gel-muted);
	}

	:global(.gel-spinner) {
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		border: 3px solid rgba(var(--gel-accent-rgb), 0.18);
		border-top-color: rgba(var(--gel-accent-rgb), 0.9);
		animation: gel-spin 0.8s linear infinite;
	}

	:global(.gel-stat-grid) {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.9rem;
	}

	:global(.gel-stat-card) {
		padding: 1rem 1.05rem;
		display: grid;
		gap: 0.45rem;
	}

	:global(.gel-stat-card__head) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.6rem;
		color: var(--gel-muted);
		font-size: 0.85rem;
	}

	:global(.gel-stat-card__value) {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		line-height: 1;
		color: var(--gel-text);
	}

	:global(.gel-stat-card__meta) {
		margin: 0;
		font-size: 0.88rem;
		color: var(--gel-muted);
	}

	:global(.gel-table-shell) {
		overflow: hidden;
	}

	:global(.gel-table-scroll) {
		overflow-x: auto;
	}

	:global(.gel-table) {
		width: 100%;
		min-width: 760px;
		border-collapse: collapse;
	}

	:global(.gel-table th),
	:global(.gel-table td) {
		padding: 0.95rem 1rem;
		text-align: left;
		vertical-align: top;
		border-bottom: 1px solid color-mix(in srgb, var(--gel-panel-border) 86%, transparent);
	}

	:global(.gel-table th) {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		font-weight: 800;
		color: var(--gel-muted);
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 78%, transparent);
	}

	:global(.gel-table tbody tr:hover) {
		background: color-mix(in srgb, rgba(var(--gel-accent-rgb), 0.08) 74%, transparent);
	}

	:global(.gel-table tbody tr:last-child td) {
		border-bottom: none;
	}

	:global(.gel-table__title) {
		margin: 0;
		font-weight: 700;
		color: var(--gel-text);
	}

	:global(.gel-table__subcopy) {
		margin: 0.3rem 0 0;
		color: var(--gel-muted);
		font-size: 0.9rem;
		line-height: 1.45;
	}

	:global(.gel-table__link) {
		color: var(--gel-text);
		text-decoration: none;
	}

	:global(.gel-table__actions) {
		display: flex;
		justify-content: flex-end;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	:global(.gel-status) {
		display: inline-flex;
		align-items: center;
		padding: 0.34rem 0.65rem;
		border-radius: 999px;
		font-size: 0.76rem;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		border: 1px solid transparent;
	}

	:global(.gel-status--draft) {
		background: rgba(148, 163, 184, 0.16);
		color: #e2e8f0;
		border-color: rgba(148, 163, 184, 0.22);
	}

	:global(.gel-status--scheduled) {
		background: rgba(59, 130, 246, 0.14);
		color: #bfdbfe;
		border-color: rgba(59, 130, 246, 0.24);
	}

	:global(.gel-status--active) {
		background: rgba(34, 197, 94, 0.14);
		color: #bbf7d0;
		border-color: rgba(34, 197, 94, 0.24);
	}

	:global(.gel-status--closed) {
		background: rgba(245, 158, 11, 0.14);
		color: #fde68a;
		border-color: rgba(245, 158, 11, 0.24);
	}

	:global(.gel-status--archived),
	:global(.gel-status--retired) {
		background: rgba(248, 113, 113, 0.14);
		color: #fecaca;
		border-color: rgba(248, 113, 113, 0.24);
	}

	:global(.gel-status--muted) {
		background: rgba(148, 163, 184, 0.12);
		color: var(--gel-muted);
		border-color: rgba(148, 163, 184, 0.18);
	}

	:global(.gel-grid-2),
	:global(.gel-grid-3),
	:global(.gel-grid-4) {
		display: grid;
		gap: 1rem;
	}

	:global(.gel-grid-2) {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	:global(.gel-grid-3) {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	:global(.gel-grid-4) {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}

	:global(.gel-card) {
		padding: 1.15rem 1.2rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	:global(.gel-card__header) {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	:global(.gel-card__title) {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--gel-text);
	}

	:global(.gel-card__copy) {
		margin: 0;
		color: var(--gel-muted);
		line-height: 1.5;
	}

	:global(.gel-stack) {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	:global(.gel-note) {
		padding: 0.95rem 1rem;
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		border-radius: 1rem;
		border: 1px solid rgba(250, 204, 21, 0.28);
		background: rgba(120, 53, 15, 0.14);
		color: #fde68a;
	}

	:global(.gel-note p) {
		margin: 0;
	}

	:global(.gel-form-grid) {
		display: grid;
		gap: 1rem;
	}

	:global(.gel-form-grid--two) {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	:global(.gel-field) {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	:global(.gel-field label),
	:global(.gel-field__label) {
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--gel-text);
	}

	:global(.gel-check-row) {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		color: var(--gel-text);
	}

	:global(.gel-check-row input[type='checkbox']) {
		accent-color: rgba(var(--gel-accent-rgb), 0.92);
	}

	:global(.gel-modal-backdrop) {
		position: fixed;
		inset: 0;
		background: rgba(10, 14, 22, 0.56);
		display: grid;
		place-items: center;
		padding: 1rem;
		z-index: 70;
	}

	:global(.gel-modal) {
		width: min(100%, 44rem);
		max-height: calc(100vh - 2rem);
		overflow: auto;
		padding: 1.2rem;
	}

	:global(.gel-modal__header) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding-bottom: 1rem;
		margin-bottom: 1rem;
		border-bottom: 1px solid var(--gel-panel-border);
	}

	:global(.gel-modal__title) {
		margin: 0;
		font-size: 1.15rem;
		font-weight: 800;
		color: var(--gel-text);
	}

	:global(.gel-modal__actions) {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		padding-top: 1rem;
		margin-top: 0.5rem;
		border-top: 1px solid var(--gel-panel-border);
	}

	:global(.gel-kv) {
		display: grid;
		gap: 0.3rem;
	}

	:global(.gel-kv__label) {
		margin: 0;
		font-size: 0.85rem;
		color: var(--gel-muted);
	}

	:global(.gel-kv__value) {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--gel-text);
	}

	:global(.gel-bar-track) {
		height: 0.55rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 70%, rgba(255, 255, 255, 0.06));
		overflow: hidden;
	}

	:global(.gel-bar-fill) {
		height: 100%;
		border-radius: inherit;
		background: linear-gradient(90deg, rgba(var(--gel-accent-rgb), 0.92), rgba(var(--gel-accent-rgb), 0.58));
	}

	:global(.gel-bar-fill--amber) {
		background: linear-gradient(90deg, rgba(245, 158, 11, 0.92), rgba(251, 191, 36, 0.58));
	}

	:global(.gel-switch-row) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding: 0.25rem 0;
	}

	:global(.gel-switch-copy) {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	:global(.gel-switch-copy p) {
		margin: 0;
	}

	:global(.gel-switch-copy strong) {
		font-size: 0.96rem;
		color: var(--gel-text);
	}

	:global(.gel-switch-copy span) {
		font-size: 0.9rem;
		color: var(--gel-muted);
	}

	:global(.gel-switch) {
		position: relative;
		display: inline-flex;
		align-items: center;
		cursor: pointer;
	}

	:global(.gel-switch input) {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}

	:global(.gel-switch__track) {
		width: 3rem;
		height: 1.7rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--gel-panel-bg-strong) 72%, rgba(255, 255, 255, 0.08));
		border: 1px solid var(--gel-panel-border);
		transition: background 0.18s ease, border-color 0.18s ease;
	}

	:global(.gel-switch__thumb) {
		position: absolute;
		left: 0.22rem;
		top: 0.22rem;
		width: 1.2rem;
		height: 1.2rem;
		border-radius: 50%;
		background: #fff;
		box-shadow: 0 4px 12px rgba(15, 23, 42, 0.24);
		transition: transform 0.18s ease;
	}

	:global(.gel-switch input:checked + .gel-switch__track) {
		background: rgba(var(--gel-accent-rgb), 0.94);
		border-color: rgba(var(--gel-accent-rgb), 0.42);
	}

	:global(.gel-switch input:checked + .gel-switch__track + .gel-switch__thumb) {
		transform: translateX(1.3rem);
	}

	@keyframes gel-spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	@media (max-width: 980px) {
		:global(.gel-grid-4) {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		:global(.gel-grid-3) {
			grid-template-columns: 1fr;
		}

		:global(.gel-form-grid--two),
		:global(.gel-grid-2) {
			grid-template-columns: 1fr;
		}

		:global(.gel-toolbar__filters) {
			grid-template-columns: 1fr;
			min-width: 100%;
		}

		:global(.gel-toolbar__controls) {
			width: 100%;
			flex-wrap: wrap;
		}

		:global(.gel-toolbar__controls .gel-select),
		:global(.gel-toolbar__controls .gel-button),
		:global(.gel-toolbar__controls > a.gel-button) {
			flex: 1 1 11rem;
			width: 100%;
		}
	}

	@media (max-width: 720px) {
		.gel-shell {
			padding: 0.8rem;
		}

		.gel-shell__nav {
			padding: 1rem;
		}

		:global(.gel-page__hero),
		:global(.gel-toolbar),
		:global(.gel-card),
		:global(.gel-stat-card),
		:global(.gel-modal) {
			padding-left: 1rem;
			padding-right: 1rem;
		}

		:global(.gel-table) {
			min-width: 640px;
		}
	}
</style>
