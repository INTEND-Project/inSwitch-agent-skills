import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  Currency,
  getStoredCurrency,
  loadRates,
  setStoredCurrency
} from '../utils/currency';

type CurrencyContextValue = {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  rates: Record<Currency, number> | null;
  ratesAvailable: boolean;
};

const CurrencyContext = createContext<CurrencyContextValue | undefined>(undefined);

type CurrencyProviderProps = {
  children: React.ReactNode;
};

export const CurrencyProvider: React.FC<CurrencyProviderProps> = ({ children }) => {
  const [currency, setCurrency] = useState<Currency>(() => getStoredCurrency());
  const [rates, setRates] = useState<Record<Currency, number> | null>(null);

  useEffect(() => {
    setStoredCurrency(currency);
  }, [currency]);

  useEffect(() => {
    let cancelled = false;

    const hydrateRates = async () => {
      const loadedRates = await loadRates();
      if (cancelled) return;

      setRates(loadedRates);

      if (loadedRates === null) {
        setCurrency((current) => {
          if (current === 'USD') return current;
          setStoredCurrency('USD');
          return 'USD';
        });
      }
    };

    void hydrateRates();

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<CurrencyContextValue>(
    () => ({
      currency,
      setCurrency,
      rates,
      ratesAvailable: rates !== null
    }),
    [currency, rates]
  );

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
};

export const useCurrency = (): CurrencyContextValue => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error('useCurrency must be used within a CurrencyProvider');
  }
  return context;
};
