<script lang="ts">
	import * as Item from '$lib/components/ui/item/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import RankingItemDialog from '$lib/RankingItemDialog.svelte';
	import GripVertical from '@lucide/svelte/icons/grip-vertical';
	import type { RankedCompany, RankingMetric } from '$lib/types.js';

	let {
		stock,
		ranking,
		displayScore,
		selectedMetric,
		addToComparison,
		removeFromComparison,
		comparisonList
	}: {
		stock: RankedCompany;
		ranking: number;
		displayScore: number | null;
		selectedMetric: RankingMetric;
		addToComparison: (stock: RankedCompany) => void;
		removeFromComparison: (stock: RankedCompany) => void;
		comparisonList: RankedCompany[];
	} = $props();

	function isBeingCompared() {
		return comparisonList.some((item) => item.companyName === stock.companyName);
	}

	function formattedScore() {
		if (displayScore === null) return 'N/A';
		const value = Number(displayScore.toFixed(1));
		return selectedMetric === 'Overall' ? `${value} / 100` : `${value} ¢/$`;
	}

	function dragStart(event: DragEvent) {
		if (!event.dataTransfer) return;
		event.dataTransfer.effectAllowed = 'copy';
		event.dataTransfer.setData('application/x-ranked-company', stock.id);
		event.dataTransfer.setData('text/plain', stock.companyName);
	}
</script>

<div
	role="group"
	draggable="true"
	ondragstart={dragStart}
	class="flex w-full cursor-grab flex-col gap-6 active:cursor-grabbing"
	aria-label={`Rank ${ranking}: ${stock.companyName}. Drag to a comparison panel.`}
>
	<Item.Root variant="outline" class="w-full">
		<div class="pl-2 text-muted-foreground" title="Drag to compare">
			<GripVertical class="size-5" />
		</div>
		<div class="p-3 text-center">
			<p class="text-3xl">#{ranking}</p>
			<Separator />
			<span class="text-xs text-muted-foreground">
				{selectedMetric === 'Overall' ? 'Net impact' : selectedMetric}
			</span><br />
			<span
				class={displayScore !== null && displayScore >= 0 ? 'text-emerald-700' : 'text-rose-700'}
				>{formattedScore()}</span
			>
		</div>
		<Item.Content>
			<Item.Title class="text-base">{stock.companyName}</Item.Title>
			<Item.Description
				>{stock.esg.industry || stock.esg.country_of_hq || 'Company profile'}</Item.Description
			>
		</Item.Content>
		<Item.Actions>
			<Button
				disabled={comparisonList.length >= 2 && !isBeingCompared()}
				title={comparisonList.length >= 2 && !isBeingCompared()
					? 'Drag this company onto the left or right panel to replace it'
					: undefined}
				onclick={() => (isBeingCompared() ? removeFromComparison(stock) : addToComparison(stock))}
				>{isBeingCompared() ? 'Remove' : 'Compare'}</Button
			>
			<RankingItemDialog {stock} {ranking} />
		</Item.Actions>
	</Item.Root>
</div>
