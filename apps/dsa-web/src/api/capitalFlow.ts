import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  CapitalFlowHistoryResponse,
  CapitalFlowSignalResponse,
  CapitalFlowSnapshot,
  DragonTigerResponse,
  NorthboundResponse,
  SectorFlowResponse,
} from '../types/capitalFlow';

export const capitalFlowApi = {
  /** Get northbound capital flow data. */
  getNorthbound: async (days?: number): Promise<NorthboundResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/capital-flow/northbound', {
      params: { days },
    });
    return toCamelCase<NorthboundResponse>(response.data);
  },

  /** Get sector capital flow data. */
  getSectorFlows: async (days?: number): Promise<SectorFlowResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/capital-flow/sectors', {
      params: { days },
    });
    return toCamelCase<SectorFlowResponse>(response.data);
  },

  /** Get dragon-tiger board data. */
  getDragonTiger: async (days?: number): Promise<DragonTigerResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/capital-flow/dragon-tiger', {
      params: { days },
    });
    return toCamelCase<DragonTigerResponse>(response.data);
  },

  /** Get latest capital flow snapshot. */
  getLatestSnapshot: async (): Promise<CapitalFlowSnapshot> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/capital-flow/snapshot');
    return toCamelCase<CapitalFlowSnapshot>(response.data);
  },

  /** Get historical snapshots. */
  getSnapshotHistory: async (params?: {
    page?: number;
    pageSize?: number;
    days?: number;
  }): Promise<CapitalFlowHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/capital-flow/snapshots/history',
      { params: params ? { page: params.page, page_size: params.pageSize, days: params.days } : undefined },
    );
    return toCamelCase<CapitalFlowHistoryResponse>(response.data);
  },

  /** Get capital flow composite signal. */
  getSignal: async (): Promise<CapitalFlowSignalResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/capital-flow/signal');
    return toCamelCase<CapitalFlowSignalResponse>(response.data);
  },
};
