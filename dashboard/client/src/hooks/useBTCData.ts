import { useState, useEffect, useCallback } from "react";

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface UseBTCDataOptions {
  symbol?: string;
  interval?: string;
  limit?: number;
}

export function useBTCData({
  symbol = "BTCUSDT",
  interval = "5m",
  limit = 500,
}: UseBTCDataOptions = {}) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const parsed: Candle[] = data.map((d: any[]) => ({
        time: new Date(d[0]).toISOString().replace("T", " ").slice(0, 19),
        open: parseFloat(d[1]),
        high: parseFloat(d[2]),
        low: parseFloat(d[3]),
        close: parseFloat(d[4]),
        volume: parseFloat(d[5]),
      }));

      setCandles(parsed);
    } catch (err: any) {
      setError(err.message || "Erro ao buscar dados");
    } finally {
      setLoading(false);
    }
  }, [symbol, interval, limit]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { candles, loading, error, refetch: fetchData };
}
