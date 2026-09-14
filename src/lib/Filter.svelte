<script lang="ts">
  import * as Select from "$lib/components/ui/select/index.js";

  let { filterOptions, value = $bindable(), label } = $props();
</script>
<div class="flex flex-row gap-2 items-center">
  <p>{label}</p>
  <Select.Root type="single" name="favoriteFruit" bind:value>
    <Select.Trigger class="w-[180px]">
      <Select.Value placeholder="Method" />
    </Select.Trigger>
    <Select.Content>
      <Select.Group>
	{#each filterOptions as option (option)}
          <Select.Item value={option}>
            {option}
          </Select.Item>
	{/each}
      </Select.Group>
    </Select.Content>
  </Select.Root>
</div>
