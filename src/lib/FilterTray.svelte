<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import type { RankingMetric } from '$lib/types.js';

	let { value = $bindable(), onSelect }: { value: RankingMetric; onSelect?: () => void } = $props();

	const options: RankingMetric[] = ['Overall', 'Society', 'Knowledge', 'Health', 'Environment'];
</script>

<div class="mt-2 ml-auto w-48 rounded-lg border border-border bg-background p-1 shadow-sm">
	<p class="px-2 py-1 text-xs font-medium text-muted-foreground">Rank by</p>
	<div class="flex flex-col gap-0.5" role="radiogroup" aria-label="Ranking metric">
		{#each options as option}
			<Button
				size="sm"
				variant={value === option ? 'default' : 'ghost'}
				class="w-full justify-start"
				role="radio"
				aria-checked={value === option}
				onclick={() => {
					value = option;
					onSelect?.();
				}}
			>
				{option}
			</Button>
		{/each}
	</div>
</div>
