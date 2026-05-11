import { useState, useRef, useCallback, useEffect } from "react";

interface UseReplayOptions {
  totalCandles: number;
  initialVisible?: number;
}

export function useReplay({ totalCandles, initialVisible = 20 }: UseReplayOptions) {
  const [currentIndex, setCurrentIndex] = useState(Math.min(initialVisible, totalCandles));
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const play = useCallback(() => {
    if (currentIndex >= totalCandles) return;
    setIsPlaying(true);
  }, [currentIndex, totalCandles]);

  const pause = useCallback(() => {
    setIsPlaying(false);
    clearTimer();
  }, [clearTimer]);

  const reset = useCallback(() => {
    setIsPlaying(false);
    clearTimer();
    setCurrentIndex(Math.min(initialVisible, totalCandles));
  }, [clearTimer, initialVisible, totalCandles]);

  const stepForward = useCallback(() => {
    setCurrentIndex((prev) => Math.min(prev + 1, totalCandles));
  }, [totalCandles]);

  const seek = useCallback(
    (index: number) => {
      setCurrentIndex(Math.max(1, Math.min(index, totalCandles)));
    },
    [totalCandles]
  );

  const changeSpeed = useCallback((newSpeed: number) => {
    setSpeed(newSpeed);
  }, []);

  // Timer effect
  useEffect(() => {
    clearTimer();
    if (isPlaying && currentIndex < totalCandles) {
      // Base interval: 500ms at 1x speed
      const baseInterval = 500;
      const interval = baseInterval / speed;

      intervalRef.current = setInterval(() => {
        setCurrentIndex((prev) => {
          const next = prev + 1;
          if (next >= totalCandles) {
            setIsPlaying(false);
            return totalCandles;
          }
          return next;
        });
      }, interval);
    }
    return clearTimer;
  }, [isPlaying, speed, currentIndex, totalCandles, clearTimer]);

  // Stop when reaching end
  useEffect(() => {
    if (currentIndex >= totalCandles) {
      setIsPlaying(false);
      clearTimer();
    }
  }, [currentIndex, totalCandles, clearTimer]);

  return {
    currentIndex,
    isPlaying,
    speed,
    play,
    pause,
    reset,
    stepForward,
    seek,
    changeSpeed,
  };
}
