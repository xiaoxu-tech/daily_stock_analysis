import { useEffect, useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { Coins, TrendingUp, TrendingDown, Minus, ExternalLink } from 'lucide-react';
import { useCryptoStore } from '../stores/cryptoStore';
import { ApiErrorAlert, Button, Card, Loading, EmptyState, Badge } from '../components/common';
import { cn } from '../utils/cn';
import type { CoinPrice, CompositeSignalResponse } from '../types/crypto';

const SIGNAL_COLORS: Record<string, string> = {
  strong_buy: 'text-green-400 bg-green-500/10',
  buy: 'text-green-300 bg-green-500/10',
  neutral: 'text-yellow-400 bg-yellow-500/10',
  sell: 'text-red-300 bg-red-500/10',
  strong_sell: 'text-red-400 bg-red-500/10',
};

function CoinRow({
  coin,
  onClick,
  isSelected,
}: {
  coin: CoinPrice;
  onClick: () => void;
  isSelected: boolean;
}) {
  const change = coin.change24h ?? 0;
  const ChangeIcon = change > 0 ? TrendingUp : change < 0 ? TrendingDown : Minus;
  const changeColor = change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-muted-foreground';

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
        'hover:bg-[var(--hover)]',
        isSelected && 'bg-[var(--nav-active-bg)] ring-1 ring-[hsl(var(--primary)/0.3)]',
      )}
    >
      <span className="w-8 text-center text-xs font-bold text-muted-foreground tabular-nums">
        {coin.rank ?? '-'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-foreground">{coin.symbol}</div>
        <div className="truncate text-xs text-muted-foreground">{coin.name}</div>
      </div>
      <div className="text-right">
        <div className="text-sm font-semibold tabular-nums text-foreground">
          ${coin.priceUsd?.toLocaleString() ?? '-'}
        </div>
        <div className={cn('flex items-center justify-end gap-0.5 text-xs tabular-nums', changeColor)}>
          <ChangeIcon className="h-3 w-3" />
          {change.toFixed(2)}%
        </div>
      </div>
    </button>
  );
}

function FearGreedGauge({ value, label }: { value: number; label: string }) {
  const pct = value;
  const color =
    pct >= 75 ? 'text-green-400' :
    pct >= 55 ? 'text-green-300' :
    pct >= 45 ? 'text-yellow-400' :
    pct >= 25 ? 'text-orange-400' :
    'text-red-400';

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-20 w-20">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="42" fill="none"
            stroke="currentColor" strokeWidth="8" strokeLinecap="round"
            strokeDasharray={`${pct * 2.64} 264`}
            className={color}
          />
        </svg>
        <span className={cn('absolute inset-0 flex items-center justify-center text-lg font-bold', color)}>
          {value}
        </span>
      </div>
      <span className="mt-1 text-xs font-medium text-muted-foreground">{label}</span>
    </div>
  );
}

