import { useEffect, useState } from "react";

import { api } from "../api.js";

function formatDate(value) {
  if (!value) return "never";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [confirmId, setConfirmId] = useState(null);
  const [error, setError] = useState("");

  function load() {
    api
      .listKeys()
      .then(setKeys)
      .catch(() => setError("Could not load your keys."));
  }

  useEffect(load, []);

  async function handleCreate(event) {
    event.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError("");
    try {
      const created = await api.createKey(name.trim());
      setNewKey(created.key);
      setName("");
      load();
    } catch (err) {
      setError(err?.message || "Could not create the key.");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id) {
    setConfirmId(null);
    try {
      await api.revokeKey(id);
      load();
    } catch (err) {
      setError(err?.message || "Could not revoke the key.");
    }
  }

  async function copyNewKey() {
    try {
      await navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable: the key is still selectable */
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>API keys</h2>
      </div>
      <p className="muted">
        Authenticate calls with <code>Authorization: Bearer &lt;key&gt;</code>. Limits and quota depend on your
        plan (see Usage).
      </p>

      {newKey && (
        <div className="key-reveal" role="status">
          <div className="key-reveal-head">
            <strong>Copy your new key now. It won&apos;t be shown again.</strong>
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

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <form className="key-create" onSubmit={handleCreate}>
        <label className="sr-only" htmlFor="key-name">
          Key name
        </label>
        <input
          id="key-name"
          placeholder="Key name, e.g. Production"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn primary small" type="submit" disabled={creating || !name.trim()}>
          {creating ? "Creating…" : "Create key"}
        </button>
      </form>

      <ul className="keys-list">
        {keys.length === 0 && <li className="muted key-empty">No keys yet. Create one to call the API.</li>}
        {keys.map((key) => (
          <li key={key.id} className="key-row">
            <div className="key-main">
              <span className="key-name">{key.name}</span>
              <span className="key-meta">
                <code>{key.prefix}…</code> · last used {formatDate(key.last_used_at)}
              </span>
            </div>
            {key.is_active ? (
              confirmId === key.id ? (
                <span className="key-actions">
                  <button className="btn outline small" onClick={() => handleRevoke(key.id)}>
                    Revoke; apps using it stop working
                  </button>
                  <button className="btn ghost small" onClick={() => setConfirmId(null)}>
                    Cancel
                  </button>
                </span>
              ) : (
                <button className="btn ghost small" onClick={() => setConfirmId(key.id)}>
                  Revoke
                </button>
              )
            ) : (
              <span className="pill pill-revoked">Revoked</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
