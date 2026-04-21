export type Currency = 'USD' | 'EUR' | 'NOK';

export const CURRENCIES: Array<{ code: Currency; label: string }> = [
  { code: 'USD', label: 'US Dollar' },
  { code: 'EUR', label: 'Euro' },
  { code: 'NOK', label: 'Norwegian Krone' }
];

const RATES_STORAGE_KEY = 'observability.rates';
const CURRENCY_STORAGE_KEY = 'observability.currency';
const RATES_TTL_MS = 60 * 60 * 1000;
const FETCH_TIMEOUT_MS = 5_000;
const FALLBACK_USD = 'USD';

type RatesRecord = Record<Currency, number>;

type StoredRatesPayload = {
  rates: RatesRecord;
  fetchedAt: number;
};

const isCurrency = (value: unknown): value is Currency =>
  value === 'USD' || value === 'EUR' || value === 'NOK';

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const isRatesRecord = (value: unknown): value is RatesRecord => {
  if (!value || typeof value !== 'object') return false;
  const maybe = value as Partial<Record<Currency, unknown>>;
  return (
    isFiniteNumber(maybe.USD) &&
    isFiniteNumber(maybe.EUR) &&
    isFiniteNumber(maybe.NOK)
  );
};

export const fetchRates = async (): Promise<RatesRecord | null> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const response = await fetch(
      'https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,NOK',
      { signal: controller.signal }
    );

    if (!response.ok) return null;

    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object') return null;

    const rates = (payload as { rates?: Record<string, unknown> }).rates;
    const eurRate = rates?.EUR;
    const nokRate = rates?.NOK;

    if (!isFiniteNumber(eurRate) || !isFiniteNumber(nokRate)) return null;

    return {
      USD: 1,
      EUR: eurRate,
      NOK: nokRate
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
};

export const getCachedRates = (): RatesRecord | null => {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.localStorage.getItem(RATES_STORAGE_KEY);
    if (!raw) return null;

    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;

    const { rates, fetchedAt } = parsed as {
      rates?: unknown;
      fetchedAt?: unknown;
    };

    if (!isRatesRecord(rates) || !isFiniteNumber(fetchedAt)) return null;
    if (Date.now() - fetchedAt >= RATES_TTL_MS) return null;

    return rates;
  } catch {
    return null;
  }
};

export const setCachedRates = (rates: RatesRecord): void => {
  if (typeof window === 'undefined') return;

  try {
    const payload: StoredRatesPayload = {
      rates,
      fetchedAt: Date.now()
    };
    window.localStorage.setItem(RATES_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage errors.
  }
};

export const loadRates = async (): Promise<RatesRecord | null> => {
  const cached = getCachedRates();
  if (cached) return cached;

  const fetched = await fetchRates();
  if (fetched) {
    setCachedRates(fetched);
    return fetched;
  }

  return null;
};

export const formatCurrency = (
  amountUsd: number,
  target: Currency,
  rates: RatesRecord | null
): string => {
  try {
    const currency: Currency = target;
    const canConvert = currency !== 'USD' && rates !== null;
    const convertedAmount = canConvert
      ? amountUsd * rates[currency]
      : amountUsd;

    const fractionDigits = currency === 'NOK' ? 2 : 4;

    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits
    }).format(convertedAmount);
  } catch {
    return `$${amountUsd.toFixed(4)}`;
  }
};

export const getStoredCurrency = (): Currency => {
  if (typeof window === 'undefined') return FALLBACK_USD;

  try {
    const value = window.localStorage.getItem(CURRENCY_STORAGE_KEY);
    return isCurrency(value) ? value : FALLBACK_USD;
  } catch {
    return FALLBACK_USD;
  }
};

export const setStoredCurrency = (c: Currency): void => {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(CURRENCY_STORAGE_KEY, c);
  } catch {
    // Ignore storage errors.
  }
};
