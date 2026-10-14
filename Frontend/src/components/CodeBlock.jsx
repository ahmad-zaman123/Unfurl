import { useState } from "react";

export default function CodeBlock({ label, children }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(String(children));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable: the text is still selectable */
    }
  }

  return (
    <div className="code-block">
      <div className="code-label">
        <span>{label}</span>
        <button type="button" className="btn ghost small" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre tabIndex={0} role="region" aria-label={label + " (scrollable)"}>
        <code>{children}</code>
      </pre>
    </div>
  );
}
