<script lang="ts">
	import RankingItem from '$lib/RankingItem.svelte';
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import type { RankedCompany, RankingMetric } from '$lib/types.js';

	let {
		searchQuery,
		selectedMetric,
		data,
		addToComparison,
		removeFromComparison,
		comparisonList
	}: {
		searchQuery: string;
		selectedMetric: RankingMetric;
		data: RankedCompany[];
		addToComparison: (stock: RankedCompany) => void;
		removeFromComparison: (stock: RankedCompany) => void;
		comparisonList: RankedCompany[];
	} = $props();

	function stockMatchesSearchQuery(stock: RankedCompany) {
		return !searchQuery || stock.companyName.toLowerCase().includes(searchQuery.toLowerCase());
	}

	function impactValue(value: string): number {
		const parsed = Number.parseFloat(value);
		return Number.isFinite(parsed) ? parsed : 0;
	}

	function scoreForMetric(stock: RankedCompany, metric: RankingMetric): number | null {
		if (metric === 'Overall') return stock.score;

		const category = stock.esg.category_totals[metric];
		if (!category || (!category.cost && !category.benefit)) return null;

		return impactValue(category.cost) + impactValue(category.benefit);
	}

	let rankedData = $derived.by(() =>
		[...data].sort(
			(left, right) =>
				(scoreForMetric(right, selectedMetric) ?? -Infinity) -
				(scoreForMetric(left, selectedMetric) ?? -Infinity)
		)
	);

	let visibleData = $derived.by(() =>
		rankedData
			.map((stock, index) => ({ stock, ranking: index + 1 }))
			.filter(({ stock }) => stockMatchesSearchQuery(stock))
	);
</script>

<div class="min-h-0 flex-1">
	<ScrollArea class="h-full rounded-md border">
		{#each visibleData as { stock, ranking } (stock.id)}
			<RankingItem
				{stock}
				{ranking}
				displayScore={scoreForMetric(stock, selectedMetric)}
				{selectedMetric}
				{addToComparison}
				{removeFromComparison}
				{comparisonList}
			/>
		{/each}
	</ScrollArea>
</div>
