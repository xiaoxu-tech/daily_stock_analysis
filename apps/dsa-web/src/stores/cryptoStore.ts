import { create } from 'zustand';
import { cryptoApi } from '../api/crypto';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type {
  CoinPrice,
  CompositeSignalResponse,
  FearGreedItem,
  MacroSummaryResponse,
  SectorListResponse,
} from '../types/crypto';

interface CryptoState {
  // Data
  coins: CoinPrice[] | null;
  sectors: SectorListResponse | null;
  fearGreed: FearGreedItem | null;
  macro: MacroSummaryResponse | null;
  selectedCoin: string | null;
  selectedSignal: CompositeSignalResponse | null;
  // Loading
  isLoadingCoins: boolean;
  isLoadingSectors: boolean;
  isLoadingFearGreed: boolean;
  isLoadingMacro: boolean;
  isLoadingSignal: boolean;
  // Error
  error: ParsedApiError | null;

  // Actions
  fetchCoins: (params?: { sector?: string; sortBy?: string }) => Promise<void>;
  fetchSectors: () => Promise<void>;
  fetchFearGreed: () => Promise<void>;
  fetchMacro: () => Promise<void>;
  fetchSignal: (symbol: string) => Promise<void>;
  selectCoin: (symbol: string) => void;
  reset: () => void;
}

export const useCryptoStore = create<CryptoState>((set, get) => ({
  coins: null,
  sectors: null,
  fearGreed: null,
  macro: null,
  selectedCoin: null,
  selectedSignal: null,
  isLoadingCoins: false,
  isLoadingSectors: false,
  isLoadingFearGreed: false,
  isLoadingMacro: false,
  isLoadingSignal: false,
  error: null,

  fetchCoins: async (params) => {
    set({ isLoadingCoins: true, error: null });
    try {
      const data = await cryptoApi.listCoins(params);
      set({ coins: data.items, isLoadingCoins: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingCoins: false });
    }
  },

  fetchSectors: async () => {
    set({ isLoadingSectors: true, error: null });
    try {
      const data = await cryptoApi.listSectors();
      set({ sectors: data, isLoadingSectors: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingSectors: false });
    }
  },

  fetchFearGreed: async () => {
    set({ isLoadingFearGreed: true });
    try {
      const data = await cryptoApi.getFearGreed();
      set({ fearGreed: data, isLoadingFearGreed: false });
    } catch {
      set({ isLoadingFearGreed: false });
    }
  },

  fetchMacro: async () => {
    set({ isLoadingMacro: true });
    try {
      const data = await cryptoApi.getMacro();
      set({ macro: data, isLoadingMacro: false });
    } catch {
      set({ isLoadingMacro: false });
    }
  },

  fetchSignal: async (symbol) => {
    set({ isLoadingSignal: true, selectedCoin: symbol, error: null });
    try {
      const data = await cryptoApi.getSignals(symbol);
      set({ selectedSignal: data, isLoadingSignal: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingSignal: false });
    }
  },

  selectCoin: (symbol) => {
    set({ selectedCoin: symbol });
    get().fetchSignal(symbol);
  },

  reset: () => set({
    coins: null,
    sectors: null,
    fearGreed: null,
    macro: null,
    selectedCoin: null,
    selectedSignal: null,
    error: null,
  }),
}));
