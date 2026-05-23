import { create } from 'zustand';
import { capitalFlowApi } from '../api/capitalFlow';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type {
  CapitalFlowSignalResponse,
  DragonTigerResponse,
  NorthboundResponse,
  SectorFlowResponse,
} from '../types/capitalFlow';

interface CapitalFlowState {
  // Data
  northbound: NorthboundResponse | null;
  sectorFlows: SectorFlowResponse | null;
  dragonTiger: DragonTigerResponse | null;
  signal: CapitalFlowSignalResponse | null;
  // Loading
  isLoadingNorthbound: boolean;
  isLoadingSectorFlows: boolean;
  isLoadingDragonTiger: boolean;
  isLoadingSignal: boolean;
  // Error
  error: ParsedApiError | null;

  // Actions
  fetchAll: () => Promise<void>;
  fetchNorthbound: (days?: number) => Promise<void>;
  fetchSectorFlows: (days?: number) => Promise<void>;
  fetchDragonTiger: (days?: number) => Promise<void>;
  fetchSignal: () => Promise<void>;
  reset: () => void;
}

export const useCapitalFlowStore = create<CapitalFlowState>((set) => ({
  northbound: null,
  sectorFlows: null,
  dragonTiger: null,
  signal: null,
  isLoadingNorthbound: false,
  isLoadingSectorFlows: false,
  isLoadingDragonTiger: false,
  isLoadingSignal: false,
  error: null,

  fetchAll: async () => {
    await Promise.allSettled([
      useCapitalFlowStore.getState().fetchNorthbound(),
      useCapitalFlowStore.getState().fetchSectorFlows(),
      useCapitalFlowStore.getState().fetchDragonTiger(),
      useCapitalFlowStore.getState().fetchSignal(),
    ]);
  },

  fetchNorthbound: async (days = 5) => {
    set({ isLoadingNorthbound: true, error: null });
    try {
      const data = await capitalFlowApi.getNorthbound(days);
      set({ northbound: data, isLoadingNorthbound: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingNorthbound: false });
    }
  },

  fetchSectorFlows: async (days = 3) => {
    set({ isLoadingSectorFlows: true });
    try {
      const data = await capitalFlowApi.getSectorFlows(days);
      set({ sectorFlows: data, isLoadingSectorFlows: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingSectorFlows: false });
    }
  },

  fetchDragonTiger: async (days = 5) => {
    set({ isLoadingDragonTiger: true });
    try {
      const data = await capitalFlowApi.getDragonTiger(days);
      set({ dragonTiger: data, isLoadingDragonTiger: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoadingDragonTiger: false });
    }
  },

  fetchSignal: async () => {
    set({ isLoadingSignal: true });
    try {
      const data = await capitalFlowApi.getSignal();
      set({ signal: data, isLoadingSignal: false });
    } catch {
      set({ isLoadingSignal: false });
    }
  },

  reset: () => set({
    northbound: null,
    sectorFlows: null,
    dragonTiger: null,
    signal: null,
    error: null,
  }),
}));
