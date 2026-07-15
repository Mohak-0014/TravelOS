import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, resolving Tailwind conflicts (last wins). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** "USD 1,234" style formatting for budget/price display. */
export function formatMoney(amount: number, currency?: string): string {
  const rounded = Math.round(amount).toLocaleString();
  return currency ? `${currency} ${rounded}` : rounded;
}
