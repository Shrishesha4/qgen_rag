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

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL</p>
			<h1 class="text-3xl font-semibold text-white">Settings</h1>
			<p class="text-slate-200/80">Tune defaults for new GEL assignments and notifications.</p>
		</div>
		<button
			on:click={saveSettings}
			class="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20"
		>
			<Save class="h-5 w-5" />
			<span>Save</span>
		</button>
	</div>

	<div class="grid md:grid-cols-2 gap-6">
		<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-4">
			<div class="flex items-center space-x-2">
				<ShieldCheck class="h-5 w-5 text-rose-200" />
				<h2 class="text-lg font-semibold text-white">Assignment defaults</h2>
			</div>
			<label class="block text-sm text-slate-200/90" for="maxAttempts">Max attempts per item</label>
			<input
				type="number"
				min="1"
				bind:value={$defaultMaxAttempts}
				id="maxAttempts"
				class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
			/>

			<div class="flex items-center justify-between py-2">
				<div>
					<p class="text-sm font-medium text-white">Show feedback immediately</p>
					<p class="text-sm text-slate-300/80">If off, students see feedback after review.</p>
				</div>
				<label class="relative inline-flex items-center cursor-pointer">
					<input type="checkbox" class="sr-only peer" bind:checked={$showFeedbackImmediately}>
					<div class="w-11 h-6 bg-white/10 border border-white/20 rounded-full peer-checked:bg-rose-500 transition"></div>
					<div class="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition peer-checked:translate-x-5"></div>
				</label>
			</div>
		</div>

		<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-4">
			<div class="flex items-center space-x-2">
				<Bell class="h-5 w-5 text-rose-200" />
				<h2 class="text-lg font-semibold text-white">Notifications</h2>
			</div>
			<div class="flex items-center justify-between py-2">
				<div>
					<p class="text-sm font-medium text-white">When students submit attempts</p>
					<p class="text-sm text-slate-300/80">Email digest for new submissions.</p>
				</div>
				<label class="relative inline-flex items-center cursor-pointer">
					<input type="checkbox" class="sr-only peer" bind:checked={$notifyOnSubmit}>
					<div class="w-11 h-6 bg-white/10 border border-white/20 rounded-full peer-checked:bg-rose-500 transition"></div>
					<div class="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition peer-checked:translate-x-5"></div>
				</label>
			</div>
			<div class="flex items-center justify-between py-2">
				<div>
					<p class="text-sm font-medium text-white">Score drops</p>
					<p class="text-sm text-slate-300/80">Alert when average drops below expectations.</p>
				</div>
				<label class="relative inline-flex items-center cursor-pointer">
					<input type="checkbox" class="sr-only peer" bind:checked={$notifyOnScoreDrop}>
					<div class="w-11 h-6 bg-white/10 border border-white/20 rounded-full peer-checked:bg-rose-500 transition"></div>
					<div class="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition peer-checked:translate-x-5"></div>
				</label>
			</div>
		</div>
	</div>

	<div class="glass-panel border border-amber-200/40 bg-amber-900/30 rounded-xl p-4 flex items-start space-x-3">
		<Info class="h-5 w-5 text-amber-200 mt-0.5" />
		<div>
			<p class="text-sm text-amber-100 font-semibold">Heads up</p>
			<p class="text-sm text-amber-100/90">
				These controls are front-end only for now. Wire them to a settings endpoint when it becomes available.
			</p>
		</div>
	</div>
</div>
