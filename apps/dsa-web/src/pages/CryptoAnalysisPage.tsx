import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, Activity, Gauge, BarChart3 } from 'lucide-react';
import { cryptoApi } from '../api/crypto';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, Loading, EmptyState, Badge, Button } from '../components/common';
import { cn } from '../utils/cn';
import type {
  CompositeSignalResponse,
  PatternResponse,
  OHLCVItem,
  EnhancedTechnicalDetail,
} from '../types/crypto';

const SIGNAL_COLORS: Record<string, string> = {
  strong_buy: 'text-green-400 bg-green-500/10',
  buy: 'text-green-300 bg-green-500/10',
  neutral: 'text-yellow-400 bg-yellow-500/10',
  sell: 'text-red-300 bg-red-500/10',
  strong_sell: 'text-red-400 bg-red-500/10',
};

export default function CryptoAnalysisPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [signal, setSignal] = useState<CompositeSignalResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVItem[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    if (!symbol) return;
    document.title = `${symbol.toUpperCase()} 分析 - DSA`;

    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [sig, pat, ohlcvData] = await Promise.all([
          cryptoApi.getSignals(symbol),
          cryptoApi.getPatterns(symbol, 60),
          cryptoApi.getOHLCV(symbol, { interval: '1d', days: 90 }),
        ]);
        setSignal(sig);
        setPatterns(pat);
        setOhlcv(ohlcvData.items);
      } catch (err) {
        setError(getParsedApiError(err));
      } finally {
        setIsLoading(false);
      }
    })();
  }, [symbol]);

  if (!symbol) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-1 flex-col gap-6 p-4 lg:p-6">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <Link to="/crypto">
          <Button variant="secondary" size="sm"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-lg font-semibold text-foreground">{symbol.toUpperCase()} 深度分析</h1>
        {signal && (
          <Badge className={SIGNAL_COLORS[signal.signal] ?? ''}>
            {signal.signalCn} ({signal.composite.toFixed(2)})
          </Badge>
        )}
      </div>

      {error && <ApiErrorAlert error={error} />}

      {isLoading ? (
        <Loading label="加载分析数据..." />
      ) : (
        <div className="space-y-6">
          {/* Signal Overview */}
          {signal && (
            <Card title="综合信号">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(signal.components).map(([key, comp]) => (
                  <div key={key} className="rounded-lg border border-[var(--border)] p-3 text-center">
                    <div className="text-xs text-muted-foreground capitalize">{key}</div>
                    <div className={cn('mt-1 text-lg font-bold tabular-nums',
                      comp.score > 0 ? 'text-green-400' : comp.score < 0 ? 'text-red-400' : 'text-muted-foreground'
                    )}>
                      {comp.score.toFixed(3)}
                    </div>
                    <div className="text-[10px] text-muted-foreground">{comp.signal}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Enhanced Technical */}
          {signal?.components?.technical?.detail?.enhanced && (
            <Card title="形态与趋势分析">
              {(() => {
                const e = signal.components.technical.detail as Record<string, unknown>;
                const enh = e.enhanced as EnhancedTechnicalDetail;
                return (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatItem label="K线形态" value={enh.patterns || '-'} sub={enh.patternsCount ? `${enh.patternsCount} 个` : undefined} />
                    <StatItem label="量能" value={enh.volumeStatus || '-'} />
                    <StatItem label="RSI信号" value={enh.rsiSignal || '-'} />
                    <StatItem label="乖离率" value={enh.biasSignal || '-'} />
                    <StatItem label="趋势状态" value={enh.trendState || '-'} />
                    <StatItem label="增强评分" value={enh.score?.toFixed(3) ?? '-'} />
                  </div>
                );
              })()}
            </Card>
          )}

          {/* Pattern Details */}
          {patterns && patterns.patterns.length > 0 && (
            <Card title="K线形态识别">
              <div className="space-y-2">
                {patterns.patterns.map((p, i) => (
                  <div key={i} className="flex items-center justify-between rounded border border-[var(--border)] px-3 py-2">
                    <div>
                      <span className="text-sm font-medium">{p.pattern}</span>
                      {p.desc && <span className="ml-2 text-xs text-muted-foreground">{p.desc}</span>}
                    </div>
                    <Badge className={cn('text-[10px]',
                      p.type.includes('bullish') ? 'bg-green-500/10 text-green-400' :
                      p.type.includes('bearish') ? 'bg-red-500/10 text-red-400' :
                      'bg-yellow-500/10 text-yellow-400'
                    )}>
                      {p.type} {p.strength && `(${p.strength})`}
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Mini price chart (text-based sparkline) */}
          {ohlcv && ohlcv.length > 0 && (
            <Card title="价格走势 (90日)">
              <div className="flex items-end gap-[1px] h-24">
                {ohlcv.slice(-60).map((item, i) => {
                  const allPrices = ohlcv.map((o) => o.close);
                  const min = Math.min(...allPrices);
                  const max = Math.max(...allPrices);
                  const range = max - min || 1;
                  const h = ((item.close - min) / range) * 100;
                  return (
                    <div
                      key={i}
                      className="flex-1 rounded-t transition-all"
                      style={{
                        height: `${Math.max(h, 2)}%`,
                        backgroundColor: i > 0 && item.close >= ohlcv[Math.max(0, i - 1 + (ohlcv.length - 60))]?.close
                          ? 'rgb(74 222 128 / 0.6)' : 'rgb(248 113 113 / 0.6)',
                      }}
                    />
                  );
                })}
              </div>
              <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
                <span>${Math.min(...ohlcv.map((o) => o.close)).toLocaleString()}</span>
                <span>${Math.max(...ohlcv.map((o) => o.close)).toLocaleString()}</span>
              </div>
            </Card>
          )}

          {!signal && !patterns && !ohlcv && (
            <EmptyState icon={<BarChart3 />} title="暂无数据" description={`无法获取 ${symbol} 的分析数据`} />
          )}
        </div>
      )}
    </div>
  );
}

function StatItem({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-[var(--hover)] p-3">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="text-sm font-medium text-foreground">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
