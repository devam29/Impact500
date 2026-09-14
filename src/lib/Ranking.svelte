<script lang="ts">
	import RankingList from '$lib/RankingList.svelte';
	import RankingHeader from '$lib/RankingHeader.svelte';
	import type { RankingMetric } from '$lib/types.js';

	let { data, addToComparison, removeFromComparison, comparisonList } = $props();
	let searchQuery = $state('');
	let selectedMetric = $state<RankingMetric>('Overall');
</script>

<section class="flex min-h-0 w-full flex-col">
	<RankingHeader bind:searchQuery bind:selectedMetric />

	<RankingList
		{searchQuery}
		{selectedMetric}
		{data}
		{addToComparison}
		{removeFromComparison}
		{comparisonList}
	/>
</section>
