// Where the API lives, for the example requests shown in the playground and docs.
export const API_BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8010").replace(/\/+$/, "");

// Quote a value for a single-quoted shell string.
export function shellQuote(text) {
  return "'" + String(text).replace(/'/g, "'\\''") + "'";
}
