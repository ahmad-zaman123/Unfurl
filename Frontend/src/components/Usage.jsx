import { useEffect, useState } from "react";

import { api } from "../api.js";

function StatTile({ label, value }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function Usage() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api
      .getUsage()
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return null;
  }

  const { summary, series } = data;
  const max = Math.max(1, ...series.map((point) => point.count));
  const quotaPct = Math.min(100, Math.round((summary.month_used / summary.month_quota) * 100));
  const planLabel = summary.plan.charAt(0).toUpperCase() + summary.plan.slice(1);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Usage</h2>
        <span className="pill pill-plan">{planLabel} plan</span>
      </div>

      <div className="stat-row">
        <StatTile label="Total calls" value={summary.total_calls.toLocaleString()} />
        <StatTile label="Today" value={summary.calls_today.toLocaleString()} />
        <StatTile label="Active keys" value={summary.active_keys} />
        <StatTile label="Cache hit rate" value={summary.cache.hit_rate + "%"} />
      </div>

      <div className="quota">
        <div className="quota-head">
          <span className="muted">Monthly quota</span>
          <span className="muted">
            {summary.month_used.toLocaleString()} / {summary.month_quota.toLocaleString()}
          </span>
        </div>
        <div className="quota-track">
          <div className="quota-fill" style={{ width: quotaPct + "%" }} />
        </div>
      </div>

      <div className="usage-chart">
        {series.map((point) => (
          <div
            key={point.date}
            className="usage-bar"
            style={{ height: Math.round((point.count / max) * 100) + "%" }}
            title={shortDate(point.date) + ": " + point.count}
          />
        ))}
      </div>
      <div className="usage-axis">
        <span>{shortDate(series[0].date)}</span>
        <span>{shortDate(series[series.length - 1].date)}</span>
      </div>
    </div>
  );
}