function SignalBar({ signal }: { signal: CompositeSignalResponse | null }) {
  if (!signal) return null;
  const score = signal.composite;
  const barPct = ((score + 1) / 2) * 100;
  const barColor =
    score >= 0.6 ? 'bg-green-500' :
    score >= 0.3 ? 'bg-green-400' :
    score >= -0.3 ? 'bg-yellow-500' :
    score >= -0.6 ? 'bg-orange-500' :
    'bg-red-500';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">综合信号</span>
        <Badge className={SIGNAL_COLORS[signal.signal] ?? 'text-muted-foreground'}>
          {signal.signalCn}
        </Badge>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className={cn('h-full rounded-full transition-all', barColor)}
          style={{ width: `${barPct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>-1.0</span>
        <span className="tabular-nums font-medium text-foreground">{score.toFixed(3)}</span>
        <span>+1.0</span>
      </div>
      {/* Component breakdown */}
      {signal.components && (
        <div className="mt-2 grid grid-cols-3 gap-1">
          {Object.entries(signal.components).map(([key, comp]) => (
            <div key={key} className="rounded bg-[var(--hover)] px-1.5 py-1 text-center">
              <div className="text-[10px] text-muted-foreground">{key}</div>
              <div className={cn('text-xs font-medium tabular-nums',
                comp.score > 0 ? 'text-green-400' : comp.score < 0 ? 'text-red-400' : 'text-muted-foreground'
              )}>
                {comp.score.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CryptoPage() {
  const {
    coins, fearGreed, macro, selectedCoin, selectedSignal,
    isLoadingCoins, isLoadingSignal, error,
    fetchCoins, fetchFearGreed, fetchMacro, selectCoin,
  } = useCryptoStore(useShallow((s) => ({
    coins: s.coins,
    fearGreed: s.fearGreed,
    macro: s.macro,
    selectedCoin: s.selectedCoin,
    selectedSignal: s.selectedSignal,
    isLoadingCoins: s.isLoadingCoins,
    isLoadingSignal: s.isLoadingSignal,
    error: s.error,
    fetchCoins: s.fetchCoins,
    fetchFearGreed: s.fetchFearGreed,
    fetchMacro: s.fetchMacro,
    selectCoin: s.selectCoin,
  })));

  const [sector, setSector] = useState<string | undefined>();

  useEffect(() => { document.title = '加密 - DSA'; }, []);
  useEffect(() => {
    fetchCoins({ sector, sortBy: 'rank' });
    fetchFearGreed();
    fetchMacro();
  }, [fetchCoins, fetchFearGreed, fetchMacro, sector]);

  return (
    <div className="mx-auto flex max-w-7xl flex-1 gap-6 p-4 lg:p-6">
      {/* Left: Coin list */}
      <div className="w-72 shrink-0">
        <Card title="币种列表" padding="none">
          <div className="max-h-[calc(100vh-16rem)] overflow-y-auto">
            {isLoadingCoins && coins === null ? (
              <Loading label="加载币种..." />
            ) : coins && coins.length > 0 ? (
              coins.map((c) => (
                <CoinRow
                  key={c.symbol}
                  coin={c}
                  isSelected={selectedCoin === c.symbol}
                  onClick={() => selectCoin(c.symbol)}
                />
              ))
            ) : (
              <EmptyState icon={<Coins />} title="暂无数据" description="无法获取加密货币列表" />
            )}
          </div>
        </Card>
      </div>

      {/* Right: Dashboard */}
      <div className="min-w-0 flex-1 space-y-6">
        {error && <ApiErrorAlert error={error} />}

        {/* Top row: Fear & Greed + Macro */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Card title="恐惧贪婪指数">
            {fearGreed ? (
              <FearGreedGauge value={fearGreed.value} label={fearGreed.label} />
            ) : (
              <Loading label="加载中..." />
            )}
          </Card>
          <Card title="宏观环境">
            {macro ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">综合</span>
                  <Badge className={macro.compositeScore > 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}>
                    {macro.compositeLabel}
                  </Badge>
                </div>
                {macro.summary && (
                  <p className="text-xs text-muted-foreground">{macro.summary}</p>
                )}
              </div>
            ) : (
              <Loading label="加载中..." />
            )}
          </Card>
        </div>

        {/* Bottom: Signal detail */}
        <Card title={selectedCoin ? `${selectedCoin} 信号分析` : '选择一个币种查看信号'}>
          {isLoadingSignal ? (
            <Loading label="计算信号..." />
          ) : selectedSignal ? (
            <div className="space-y-4">
              <SignalBar signal={selectedSignal} />
              {/* Technical detail */}
              {selectedSignal.components?.technical?.detail?.enhanced && (
                <div className="rounded-lg border border-[var(--border)] p-3">
                  <div className="mb-2 text-xs font-medium text-muted-foreground">形态 & 趋势</div>
                  {(() => {
                    const e = (selectedSignal.components.technical.detail as Record<string, unknown>).enhanced as Record<string, unknown>;
                    return (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <span className="text-muted-foreground">形态</span>
                        <span>{e?.patterns || '-'}</span>
                        <span className="text-muted-foreground">量能</span>
                        <span>{e?.volumeStatus || '-'}</span>
                        <span className="text-muted-foreground">RSI</span>
                        <span>{e?.rsiSignal || '-'}</span>
                        <span className="text-muted-foreground">乖离率</span>
                        <span>{e?.biasSignal || '-'}</span>
                        <span className="text-muted-foreground">趋势</span>
                        <span>{e?.trendState || '-'}</span>
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              icon={<TrendingUp />}
              title="选择币种"
              description="从左侧列表选择一个加密货币查看详细信号分析"
            />
          )}
        </Card>
      </div>
    </div>
  );
}
