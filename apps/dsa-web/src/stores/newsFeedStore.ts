import { create } from 'zustand';
import { newsApi } from '../api/news';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type { NewsItem, NewsStats, NewsSource, ScrapeRequest } from '../types/news';

interface NewsFeedState {
  // Data
  items: NewsItem[] | null;
  stats: NewsStats | null;
  sources: NewsSource[] | null;
  // Filters
  sourceType: 'crypto' | 'astock' | null;
  selectedCoin: string | null;
  // Loading
  isLoading: boolean;
  isLoadingStats: boolean;
  isScraping: boolean;
  // Error
  error: ParsedApiError | null;
  scrapeResult: string | null;

  // Actions
  fetchFeed: (params?: {
    page?: number;
    pageSize?: number;
    sourceType?: string;
    source?: string;
    coin?: string;
    hours?: number;
  }) => Promise<void>;
  fetchStats: () => Promise<void>;
  fetchSources: () => Promise<void>;
  triggerScrape: (payload: ScrapeRequest) => Promise<void>;
  setSourceType: (t: 'crypto' | 'astock' | null) => void;
  setSelectedCoin: (coin: string | null) => void;
  reset: () => void;
}

export const useNewsFeedStore = create<NewsFeedState>((set) => ({
  items: null,
  stats: null,
  sources: null,
  sourceType: null,
  selectedCoin: null,
  isLoading: false,
  isLoadingStats: false,
  isScraping: false,
  error: null,
  scrapeResult: null,

  fetchFeed: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const data = await newsApi.getFeed(params);
      set({ items: data.items, isLoading: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoading: false });
    }
  },

  fetchStats: async () => {
    set({ isLoadingStats: true });
    try {
      const data = await newsApi.getStats();
      set({ stats: data, isLoadingStats: false });
    } catch {
      set({ isLoadingStats: false });
    }
  },

  fetchSources: async () => {
    try {
      const data = await newsApi.listSources();
      set({ sources: data.sources });
    } catch { /* silent */ }
  },

  triggerScrape: async (payload) => {
    set({ isScraping: true, error: null, scrapeResult: null });
    try {
      const result = await newsApi.triggerScrape(payload);
      set({
        isScraping: false,
        scrapeResult: `抓取完成：${result.newArticles} 篇新文章 (${result.sourcesScraped} 来源, ${result.duplicatesSkipped} 重复跳过)`,
      });
    } catch (err) {
      set({ error: getParsedApiError(err), isScraping: false });
    }
  },

  setSourceType: (t) => set({ sourceType: t }),
  setSelectedCoin: (coin) => set({ selectedCoin: coin }),

  reset: () => set({
    items: null,
    stats: null,
    error: null,
    scrapeResult: null,
  }),
}));
