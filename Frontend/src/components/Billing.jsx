import { useEffect, useRef, useState } from "react";

import { api } from "../api.js";

// Stripe's webhook usually lands within seconds of the redirect back from checkout.
const UPGRADE_CHECKS = 10;
const UPGRADE_CHECK_MS = 1500;

function longDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function PlanTable({ limits, price }) {
  const rows = [
    ["Requests per minute", "per_minute"],
    ["Requests per day", "per_day"],
    ["Requests per month", "per_month"],
  ];
  return (
    <table className="plan-table">
      <thead>
        <tr>
          <th scope="col">Plan limits</th>
          <th scope="col">Free</th>
          <th scope="col">Pro</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, field]) => (
          <tr key={field}>
            <td>{label}</td>
            <td>{limits.free[field].toLocaleString()}</td>
            <td>{limits.pro[field].toLocaleString()}</td>
          </tr>
        ))}
        <tr>
          <td>Price</td>
          <td>$0</td>
          <td>{price}</td>
        </tr>
      </tbody>
    </table>
  );
}

function subscriptionNote(data) {
  if (data.status === "past_due") {
    return "Your last payment failed. Update your card in Manage billing to stay on Pro.";
  }
  if (data.cancels_at) {
    return "Your subscription ends on " + longDate(data.cancels_at) + ". You keep Pro until then.";
  }
  if (data.current_period_end) {
    return "Renews on " + longDate(data.current_period_end) + ".";
  }
  return "";
}

export default function Billing({ onPlanChanged }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // Effects run twice in development, but the return from checkout should only be handled once.
    if (started.current) return undefined;
    started.current = true;

    const result = new URLSearchParams(window.location.search).get("billing");
    if (result) window.history.replaceState(null, "", window.location.pathname);

    let timer;
    function waitForUpgrade(checksLeft) {
      api
        .getBilling()
        .then((next) => {
          setData(next);
          if (next.plan === "pro") {
            setNotice("Payment received. You're on Pro now.");
            onPlanChanged();
          } else if (checksLeft > 0) {
            timer = setTimeout(() => waitForUpgrade(checksLeft - 1), UPGRADE_CHECK_MS);
          } else {
            setNotice("Payment received. Your upgrade is still on its way, so refresh in a minute.");
          }
        })
        .catch(() => {});
    }

    if (result === "success") {
      setNotice("Confirming your payment...");
      waitForUpgrade(UPGRADE_CHECKS);
    } else {
      if (result === "cancelled") setNotice("Checkout cancelled. You haven't been charged.");
      api
        .getBilling()
        .then(setData)
        .catch(() => {});
    }
    return () => clearTimeout(timer);
  }, [onPlanChanged]);

  if (!data || !data.enabled) return null;

  async function goTo(createSession) {
    setBusy(true);
    setError("");
    try {
      const { url } = await createSession();
      window.location.assign(url);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const isPro = data.plan === "pro";

  return (
    <section className="panel" aria-labelledby="billing-heading">
      <div className="panel-head">
        <h2 id="billing-heading">Billing</h2>
        <span className="pill">{isPro ? "Pro" : "Free"} plan</span>
      </div>

      {notice && (
        <p className="note" role="status">
          {notice}
        </p>
      )}
      {error && <div className="error-banner">{error}</div>}

      <PlanTable limits={data.limits} price={data.price} />

      {isPro && <p className="note">{subscriptionNote(data)}</p>}

      <div className="billing-actions">
        {data.can_manage && (
          <button className="btn outline" disabled={busy} onClick={() => goTo(api.openBillingPortal)}>
            Manage billing
          </button>
        )}
        {!isPro && (
          <button className="btn primary" disabled={busy || data.is_demo} onClick={() => goTo(api.startCheckout)}>
            Upgrade to Pro
          </button>
        )}
      </div>

      {!isPro && data.is_demo && (
        <p className="note">Demo accounts can't be upgraded. Create a free account to try this.</p>
      )}
      {data.test_mode && (
        <p className="note billing-note">
          Stripe test mode, so no real money moves. Pay with card <code>4242 4242 4242 4242</code>, any future date and
          any CVC.
        </p>
      )}
    </section>
  );
}
