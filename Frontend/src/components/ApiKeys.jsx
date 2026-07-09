import { useEffect, useState } from "react";

import { api } from "../api.js";

function formatDate(value) {
  if (!value) {
    return "never";
  }
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);

  function load() {
    api
      .listKeys()
      .then(setKeys)
      .catch(() => {});
  }

  useEffect(load, []);

  async function handleCreate(event) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }
    setCreating(true);
    try {
      const created = await api.createKey(name.trim());
      setNewKey(created.key);
      setName("");
      load();
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id) {
    if (!window.confirm("Revoke this key? Any app using it will stop working.")) {
      return;
    }
    await api.revokeKey(id);
    load();
  }

  async function copyNewKey() {
    await navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>API keys</h2>
      </div>
      <p className="muted">
        Authenticate calls to the Unfurl API with <code>Authorization: Bearer &lt;key&gt;</code>.
        Rate limits and quota depend on your plan (see Usage above).
      </p>

      {newKey && (
        <div className="key-reveal">
          <div className="key-reveal-head">
            <strong>Copy your new key now — it won&apos;t be shown again.</strong>
            <button className="link-btn" onClick={() => setNewKey("")}>
              Dismiss
            </button>
          </div>
          <div className="url-bar">
            <code>{newKey}</code>
            <button className="btn primary small" onClick={copyNewKey}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      )}

      <form className="key-create" onSubmit={handleCreate}>
        <input
          placeholder="Key name (e.g. Production)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn primary small" type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create key"}
        </button>
      </form>

      <ul className="keys-list">
        {keys.length === 0 && <li className="muted key-empty">No keys yet.</li>}
        {keys.map((key) => (
          <li key={key.id} className="key-row">
            <div className="key-main">
              <span className="key-name">{key.name}</span>
              <span className="key-meta">
                <code>{key.prefix}…</code> · last used {formatDate(key.last_used_at)}
              </span>
            </div>
            {key.is_active ? (
              <button className="btn ghost small" onClick={() => handleRevoke(key.id)}>
                Revoke
              </button>
            ) : (
              <span className="pill pill-revoked">Revoked</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
