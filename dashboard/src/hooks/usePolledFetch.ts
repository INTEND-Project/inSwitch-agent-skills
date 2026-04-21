import { useCallback, useEffect, useRef } from 'react';

type LoadFn = () => Promise<void>;

const isDocumentVisible = () =>
  typeof document === 'undefined' || document.visibilityState === 'visible';

const usePolledFetch = (loadFn: LoadFn, intervalMs: number) => {
  const loadFnRef = useRef(loadFn);
  const inFlightRef = useRef(false);
  const isVisibleRef = useRef(isDocumentVisible());

  useEffect(() => {
    loadFnRef.current = loadFn;
  }, [loadFn]);

  const runNow = useCallback(async (overrideLoadFn?: LoadFn) => {
    if (!isVisibleRef.current || inFlightRef.current) return;

    inFlightRef.current = true;
    try {
      const fn = overrideLoadFn ?? loadFnRef.current;
      await fn();
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    isVisibleRef.current = isDocumentVisible();

    const handleVisibilityChange = () => {
      isVisibleRef.current = isDocumentVisible();
      if (isVisibleRef.current) {
        void runNow();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [runNow]);

  useEffect(() => {
    const timerId = window.setInterval(() => {
      void runNow();
    }, intervalMs);

    return () => {
      window.clearInterval(timerId);
    };
  }, [intervalMs, runNow]);

  return { runNow };
};

export default usePolledFetch;
