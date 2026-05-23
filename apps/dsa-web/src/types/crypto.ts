/**
 * Crypto-related type definitions.
 * Mirror backend Pydantic schemas in camelCase.
 */

// ============ Coin / Price ============

export interface CoinPrice {
  symbol: string;
  name?: string;
  priceUsd?: number;
  change24h?: number;
  change7d?: number;
  marketCapUsd?: number;
  volume24hUsd?: number;
  rank?: number;
  sector?: string;
  updatedAt?: string;
}

export interface CoinListResponse {
  items: CoinPrice[];
  total: number;
  page: number;
  pageSize: number;
}

// ============ Signal ============

export interface SignalComponent {
  score: number;
  signal?: string;
  detail?: Record<string, unknown>;
}

export interface EnhancedTechnicalDetail {
  signal?: string;
  score?: number;
  patterns?: string;
  patternsCount?: number;
  volumeStatus?: string;
  rsiSignal?: string;
  biasSignal?: string;
  trendState?: string;
  subScores?: Record<string, number | null>;
}

export interface TimeframeDetail {
  score: number;
  rsi?: number;
  macdSignal?: string;
  bbSignal?: string;
  emaTrend?: string;
}

export interface TechnicalDetail {
  signal?: string;
  rsi?: number;
  macd?: string;
  bb?: string;
  ema?: string;
  score: number;
  taScore?: number;
  enhancedScore?: number;
  alignment?: string;
  enhanced?: EnhancedTechnicalDetail;
  timeframes?: Record<string, TimeframeDetail>;
}

export interface CompositeSignalResponse {
  coin: string;
  composite: number;
  signal: SignalLabel;
  signalCn: string;
  components: Record<string, SignalComponent>;
  weights: Record<string, number>;
}

export type SignalLabel = 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'strong_sell';

export interface SignalHistoryItem {
  id: number;
  assetCode: string;
  compositeScore: number;
  signalLabel: string;
  createdAt?: string;
}

export interface SignalHistoryResponse {
  items: SignalHistoryItem[];
  total: number;
  page: number;
  pageSize: number;
}

// ============ Fear & Greed ============

export interface FearGreedItem {
  value: number;
  label: string;
  signal: string;
  score: number;
  timestamp?: string;
}

export interface FearGreedHistoryItem {
  timestamp: string;
  value: number;
  label: string;
}

export interface FearGreedHistoryResponse {
  items: FearGreedHistoryItem[];
  latest?: FearGreedItem;
  total: number;
  days: number;
}

// ============ Sector ============

export interface CryptoSector {
  key: string;
  name: string;
  coins: string[];
  coinCount: number;
}

export interface SectorListResponse {
  sectors: CryptoSector[];
  totalSectors: number;
  totalCoins: number;
}

// ============ Macro ============

export interface MacroSignal {
  name: string;
  latestValue?: number;
  score?: number;
  signal?: string;
}

export interface MacroSummaryResponse {
  compositeScore: number;
  compositeLabel: string;
  indicators: Record<string, MacroSignal>;
  summary?: string;
}

// ============ OHLCV ============

export interface OHLCVItem {
  timestamp: string;
  open?: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
}

export interface OHLCVResponse {
  coin: string;
  interval: string;
  items: OHLCVItem[];
  count: number;
}

// ============ Patterns ============

export interface DetectedPattern {
  pattern: string;
  type: string;
  strength?: string;
  desc?: string;
  candleOffset?: number;
}

export interface PatternResponse {
  coin: string;
  patternsCount: number;
  patternSignal?: string;
  patternScore?: number;
  summary?: string;
  currentPrice?: number;
  patterns: DetectedPattern[];
}

// ============ On-demand analysis ============

export interface AnalyzeCoinRequest {
  symbol: string;
  includeNews?: boolean;
  includeSignals?: boolean;
}

export interface AnalyzeCoinResponse {
  coin: string;
  signal?: CompositeSignalResponse;
  newsCount?: number;
  patterns?: PatternResponse;
  analysisTime?: string;
  status: 'ok' | 'partial' | 'error';
}
