/**
 * Capital flow type definitions.
 * Northbound, sector flow, dragon-tiger board.
 */

// ============ Northbound ============

export interface NorthboundFlow {
  date: string;
  netInflowCny: number;
  balance?: number;
  quota?: number;
}

export interface NorthboundResponse {
  items: NorthboundFlow[];
  totalInflow: number;
  avgDaily: number;
  trend?: string;
  days: number;
}

// ============ Sector Flow ============

export interface SectorFlow {
  sectorName?: string;
  sectorCode?: string;
  mainNetInflow: number;
  superLargeNet?: number;
  largeNet?: number;
  mediumNet?: number;
  smallNet?: number;
  priceChangePct?: number;
}

export interface SectorFlowResponse {
  items: SectorFlow[];
  positiveSectors: number;
  totalSectors: number;
  positiveRatio: number;
  topInflow: SectorFlow[];
  topOutflow: SectorFlow[];
}

// ============ Dragon-Tiger ============

export interface DragonTigerStock {
  stockCode: string;
  stockName?: string;
  buyAmountCny?: number;
  sellAmountCny?: number;
  netAmountCny?: number;
  reason?: string;
  changePct?: number;
  turnoverRate?: number;
  date?: string;
}

export interface DragonTigerResponse {
  items: DragonTigerStock[];
  totalNet: number;
  netRatio: number;
  signal?: string;
  stocksCount: number;
}

// ============ Snapshot ============

export interface CapitalFlowSnapshot {
  date: string;
  northbound: NorthboundFlow[];
  sectorFlows: SectorFlow[];
  dragonTiger: DragonTigerStock[];
  signal?: Record<string, unknown>;
}

export interface CapitalFlowHistoryResponse {
  items: CapitalFlowSnapshot[];
  total: number;
  page: number;
  pageSize: number;
}

// ============ Signal ============

export interface CapitalFlowSignalComponent {
  score: number;
  signal?: string;
  detail?: Record<string, unknown>;
}

export interface CapitalFlowSignalResponse {
  assetCode: string;
  compositeScore: number;
  signalLabel: string;
  components: Record<string, CapitalFlowSignalComponent>;
  weights: Record<string, number>;
}
