import { useEffect } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { ArrowUpDown, TrendingUp, TrendingDown, BarChart3, DollarSign } from 'lucide-react';
import { useCapitalFlowStore } from '../stores/capitalFlowStore';
import { ApiErrorAlert, Card, Loading, EmptyState, Badge, Button } from '../components/common';
import { cn } from '../utils/cn';
import type { NorthboundFlow, SectorFlow, DragonTigerStock } from '../types/capitalFlow';

function formatInflow(cny: number): string {
  const abs = Math.abs(cny);
  const sign = cny >= 0 ? '+' : '-';
  return `${sign}${abs.toFixed(2)}亿`;
}

export default function CapitalFlowPage() {
  const {
    northbound, sectorFlows, dragonTiger, signal,
    isLoadingNorthbound, isLoadingSectorFlows, isLoadingDragonTiger,
    error, fetchAll,
  } = useCapitalFlowStore(useShallow((s) => ({
    northbound: s.northbound,
    sectorFlows: s.sectorFlows,
    dragonTiger: s.dragonTiger,
    signal: s.signal,
    isLoadingNorthbound: s.isLoadingNorthbound,
    isLoadingSectorFlows: s.isLoadingSectorFlows,
    isLoadingDragonTiger: s.isLoadingDragonTiger,
    error: s.error,
    fetchAll: s.fetchAll,
  })));

  useEffect(() => { document.title = '资金流向 - DSA'; }, []);
  useEffect(() => { fetchAll(); }, [fetchAll]);

  const loading = isLoadingNorthbound || isLoadingSectorFlows || isLoadingDragonTiger;

  return (
    <div className="mx-auto flex max-w-6xl flex-1 flex-col gap-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <ArrowUpDown className="h-5 w-5" /> A股资金流向
        </h1>
        {signal && (
          <Badge className={cn('text-sm px-3 py-1',
            signal.compositeScore > 0 ? 'bg-green-500/10 text-green-400' :
            signal.compositeScore < 0 ? 'bg-red-500/10 text-red-400' :
            'bg-yellow-500/10 text-yellow-400'
          )}>
            市场情绪：{signal.signalLabel}
          </Badge>
        )}
        <Button variant="secondary" size="sm" onClick={fetchAll} isLoading={loading}>
          刷新
        </Button>
      </div>

      {error && <ApiErrorAlert error={error} />}

      {/* Northbound */}
      <Card title="北向资金流向">
        {loading && northbound === null ? <Loading label="加载北向数据..." /> :
         northbound ? (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">累计净流入 </span>
                <span className={cn('font-semibold tabular-nums', northbound.totalInflow >= 0 ? 'text-green-400' : 'text-red-400')}>
                  {formatInflow(northbound.totalInflow)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">日均 </span>
                <span className="font-semibold tabular-nums">{northbound.avgDaily.toFixed(2)}亿</span>
              </div>
              <div>
                <span className="text-muted-foreground">趋势 </span>
                <span className="font-medium">{northbound.trend}</span>
              </div>
            </div>
            {/* Bar chart simulation */}
            <div className="flex items-end gap-1 h-16">
              {northbound.items.slice(-10).map((nb: NorthboundFlow, i: number) => {
                const maxAbs = Math.max(...northbound.items.map((n: NorthboundFlow) => Math.abs(n.netInflowCny)), 1);
                const h = Math.abs(nb.netInflowCny) / maxAbs * 100;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                    <div
                      className={cn('w-full rounded-t transition-all', nb.netInflowCny >= 0 ? 'bg-green-500/60' : 'bg-red-500/60')}
                      style={{ height: `${Math.max(h, 4)}%` }}
                    />
                    <span className="text-[9px] text-muted-foreground">{nb.date.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : <EmptyState icon={<BarChart3 />} title="暂无北向数据" />}
      </Card>

      {/* Sector Flow */}
      <Card title="板块资金流向">
        {sectorFlows ? (
          <div className="space-y-2">
            <div className="flex gap-4 text-xs text-muted-foreground mb-2">
              <span>板块数 {sectorFlows.totalSectors}</span>
              <span>净流入 {sectorFlows.positiveSectors} ({sectorFlows.positiveRatio.toFixed(0)}%)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)] text-muted-foreground">
                    <th className="py-1.5 text-left font-medium">板块</th>
                    <th className="py-1.5 text-right font-medium">主力净流入</th>
                    <th className="py-1.5 text-right font-medium">涨跌幅</th>
                  </tr>
                </thead>
                <tbody>
                  {[...sectorFlows.topInflow, ...sectorFlows.topOutflow].slice(0, 12).map((sf: SectorFlow, i: number) => (
                    <tr key={i} className="border-b border-[var(--border)]/50">
                      <td className="py-1.5">{sf.sectorName || '-'}</td>
                      <td className={cn('py-1.5 text-right tabular-nums', sf.mainNetInflow > 0 ? 'text-green-400' : 'text-red-400')}>
                        {formatInflow(sf.mainNetInflow)}
                      </td>
                      <td className={cn('py-1.5 text-right tabular-nums', (sf.priceChangePct ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>
                        {sf.priceChangePct?.toFixed(2) ?? '-'}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <Loading label="加载板块数据..." />
        )}
      </Card>

      {/* Dragon Tiger */}
      <Card title="龙虎榜">
        {dragonTiger ? (
          <div className="space-y-2">
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>上榜 {dragonTiger.stocksCount} 只</span>
              <span>总净额 {formatInflow(dragonTiger.totalNet)}</span>
              <span className="font-medium text-foreground">{dragonTiger.signal}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)] text-muted-foreground">
                    <th className="py-1.5 text-left font-medium">代码</th>
                    <th className="py-1.5 text-left font-medium">名称</th>
                    <th className="py-1.5 text-right font-medium">净额(亿)</th>
                    <th className="py-1.5 text-right font-medium">涨跌幅</th>
                    <th className="py-1.5 text-left font-medium">上榜原因</th>
                  </tr>
                </thead>
                <tbody>
                  {dragonTiger.items.slice(0, 20).map((dt: DragonTigerStock, i: number) => (
                    <tr key={i} className="border-b border-[var(--border)]/50">
                      <td className="py-1.5 font-mono">{dt.stockCode}</td>
                      <td className="py-1.5">{dt.stockName || '-'}</td>
                      <td className={cn('py-1.5 text-right tabular-nums', (dt.netAmountCny ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>
                        {dt.netAmountCny?.toFixed(2) ?? '-'}
                      </td>
                      <td className={cn('py-1.5 text-right tabular-nums', (dt.changePct ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>
                        {dt.changePct?.toFixed(2) ?? '-'}%
                      </td>
                      <td className="py-1.5 text-muted-foreground max-w-[200px] truncate">{dt.reason || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <Loading label="加载龙虎榜..." />
        )}
      </Card>
    </div>
  );
}
