<script lang="ts">
	import * as Item from '$lib/components/ui/item/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';
	import type { RankingMetric } from '$lib/types.js';

	let {
		searchQuery = $bindable(),
		selectedMetric = $bindable()
	}: {
		searchQuery: string;
		selectedMetric: RankingMetric;
	} = $props();

	const options: RankingMetric[] = ['Overall', 'Society', 'Knowledge', 'Health', 'Environment'];
</script>

<div class="mb-5 w-full">
	<Item.Root variant="outline">
		<Item.Content class="p-3">
			<Item.Title class="text-center text-3xl tracking-tight text-primary">
				S&amp;P 500 Sustainability Ranking
			</Item.Title>
			<div class="mt-3 flex items-center gap-2">
				<Input
					type="search"
					placeholder="Search companies"
					class="min-w-0 flex-1"
					bind:value={searchQuery}
				/>

				<label class="relative shrink-0">
					<span class="sr-only">Rank companies by</span>
					<SlidersHorizontal
						class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
					/>
					<select
						bind:value={selectedMetric}
						class="h-9 min-w-40 appearance-none rounded-md border border-border bg-background pr-9 pl-9 text-sm font-medium shadow-xs transition-colors outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
						aria-label="Rank companies by"
					>
						{#each options as option (option)}
							<option value={option}>{option}</option>
						{/each}
					</select>
					<ChevronDown
						class="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
					/>
				</label>
			</div>
		</Item.Content>
	</Item.Root>
</div>
