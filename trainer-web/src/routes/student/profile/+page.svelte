
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { logout } from '$lib/api/auth';
	import { session } from '$lib/session';
	import {
		AlertCircle,
		User2,
		Mail,
		Globe,
		CalendarDays,
		ShieldCheck,
		BookmarkCheck,
		Hash,
		Sparkles,
		Activity,
		CheckCircle,
		MapPin,
		Users
	} from 'lucide-svelte';

	type UserResponse = {
		id: string;
		email: string;
		username: string;
		full_name?: string | null;
		avatar_url?: string | null;
		timezone: string;
		language: string;
		role: string;
		can_manage_groups: boolean;
		can_generate: boolean;
		can_vet: boolean;
		is_active: boolean;
		created_at: string;
		last_login_at?: string | null;
		preferences?: Record<string, unknown> | null;
		grade?: string | null;
		cohort?: string | null;
		consent_given: boolean;
		consent_given_at?: string | null;
	};

	type StudentProfileResponse = {
		user: UserResponse;
		total_assignments: number;
		completed_attempts: number;
		average_score: number | null;
		streak_days: number;
	};

	let data: StudentProfileResponse | null = null;
	let isLoading = true;
	let error: string | null = null;

	onMount(async () => {
		await loadProfile();
	});

	async function loadProfile() {
		isLoading = true;
		error = null;
		try {
			data = await apiFetch<StudentProfileResponse>('/gel/student/profile');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load profile';
		} finally {
			isLoading = false;
		}
	}

	function formatDate(value: string | null | undefined): string {
		if (!value) return '—';
		return new Date(value).toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	function formatScore(value: number | null): string {
		if (value === null || Number.isNaN(value)) return '—';
		return `${value.toFixed(0)}%`;
	}

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/');
	}
</script>

