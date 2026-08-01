import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function shortAddress(address: string, chars = 6): string {
  if (address.length <= chars * 2 + 2) return address;
  return `${address.slice(0, chars)}…${address.slice(-4)}`;
}

export function formatApy(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatAmount(value: string | number | null): string {
  if (value === null || value === undefined) return "—";
  const number = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(number)) return "—";
  return number.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
}
