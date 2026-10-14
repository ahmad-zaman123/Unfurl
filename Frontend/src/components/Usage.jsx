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

  if (!data) return null;

  const { summary, series } = data;
  const total = series.reduce((sum, point) => sum + point.count, 0);
  const max = Math.max(1, ...series.map((point) => point.count));
  const quotaPct = Math.min(100, Math.round((summary.month_used / summary.month_quota) * 100));
  const planLabel = summary.plan.charAt(0).toUpperCase() + summary.plan.slice(1);
  const level = quotaPct >= 90 ? "over" : quotaPct >= 75 ? "warn" : "ok";
  const note =
    level === "over" ? "Near the monthly limit" : level === "warn" ? "Approaching the monthly limit" : "";

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Usage</h2>
        <span className="pill">{planLabel} plan</span>
      </div>

      <div className="stat-row">
        <StatTile label="Total calls" value={summary.total_calls.toLocaleString()} />
        <StatTile label="Today" value={summary.calls_today.toLocaleString()} />
        <StatTile label="Active keys" value={summary.active_keys} />
        <StatTile label="Cache hits" value={summary.cache.hit_rate + "%"} />
      </div>

      <div className="quota">
        <div className="quota-head">
          <span>Monthly quota</span>
          <span>
            {summary.month_used.toLocaleString()} of {summary.month_quota.toLocaleString()} ({quotaPct}%)
          </span>
        </div>
        <div
          className="quota-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={quotaPct}
          aria-label="Monthly quota used"
        >
          <div className={"quota-fill " + level} style={{ width: quotaPct + "%" }} />
        </div>
        {note && <div className={"quota-note " + level}>{note}</div>}
      </div>

      {total === 0 ? (
        <p className="note">
          No calls in the last {series.length} days. Make a request with an API key and it shows up here.
        </p>
      ) : (
        <>
          <div
            className="usage-chart"
            role="img"
            aria-label={
              "Calls per day from " +
              shortDate(series[0].date) +
              " to " +
              shortDate(series[series.length - 1].date) +
              ", peak " +
              max.toLocaleString()
            }
          >
            {series.map((point) => (
              <div
                key={point.date}
                className="usage-bar"
                style={{ height: Math.max(2, Math.round((point.count / max) * 100)) + "%" }}
                title={shortDate(point.date) + ": " + point.count.toLocaleString() + " calls"}
              />
            ))}
          </div>
          <div className="usage-axis">
            <span>{shortDate(series[0].date)}</span>
            <span>
              Peak {max.toLocaleString()} {max === 1 ? "call" : "calls"} a day
            </span>
            <span>{shortDate(series[series.length - 1].date)}</span>
          </div>
        </>
      )}
    </div>
  );
}
