/**
 * News-related type definitions.
 * Unified news feed for crypto + A-share news.
 */

// ============ News Item ============

export interface NewsItem {
  id?: number;
  newsId: string;
  source: string;
  sourceType: 'crypto' | 'astock';
  title: string;
  url?: string;
  summary?: string;
  content?: string;
  publishedAt?: string;
  scrapedAt?: string;
  // Crypto-specific
  mentionedCoins?: string[];
  sentimentScore?: number;
  sentimentLabel?: string;
  eventType?: string;
  aiAnalysis?: string;
  // A-stock-specific
  affectedStocks?: string[];
  aSentiment?: string;
}

export interface NewsListResponse {
  items: NewsItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface NewsDetailResponse {
  item: NewsItem;
  relatedNews: NewsItem[];
}

// ============ Sources ============

export interface NewsSource {
  source: string;
  sourceType: string;
  description?: string;
  articleCount?: number;
  lastFetch?: string;
}

export interface NewsSourceListResponse {
  sources: NewsSource[];
  totalSources: number;
}

// ============ Stats ============

export interface NewsStats {
  totalArticles: number;
  articles24h: number;
  articles7d: number;
  bySource: Record<string, number>;
  bySentiment: Record<string, number>;
  topCoins: Record<string, number>;
  topStocks: Record<string, number>;
}

// ============ Scrape ============

export interface ScrapeRequest {
  sourceType: 'crypto' | 'astock' | 'both';
  maxArticles?: number;
  analyze?: boolean;
}

export interface ScrapeResponse {
  status: 'ok' | 'partial' | 'error';
  sourceType: string;
  sourcesScraped: number;
  totalFetched: number;
  newArticles: number;
  duplicatesSkipped: number;
  errors: string[];
  elapsedSeconds?: number;
}

// ============ Query params ============

export interface NewsQueryParams {
  page?: number;
  pageSize?: number;
  sourceType?: string;
  source?: string;
  coin?: string;
  hours?: number;
}
