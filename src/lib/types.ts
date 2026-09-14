export interface ImpactAmount {
	cost: string;
	benefit: string;
	unit: string;
}

export interface ImpactMetric extends ImpactAmount {
	category: string;
	metric: string;
}

export interface EmissionsEstimate {
	method?: string;
	sector_used?: string;
	peer_count?: string;
	notes?: string;
}

export interface EmissionsScope {
	tco2e: number | null;
	is_estimated: boolean;
	estimate: EmissionsEstimate | null;
}

export interface CarbonData {
	data_source: string;
	report_url: string;
	is_estimated: boolean;
	notes: string;
	scope1: EmissionsScope;
	scope2: EmissionsScope & {
		location_tco2e: number | null;
		market_tco2e: number | null;
	};
}

export interface EnvironmentalScores {
	environmental_composite_score: number | null;
}

export interface Sp500CompanyRecord {
	ticker: string;
	security: string;
	gics_sector: string;
	gics_sub_industry: string;
	headquarters_location: string;
	co2: CarbonData;
	scores: EnvironmentalScores;
	upright: Partial<UprightCompany> & {
		revenue_musd?: number | string | null;
		is_estimated?: boolean;
	};
}

export interface UprightCompany {
	company: string;
	industry: string;
	screener_revenue_musd: string;
	largest_cost: string;
	largest_benefit: string;
	screener_net_impact_ratio: string;
	screener_percentile: string;
	upright_url: string;
	country_of_hq: string;
	revenue: string;
	employee_count: string;
	net_impact_ratio: string;
	rank_top_percent: string;
	benchmark_percent_lower: string;
	model_release: string;
	top_negative_impact_explanation: string;
	top_positive_impact_explanation: string;
	category_totals: Record<string, ImpactAmount>;
	metrics: ImpactMetric[];
	scraped_at_utc: string;
	source_index: string;
	source_url: string;
}

export interface RankedCompany {
	id: string;
	companyName: string;
	stockName: string;
	score: number | null;
	percentile: number | null;
	esg: UprightCompany;
	co2: CarbonData;
}

export type RankingMetric = 'Overall' | 'Society' | 'Knowledge' | 'Health' | 'Environment';
