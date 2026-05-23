import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  NewsDetailResponse,
  NewsListResponse,
  NewsQueryParams,
  NewsSourceListResponse,
  NewsStats,
  ScrapeRequest,
  ScrapeResponse,
} from '../types/news';

export const newsApi = {
  /** Get unified news feed. */
  getFeed: async (params?: NewsQueryParams): Promise<NewsListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/news/feed', {
      params: params ? {
        page: params.page,
        page_size: params.pageSize,
        source_type: params.sourceType,
        source: params.source,
        coin: params.coin,
        hours: params.hours,
      } : undefined,
    });
    return toCamelCase<NewsListResponse>(response.data);
  },

  /** Get single news detail. */
  getDetail: async (newsId: string): Promise<NewsDetailResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/news/feed/${newsId}`);
    return toCamelCase<NewsDetailResponse>(response.data);
  },

  /** List available news sources. */
  listSources: async (): Promise<NewsSourceListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/news/sources');
    return toCamelCase<NewsSourceListResponse>(response.data);
  },

  /** Get news statistics. */
  getStats: async (): Promise<NewsStats> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/news/stats');
    return toCamelCase<NewsStats>(response.data);
  },

  /** Trigger news scraping. */
  triggerScrape: async (payload: ScrapeRequest): Promise<ScrapeResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/news/scrape', {
      source_type: payload.sourceType,
      max_articles: payload.maxArticles ?? 20,
      analyze: payload.analyze ?? true,
    });
    return toCamelCase<ScrapeResponse>(response.data);
  },
};
