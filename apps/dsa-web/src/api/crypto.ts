import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  AnalyzeCoinRequest,
  AnalyzeCoinResponse,
  CoinListResponse,
  CoinPrice,
  CompositeSignalResponse,
  FearGreedHistoryResponse,
  FearGreedItem,
  MacroSummaryResponse,
  OHLCVResponse,
  PatternResponse,
  SectorListResponse,
  SignalHistoryResponse,
} from '../types/crypto';

export const cryptoApi = {
  /** List tracked coins with latest prices. */
  listCoins: async (params?: {
    page?: number;
    pageSize?: number;
    sector?: string;
    sortBy?: string;
  }): Promise<CoinListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/crypto/coins', { params });
    return toCamelCase<CoinListResponse>(response.data);
  },

  /** Get single coin detail. */
  getCoin: async (symbol: string): Promise<CoinPrice> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/crypto/coins/${symbol}`);
    return toCamelCase<CoinPrice>(response.data);
  },

  /** Get composite trading signal for a coin. */
  getSignals: async (symbol: string): Promise<CompositeSignalResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/crypto/coins/${symbol}/signals`);
    return toCamelCase<CompositeSignalResponse>(response.data);
  },

  /** Get signal history for a coin. */
  getSignalHistory: async (
    symbol: string,
    params?: { page?: number; pageSize?: number; days?: number },
  ): Promise<SignalHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/crypto/coins/${symbol}/signals/history`,
      { params },
    );
    return toCamelCase<SignalHistoryResponse>(response.data);
  },

  /** Get current Fear & Greed index. */
  getFearGreed: async (): Promise<FearGreedItem> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/crypto/fear-greed');
    return toCamelCase<FearGreedItem>(response.data);
  },

  /** Get Fear & Greed history. */
  getFearGreedHistory: async (days?: number): Promise<FearGreedHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/crypto/fear-greed/history', {
      params: { days },
    });
    return toCamelCase<FearGreedHistoryResponse>(response.data);
  },

  /** List crypto sectors. */
  listSectors: async (): Promise<SectorListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/crypto/sectors');
    return toCamelCase<SectorListResponse>(response.data);
  },

  /** Get macro indicators. */
  getMacro: async (): Promise<MacroSummaryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/crypto/macro');
    return toCamelCase<MacroSummaryResponse>(response.data);
  },

  /** Get OHLCV price history. */
  getOHLCV: async (
    symbol: string,
    params?: { interval?: string; days?: number },
  ): Promise<OHLCVResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/crypto/coins/${symbol}/ohlcv`,
      { params },
    );
    return toCamelCase<OHLCVResponse>(response.data);
  },

  /** Detect candlestick patterns. */
  getPatterns: async (symbol: string, days?: number): Promise<PatternResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/crypto/coins/${symbol}/patterns`,
      { params: { days } },
    );
    return toCamelCase<PatternResponse>(response.data);
  },

  /** Trigger on-demand analysis for a coin. */
  analyzeCoin: async (payload: AnalyzeCoinRequest): Promise<AnalyzeCoinResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/crypto/analyze', {
      symbol: payload.symbol,
      include_news: payload.includeNews ?? true,
      include_signals: payload.includeSignals ?? true,
    });
    return toCamelCase<AnalyzeCoinResponse>(response.data);
  },
};
