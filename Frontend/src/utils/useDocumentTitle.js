import { useEffect } from "react";

const SUFFIX = "Unfurl";

/** Give each screen its own browser-tab title, e.g. "Quickstart — Unfurl". */
export function useDocumentTitle(title) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? title + " — " + SUFFIX : previous;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
