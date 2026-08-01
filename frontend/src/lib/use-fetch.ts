"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface FetchState<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): FetchState<T> {
  const [result, setResult] = useState<{ data: T | undefined; error: string | null }>({
    data: undefined,
    error: null,
  });
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let cancelled = false;
    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) setResult({ data, error: null });
      })
      .catch((exc) => {
        if (!cancelled) {
          setResult({
            data: undefined,
            error: exc instanceof Error ? exc.message : "Request failed",
          });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => {
    setResult({ data: undefined, error: null });
    setNonce((value) => value + 1);
  }, []);

  const loading = result.data === undefined && result.error === null;

  return { data: result.data, error: result.error, loading, reload };
}
