<script lang="ts">
	import { writable } from 'svelte/store';
	import { Save, ShieldCheck, Bell, Info } from 'lucide-svelte';

	const showFeedbackImmediately = writable(true);
	const defaultMaxAttempts = writable(2);
	const notifyOnSubmit = writable(true);
	const notifyOnScoreDrop = writable(true);

	function saveSettings() {
		alert('Settings UI is ready. Hook this form to a backend endpoint when available.');
	}
</script>

<svelte:head>
	<title>GEL Settings | Teacher Dashboard</title>
</svelte:head>

<div class="gel-page">
	<section class="gel-panel gel-page__hero">
		<div>
			<p class="gel-page__eyebrow">GEL</p>
			<h1 class="gel-page__title">Settings</h1>
			<p class="gel-page__copy">
				Tune the defaults teachers rely on when creating assignments, then define the notification
				behavior you want once the backing settings endpoint is connected.
			</p>
		</div>
		<div class="gel-page__actions">
			<button on:click={saveSettings} class="gel-button gel-button--primary">
				<Save class="h-5 w-5" />
				<span>Save Settings</span>
			</button>
		</div>
	</section>

	<section class="gel-grid-2">
		<div class="gel-panel gel-card">
			<div class="gel-card__header">
				<ShieldCheck class="h-5 w-5" />
				<h2 class="gel-card__title">Assignment Defaults</h2>
			</div>
			<p class="gel-card__copy">Set the baseline behavior applied to newly created GEL assignments.</p>
			<div class="gel-field">
				<label for="maxAttempts">Max attempts per item</label>
				<input id="maxAttempts" class="gel-input" type="number" min="1" bind:value={$defaultMaxAttempts} />
			</div>
			<div class="gel-switch-row">
				<div class="gel-switch-copy">
					<strong>Show feedback immediately</strong>
					<span>If disabled, students only see feedback after review is complete.</span>
				</div>
				<label class="gel-switch" aria-label="Toggle immediate feedback">
					<input type="checkbox" bind:checked={$showFeedbackImmediately} />
					<span class="gel-switch__track"></span>
					<span class="gel-switch__thumb"></span>
				</label>
			</div>
		</div>

		<div class="gel-panel gel-card">
			<div class="gel-card__header">
				<Bell class="h-5 w-5" />
				<h2 class="gel-card__title">Notifications</h2>
			</div>
			<p class="gel-card__copy">Choose which teacher-facing alerts should be turned on by default.</p>
			<div class="gel-switch-row">
				<div class="gel-switch-copy">
					<strong>Student submissions</strong>
					<span>Send a digest when new attempts arrive for review.</span>
				</div>
				<label class="gel-switch" aria-label="Toggle submission notifications">
					<input type="checkbox" bind:checked={$notifyOnSubmit} />
					<span class="gel-switch__track"></span>
					<span class="gel-switch__thumb"></span>
				</label>
			</div>
			<div class="gel-switch-row">
				<div class="gel-switch-copy">
					<strong>Score drops</strong>
					<span>Alert teachers when cohort performance falls below expectations.</span>
				</div>
				<label class="gel-switch" aria-label="Toggle score drop notifications">
					<input type="checkbox" bind:checked={$notifyOnScoreDrop} />
					<span class="gel-switch__track"></span>
					<span class="gel-switch__thumb"></span>
				</label>
			</div>
		</div>
	</section>

	<div class="gel-note gel-panel">
		<Info class="h-5 w-5" />
		<div>
			<p><strong>Heads up</strong></p>
			<p>These controls are currently front-end only. Connect them to a teacher settings endpoint when it becomes available.</p>
		</div>
	</div>
</div>
