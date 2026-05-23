import { useEffect, useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import {
  Newspaper, ExternalLink, RefreshCw, Filter, Calendar, Coins,
  TrendingUp, TrendingDown, Hash, InlineAlert,
} from 'lucide-react';
import { useNewsFeedStore } from '../stores/newsFeedStore';
import { ApiErrorAlert, Button, Card, Loading, EmptyState, Badge } from '../components/common';
import { cn } from '../utils/cn';
import type { NewsItem } from '../types/news';

const PAGE_SIZE = 20;

function NewsCard({ item }: { item: NewsItem }) {
  const sentimentColor =
    item.sentimentScore === undefined ? '' :
    item.sentimentScore >= 0.65 ? 'bg-green-500/10 text-green-400' :
    item.sentimentScore >= 0.45 ? 'bg-yellow-500/10 text-yellow-400' :
    'bg-red-500/10 text-red-400';

  return (
    <div className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:bg-[var(--hover)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge className="bg-primary/10 text-primary text-[10px]">{item.source}</Badge>
            {item.sentimentScore !== undefined && (
              <Badge className={cn('text-[10px]', sentimentColor)}>
                {item.sentimentLabel ?? (item.sentimentScore >= 0.5 ? 'bullish' : 'bearish')}
              </Badge>
            )}
            {item.eventType && (
              <span className="text-[10px] text-muted-foreground">{item.eventType}</span>
            )}
          </div>
          <a
            href={item.url ?? '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-foreground hover:underline line-clamp-2"
          >
            {item.title}
          </a>
          {item.summary && (
            <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{item.summary}</p>
          )}
          {item.mentionedCoins && item.mentionedCoins.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {item.mentionedCoins.slice(0, 5).map((coin) => (
                <span key={coin} className="rounded bg-[var(--hover)] px-1 py-px text-[10px] text-muted-foreground">
                  {coin}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground tabular-nums whitespace-nowrap">
          {item.publishedAt ? new Date(item.publishedAt).toLocaleDateString('zh-CN') : ''}
        </span>
      </div>
    </div>
  );
}

export default function NewsFeedPage() {
  const {
    items, stats, isLoading, isScraping, error, scrapeResult,
    sourceType, fetchFeed, fetchStats, triggerScrape, setSourceType,
  } = useNewsFeedStore(useShallow((s) => ({
    items: s.items,
    stats: s.stats,
    isLoading: s.isLoading,
    isScraping: s.isScraping,
    error: s.error,
    scrapeResult: s.scrapeResult,
    sourceType: s.sourceType,
    fetchFeed: s.fetchFeed,
    fetchStats: s.fetchStats,
    triggerScrape: s.triggerScrape,
    setSourceType: s.setSourceType,
  })));

  const [page, setPage] = useState(1);

  useEffect(() => { document.title = '新闻 - DSA'; }, []);
  useEffect(() => {
    fetchFeed({ page, pageSize: PAGE_SIZE, sourceType: sourceType ?? undefined, hours: 168 });
    fetchStats();
  }, [fetchFeed, fetchStats, page, sourceType]);

  const tabs = [
    { key: null, label: '全部' },
    { key: 'crypto' as const, label: '加密货币' },
    { key: 'astock' as const, label: 'A股' },
  ];

  return (
    <div className="mx-auto flex max-w-4xl flex-1 flex-col gap-4 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Newspaper className="h-5 w-5" /> 新闻聚合
        </h1>
        <Button
          variant="secondary"
          size="sm"
          isLoading={isScraping}
          loadingText="抓取中..."
          onClick={() => triggerScrape({ sourceType: sourceType ?? 'both', maxArticles: 20, analyze: true })}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          抓取最新
        </Button>
      </div>

      {error && <ApiErrorAlert error={error} />}
      {scrapeResult && <InlineAlert variant="success" message={scrapeResult} />}

      {/* Stats bar */}
      {stats && (
        <div className="flex flex-wrap gap-3 rounded-lg border border-[var(--border)] px-4 py-2 text-xs text-muted-foreground">
          <span>总量 {stats.totalArticles}</span>
          <span>24h {stats.articles24h}</span>
          <span>7d {stats.articles7d}</span>
          <span className="text-foreground font-medium">
            Top: {Object.entries(stats.topCoins).slice(0, 3).map(([k, v]) => `${k}(${v})`).join(' ')}
          </span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-[var(--hover)] p-0.5">
        {tabs.map((t) => (
          <button
            key={t.key ?? 'all'}
            type="button"
            onClick={() => { setSourceType(t.key); setPage(1); }}
            className={cn(
              'flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              sourceType === t.key ? 'bg-[var(--background)] text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* News list */}
      {isLoading && items === null ? (
        <Loading label="加载新闻..." />
      ) : items && items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item) => (
            <NewsCard key={item.newsId} item={item} />
          ))}
          {items.length >= PAGE_SIZE && (
            <div className="flex justify-center pt-2">
              <Button variant="secondary" size="sm" onClick={() => setPage((p) => p + 1)}>
                加载更多
              </Button>
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={<Newspaper />}
          title="暂无新闻"
          description="点击右上角「抓取最新」按钮获取新闻"
        />
      )}
    </div>
  );
}
