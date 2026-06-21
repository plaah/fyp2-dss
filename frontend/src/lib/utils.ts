import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatRp(n: number | undefined | null) {
  if (n == null) return "—"
  return "Rp " + n.toLocaleString("id-ID")
}
