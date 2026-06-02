export type MarketSessionStatus = 'open' | 'closed' | 'pre-open' | 'post-close';

export type MarketDirection = 'up' | 'down' | 'flat';

export type MarketInfo = {
  /** Exchange code, e.g. 'NYSE', 'HKEX'. */
  exchange: string;
  /** Trading-session status derived from local trading hours. */
  status: MarketSessionStatus;
  /** Daily direction when known; null when closed or data unavailable. */
  direction: MarketDirection | null;
  /** Daily percent change when known; null when unavailable. */
  changePercent: number | null;
};

export type MarketStatusMap = Record<string, MarketInfo>;
