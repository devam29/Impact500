<script lang="ts">
  import * as Item from "$lib/components/ui/item/index.js";
  import { Separator } from "$lib/components/ui/separator/index.js";

  let { hover, comparisonList } = $props();
</script>

<div class="flex w-full max-w-md flex-col gap-6">
  <Item.Root variant="outline">
    <Item.Content>
      {#if comparisonList.length !== 0}
	<Item.Title>Comparison</Item.Title>
	{#each comparisonList as company (company)}
	  {company.companyName}
	{/each}
	
	<Separator/>
      {/if}
      
      {#if hover === null}
	No data
      {:else}
	<Item.Title>{hover.companyName}</Item.Title>
	<Item.Description
	  >
	  
	  Overall Score: {hover.score}
	</Item.Description
	  >
	{/if}
      </Item.Content>
  </Item.Root>
</div>
