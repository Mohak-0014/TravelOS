// Mirrors backend/tools/currency.py — keep rates in sync with that file.
const RATE_TO_INR: Record<string, number> = {
  INR: 1,
  USD: 0.0119,
  EUR: 0.01099,
  GBP: 0.00943,
  JPY: 1.851,
  AUD: 0.01852,
  NZD: 0.02,
  CAD: 0.01639,
  CHF: 0.01053,
  SGD: 0.01587,
  HKD: 0.09346,
  MYR: 0.05263,
  THB: 0.41667,
  IDR: 192.31,
  PHP: 0.68027,
  VND: 303.03,
  KRW: 16.667,
  CNY: 0.08696,
  TWD: 0.38462,
  AED: 0.04386,
  QAR: 0.04329,
  EGP: 0.57143,
  ZAR: 0.22222,
  TRY: 0.41667,
  BRL: 0.06667,
  MXN: 0.2381,
  SEK: 0.125,
  NOK: 0.11111,
  DKK: 0.08197,
  NPR: 1.6,
  LKR: 3.175,
  RUB: 1.07527,
  CZK: 0.2381,
  HUF: 3.07692,
  PLN: 0.04167,
};

export function convertToBudgetCurrency(amount: number, from: string, to: string): number {
  if (from === to) return amount;
  const fromRate = RATE_TO_INR[from.toUpperCase()];
  const toRate = RATE_TO_INR[to.toUpperCase()];
  if (!fromRate || !toRate) return amount;
  const inr = amount / fromRate; // convert to INR pivot
  return inr * toRate; // then to target currency
}