<div class="page-container student-shell space-y-8">
	<section class="glass-panel gradient-card">
		<div class="identity">
			<div class="avatar-pill">
				<User2 class="h-7 w-7" />
			</div>
			<div>
				<p class="eyebrow">Profile</p>
				<h1 class="hero">{data?.user.full_name || data?.user.username || 'Your profile'}</h1>
				<p class="muted">See your account details and progress snapshot.</p>
			</div>
		</div>
		<div class="hero-metrics">
			<div>
				<p class="summary-value">{data?.streak_days ?? 0}</p>
				<p class="summary-label">Day streak</p>
			</div>
			<div>
				<p class="summary-value">{formatScore(data?.average_score ?? null)}</p>
				<p class="summary-label">Average score</p>
			</div>
			<button class="logout-btn" on:click={handleLogout}>Sign out</button>
		</div>
	</section>

	{#if isLoading}
		<div class="center-state">
			<div class="spinner"></div>
			<p class="muted">Loading profile...</p>
		</div>
	{:else if error}
		<div class="glass-panel error-panel">
			<div class="flex gap-2 items-center text-red-200">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="pill ghost" on:click={loadProfile}>Try again</button>
		</div>
	{:else if data}
		<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
			<div class="glass-panel stat-card">
				<div class="icon-pill"><BookmarkCheck class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.total_assignments}</p>
					<p class="stat-label">Assignments</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><CheckCircle class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.completed_attempts}</p>
					<p class="stat-label">Completed attempts</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><Sparkles class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{formatScore(data.average_score)}</p>
					<p class="stat-label">Average score</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><Activity class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.streak_days}</p>
					<p class="stat-label">Day streak</p>
				</div>
			</div>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
			<section class="glass-panel detail-card lg:col-span-2">
				<header class="section-head">
					<div>
						<p class="text-white font-semibold">Account</p>
						<p class="muted">Basics and contact</p>
					</div>
				</header>
				<div class="detail-grid">
					<div class="detail-row">
						<User2 class="icon" />
						<div>
							<p class="detail-label">Username</p>
							<p class="detail-value">{data.user.username}</p>
						</div>
					</div>
					<div class="detail-row">
						<Mail class="icon" />
						<div>
							<p class="detail-label">Email</p>
							<p class="detail-value">{data.user.email}</p>
						</div>
					</div>
					<div class="detail-row">
						<Globe class="icon" />
						<div>
							<p class="detail-label">Language</p>
							<p class="detail-value">{data.user.language}</p>
						</div>
					</div>
					<div class="detail-row">
						<MapPin class="icon" />
						<div>
							<p class="detail-label">Timezone</p>
							<p class="detail-value">{data.user.timezone}</p>
						</div>
					</div>
				</div>
			</section>

			<section class="glass-panel detail-card">
				<header class="section-head">
					<div>
						<p class="text-white font-semibold">Learning</p>
						<p class="muted">Cohort and grade</p>
					</div>
				</header>
				<div class="detail-grid">
					<div class="detail-row">
						<Hash class="icon" />
						<div>
							<p class="detail-label">Cohort</p>
							<p class="detail-value">{data.user.cohort || '—'}</p>
						</div>
					</div>
					<div class="detail-row">
						<BookmarkCheck class="icon" />
						<div>
							<p class="detail-label">Grade</p>
							<p class="detail-value">{data.user.grade || '—'}</p>
						</div>
					</div>
					<div class="detail-row">
						<ShieldCheck class="icon" />
						<div>
							<p class="detail-label">Consent</p>
							<p class="detail-value">
								{data.user.consent_given ? 'Given' : 'Not given'}
								{#if data.user.consent_given_at}
									<span class="muted"> • {formatDate(data.user.consent_given_at)}</span>
								{/if}
							</p>
						</div>
					</div>
				</div>
			</section>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<section class="glass-panel detail-card">
				<header class="section-head">
					<div>
						<p class="text-white font-semibold">Activity</p>
						<p class="muted">Recent and lifetime</p>
					</div>
				</header>
				<div class="detail-grid">
					<div class="detail-row">
						<Activity class="icon" />
						<div>
							<p class="detail-label">Last login</p>
							<p class="detail-value">{formatDate(data.user.last_login_at)}</p>
						</div>
					</div>
					<div class="detail-row">
						<CalendarDays class="icon" />
						<div>
							<p class="detail-label">Joined</p>
							<p class="detail-value">{formatDate(data.user.created_at)}</p>
						</div>
					</div>
				</div>
			</section>

			<section class="glass-panel detail-card">
				<header class="section-head">
					<div>
						<p class="text-white font-semibold">Permissions</p>
						<p class="muted">Capabilities for your role</p>
					</div>
				</header>
				<div class="pill-grid">
					<span class={`pill ${data.user.can_generate ? 'yes' : 'no'}`}>
						<Sparkles class="h-4 w-4" /> Generate
					</span>
					<span class={`pill ${data.user.can_vet ? 'yes' : 'no'}`}>
						<CheckCircle class="h-4 w-4" /> Vet
					</span>
					<span class={`pill ${data.user.can_manage_groups ? 'yes' : 'no'}`}>
						<Users class="h-4 w-4" /> Manage groups
					</span>
				</div>
			</section>
		</div>
	{/if}
</div>

<style>
	.page-container {
		max-width: 1180px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
	}

	.glass-panel {
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 18px;
		padding: 18px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
		backdrop-filter: blur(18px);
	}

	.gradient-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.25rem;
		background: radial-gradient(circle at 20% 20%, rgba(99, 102, 241, 0.28), transparent 32%),
			radial-gradient(circle at 80% 10%, rgba(45, 212, 191, 0.26), transparent 34%),
			linear-gradient(135deg, rgba(17, 24, 39, 0.92), rgba(15, 23, 42, 0.86));
	}

	.identity {
		display: flex;
		align-items: center;
		gap: 0.9rem;
	}

	.avatar-pill {
		width: 46px;
		height: 46px;
		border-radius: 14px;
		display: grid;
		place-items: center;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: #fff;
	}

	.eyebrow {
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.72);
	}

	.hero {
		margin: 2px 0 6px;
		color: #fff;
		font-size: clamp(1.75rem, 2.2vw, 2.2rem);
		font-weight: 700;
	}

	.muted {
		color: rgba(255, 255, 255, 0.72);
		margin: 0;
	}

	.hero-metrics {
		display: flex;
		gap: 1.5rem;
		align-items: center;
	}

	.logout-btn {
		margin-left: auto;
		padding: 10px 14px;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.18);
		background: rgba(255, 255, 255, 0.08);
		color: #fff;
		font-weight: 700;
		transition: 140ms ease;
		cursor: pointer;
	}

	.logout-btn:hover {
		border-color: rgba(255, 255, 255, 0.32);
		background: rgba(255, 255, 255, 0.16);
	}

	.summary-value {
		margin: 0;
		font-size: 1.9rem;
		font-weight: 700;
		color: #fff;
	}

	.summary-label {
		margin: 0;
		color: rgba(255, 255, 255, 0.7);
		font-size: 0.95rem;
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.5rem;
		padding: 2rem 1.5rem;
		text-align: center;
	}

	.spinner {
		width: 44px;
		height: 44px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.18);
		border-top-color: rgba(255, 255, 255, 0.8);
		animation: spin 0.8s linear infinite;
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 16px;
	}

	.stat-value {
		margin: 0;
		font-size: 1.6rem;
		font-weight: 700;
		color: #fff;
	}

	.stat-label {
		margin: 0;
		color: rgba(255, 255, 255, 0.72);
		font-size: 0.95rem;
	}

	.icon-pill {
		width: 44px;
		height: 44px;
		border-radius: 14px;
		display: grid;
		place-items: center;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: #fff;
	}

	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.detail-card {
		padding: 18px;
	}

	.detail-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 12px;
	}

	.detail-row {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 10px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.detail-row:last-child {
		border-bottom: none;
	}

	.icon {
		width: 18px;
		height: 18px;
		color: rgba(255, 255, 255, 0.72);
		flex-shrink: 0;
	}

	.detail-label {
		margin: 0;
		color: rgba(255, 255, 255, 0.6);
		font-size: 0.9rem;
	}

	.detail-value {
		margin: 2px 0 0;
		color: #fff;
		font-weight: 600;
	}

	.pill-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		font-weight: 600;
		color: #fff;
	}

	.pill.yes { background: rgba(16, 185, 129, 0.18); border-color: rgba(16, 185, 129, 0.35); }
	.pill.no { background: rgba(239, 68, 68, 0.14); border-color: rgba(239, 68, 68, 0.32); }

	.ghost {
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: #fff;
		cursor: pointer;
		transition: 140ms ease;
	}

	.ghost:hover {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(var(--theme-primary-rgb), 0.12);
	}

	.error-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	@media (max-width: 900px) {
		.hero-metrics { flex-wrap: wrap; }
		.detail-grid { grid-template-columns: 1fr; }
	}

	:global([data-color-mode='light']) .student-shell {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .gradient-card {
		background: linear-gradient(135deg, #f8fafc, #e0f2fe);
	}

	:global([data-color-mode='light']) .student-shell .glass-panel {
		background: rgba(255, 255, 255, 0.92);
		border-color: rgba(15, 23, 42, 0.08);
		box-shadow: 0 18px 50px rgba(15, 23, 42, 0.14);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .hero,
	:global([data-color-mode='light']) .student-shell .summary-value,
	:global([data-color-mode='light']) .student-shell .detail-value {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .eyebrow,
	:global([data-color-mode='light']) .student-shell .muted,
	:global([data-color-mode='light']) .student-shell .summary-label,
	:global([data-color-mode='light']) .student-shell .stat-label,
	:global([data-color-mode='light']) .student-shell .detail-label,
	:global([data-color-mode='light']) .student-shell .icon,
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/60),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/70),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/80),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/50) {
		color: #475569;
	}

	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white) {
		color: #0f172a !important;
	}

	:global([data-color-mode='light']) .student-shell .avatar-pill,
	:global([data-color-mode='light']) .student-shell .icon-pill {
		background: #e2e8f0;
		border-color: rgba(15, 23, 42, 0.12);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .pill {
		border-color: rgba(15, 23, 42, 0.12);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .pill.yes {
		background: rgba(16, 185, 129, 0.14);
		border-color: rgba(16, 185, 129, 0.32);
	}

	:global([data-color-mode='light']) .student-shell .pill.no {
		background: rgba(239, 68, 68, 0.14);
		border-color: rgba(239, 68, 68, 0.32);
	}

	:global([data-color-mode='light']) .student-shell .logout-btn {
		border-color: rgba(15, 23, 42, 0.12);
		background: rgba(15, 23, 42, 0.04);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .ghost {
		border-color: rgba(15, 23, 42, 0.12);
		background: rgba(15, 23, 42, 0.04);
		color: #0f172a;
	}
</style>
