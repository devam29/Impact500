<script lang="ts">
	import Ranking from '$lib/Ranking.svelte';
	import ComparisonPanel from '$lib/ComparisonPanel.svelte';
	import sp500Companies from '../upright_metrics/sp500_metrics.json';
	import type {
		ImpactAmount,
		ImpactMetric,
		RankedCompany,
		Sp500CompanyRecord,
		UprightCompany
	} from '$lib/types.js';

	function text(value: unknown): string {
		return value === null || value === undefined ? '' : String(value);
	}

	function impactAmount(value: Partial<ImpactAmount> | undefined): ImpactAmount {
		return {
			cost: text(value?.cost),
			benefit: text(value?.benefit),
			unit: text(value?.unit) || 'cents per dollar of revenue'
		};
	}

	function normalizeUpright(record: Sp500CompanyRecord): UprightCompany {
		const source = record.upright;
		const categoryTotals = Object.fromEntries(
			Object.entries(source.category_totals ?? {}).map(([category, total]) => [
				category,
				impactAmount(total)
			])
		);
		const metrics: ImpactMetric[] = (source.metrics ?? []).map((metric) => ({
			category: text(metric.category),
			metric: text(metric.metric),
			...impactAmount(metric)
		}));

		return {
			company: text(source.company) || record.security,
			industry: text(source.industry) || record.gics_sub_industry || record.gics_sector,
			screener_revenue_musd: text(source.screener_revenue_musd),
			largest_cost: text(source.largest_cost),
			largest_benefit: text(source.largest_benefit),
			screener_net_impact_ratio: text(source.screener_net_impact_ratio),
			screener_percentile: text(source.screener_percentile),
			upright_url: text(source.upright_url),
			country_of_hq: record.headquarters_location || text(source.country_of_hq),
			revenue:
				text(source.revenue) ||
				(source.revenue_musd === null || source.revenue_musd === undefined
					? ''
					: `${new Intl.NumberFormat().format(Number(source.revenue_musd))} M$`),
			employee_count: text(source.employee_count),
			net_impact_ratio: text(source.net_impact_ratio),
			rank_top_percent: text(source.rank_top_percent),
			benchmark_percent_lower: text(source.benchmark_percent_lower),
			model_release: text(source.model_release),
			top_negative_impact_explanation: text(source.top_negative_impact_explanation),
			top_positive_impact_explanation: text(source.top_positive_impact_explanation),
			category_totals: categoryTotals,
			metrics,
			scraped_at_utc: text(source.scraped_at_utc),
			source_index: text(source.source_index),
			source_url: text(source.source_url)
		};
	}

	const unrankedCompanies = (sp500Companies as unknown as Sp500CompanyRecord[]).map((record) => {
		const esg = normalizeUpright(record);
		return {
			id: record.ticker,
			companyName: record.security,
			stockName: record.ticker,
			score: record.scores.environmental_composite_score,
			percentile: null,
			esg,
			co2: record.co2
		};
	});

	const scores = unrankedCompanies.flatMap((company) =>
		company.score === null ? [] : [company.score]
	);

	function percentile(score: number | null): number | null {
		if (score === null || scores.length < 2) return null;
		const lowerScores = scores.filter((candidate) => candidate < score).length;
		return (lowerScores / (scores.length - 1)) * 100;
	}

	const data: RankedCompany[] = unrankedCompanies
		.map((company) => ({ ...company, percentile: percentile(company.score) }))
		.sort((left, right) => (right.score ?? -Infinity) - (left.score ?? -Infinity));

	let leftCompany = $state<RankedCompany | null>(null);
	let rightCompany = $state<RankedCompany | null>(null);
	let comparisonList = $derived(
		[leftCompany, rightCompany].filter((company): company is RankedCompany => company !== null)
	);

	function addToComparison(company: RankedCompany) {
		if (comparisonList.some((item) => item.companyName === company.companyName)) return;
		if (!leftCompany) leftCompany = company;
		else if (!rightCompany) rightCompany = company;
	}

	function removeFromComparison(company: RankedCompany) {
		if (leftCompany?.companyName === company.companyName) leftCompany = null;
		if (rightCompany?.companyName === company.companyName) rightCompany = null;
	}

	function dropCompany(side: 'left' | 'right', identifier: string) {
		const company = data.find((item) => item.id === identifier);
		if (!company) return;

		if (side === 'left') {
			if (rightCompany?.companyName === company.companyName) rightCompany = null;
			leftCompany = company;
		} else {
			if (leftCompany?.companyName === company.companyName) leftCompany = null;
			rightCompany = company;
		}
	}
</script>

<main
	class="mx-auto grid min-h-screen max-w-[112rem] grid-cols-1 gap-5 p-4 sm:p-6 xl:h-screen xl:min-h-0 xl:grid-cols-[minmax(34rem,42rem)_minmax(42rem,1fr)]"
>
	<Ranking {data} {addToComparison} {removeFromComparison} {comparisonList} />
	<section class="grid min-h-0 grid-cols-1 gap-3 sm:grid-cols-2" aria-label="Company comparison">
		<ComparisonPanel
			company={leftCompany}
			side="left"
			onDropCompany={(identifier) => dropCompany('left', identifier)}
			onRemove={() => (leftCompany = null)}
		/>
		<ComparisonPanel
			company={rightCompany}
			side="right"
			onDropCompany={(identifier) => dropCompany('right', identifier)}
			onRemove={() => (rightCompany = null)}
		/>
	</section>
</main>
