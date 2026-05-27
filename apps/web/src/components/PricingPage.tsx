/**
 * Pricing page — lists plans from /billing/plans, shows current plan,
 * and offers a Subscribe button that redirects to Stripe Checkout (S03-02).
 *
 * No business logic lives here: gating is server-side. This component only
 * reflects state returned by the API and initiates the Stripe redirect.
 */

import { useEffect, useState } from 'react';
import { ApiError, getBilling, getPlans, startCheckout } from '../api';
import type { BillingStatus, PlanEntry } from '../types';

interface PricingPageProps {
  token: string;
}

export function PricingPage({ token }: PricingPageProps) {
  const [plans, setPlans] = useState<PlanEntry[]>([]);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPlans()
      .then((r) => setPlans(r.plans))
      .catch(() => setError('Could not load plan catalog'));
    getBilling(token)
      .then(setBilling)
      .catch(() => setError('Could not load billing status'));
  }, [token]);

  async function handleSubscribe(plan: string) {
    setBusy(plan);
    setError(null);
    try {
      const url = await startCheckout(token, plan);
      window.location.href = url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start checkout');
      setBusy(null);
    }
  }

  const currentPlan = billing?.plan ?? 'free';
  const isActive = billing?.status === 'active';

  return (
    <div className="pricing">
      <h2>Plans &amp; Pricing</h2>
      {billing && (
        <p className="muted">
          Current plan:{' '}
          <strong>
            {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)}
          </strong>
          {isActive ? ' (active)' : billing.status !== 'none' ? ` (${billing.status})` : ''}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="pricing__grid">
        {plans.map((plan) => {
          const isCurrent = plan.plan === currentPlan && isActive;
          return (
            <div key={plan.plan} className={`card pricing__card${plan.plan === 'pro' ? ' pricing__card--featured' : ''}`}>
              <div className="pricing__header">
                <h3>{plan.display_name}</h3>
                {isCurrent && <span className="pricing__badge">Current plan</span>}
              </div>
              <p className="pricing__price">
                {plan.price_monthly_usd ? (
                  <>
                    <span className="pricing__amount">${plan.price_monthly_usd}</span>
                    <span className="muted">/mo</span>
                  </>
                ) : (
                  <span className="pricing__amount">Free</span>
                )}
              </p>
              <p className="muted">{plan.description}</p>
              <ul className="pricing__features">
                {plan.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              {plan.premium && !isCurrent && (
                <button
                  onClick={() => handleSubscribe(plan.plan)}
                  disabled={busy === plan.plan}
                  type="button"
                >
                  {busy === plan.plan ? 'Redirecting…' : 'Subscribe'}
                </button>
              )}
              {isCurrent && (
                <button disabled type="button">
                  Current plan
                </button>
              )}
              {!plan.premium && (
                <button disabled type="button">
                  Free tier
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
