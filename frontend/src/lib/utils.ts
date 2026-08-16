import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge multiple Tailwind CSS class names cleanly without collision.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
