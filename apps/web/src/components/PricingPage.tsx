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
      <BillingSummary billing={billing} currentPlan={currentPlan} isActive={isActive} />
      {error && <p className="error">{error}</p>}
      <div className="pricing__grid">
        {plans.map((plan) => (
          <PlanCard
            key={plan.plan}
            busy={busy}
            currentPlan={currentPlan}
            isActive={isActive}
            plan={plan}
            onSubscribe={handleSubscribe}
          />
        ))}
      </div>
    </div>
  );
}

function BillingSummary({
  billing,
  currentPlan,
  isActive,
}: {
  billing: BillingStatus | null;
  currentPlan: string;
  isActive: boolean;
}) {
  if (!billing) return null;
  const status = isActive ? ' (active)' : billing.status !== 'none' ? ` (${billing.status})` : '';
  return (
    <p className="muted">
      Current plan: <strong>{formatPlan(currentPlan)}</strong>
      {status}
    </p>
  );
}

function PlanCard({
  busy,
  currentPlan,
  isActive,
  plan,
  onSubscribe,
}: {
  busy: string | null;
  currentPlan: string;
  isActive: boolean;
  plan: PlanEntry;
  onSubscribe: (plan: string) => void;
}) {
  const isCurrent = plan.plan === currentPlan && isActive;
  const featured = plan.plan === 'pro' ? ' pricing__card--featured' : '';
  return (
    <div className={`card pricing__card${featured}`}>
      <PlanHeader isCurrent={isCurrent} plan={plan} />
      <PlanPrice plan={plan} />
      <p className="muted">{plan.description}</p>
      <ul className="pricing__features">
        {plan.features.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
      <PlanButton
        busy={busy}
        isCurrent={isCurrent}
        plan={plan}
        onSubscribe={onSubscribe}
      />
    </div>
  );
}

function PlanHeader({ isCurrent, plan }: { isCurrent: boolean; plan: PlanEntry }) {
  return (
    <div className="pricing__header">
      <h3>{plan.display_name}</h3>
      {isCurrent && <span className="pricing__badge">Current plan</span>}
    </div>
  );
}

function PlanPrice({ plan }: { plan: PlanEntry }) {
  return (
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
  );
}

function PlanButton({
  busy,
  isCurrent,
  plan,
  onSubscribe,
}: {
  busy: string | null;
  isCurrent: boolean;
  plan: PlanEntry;
  onSubscribe: (plan: string) => void;
}) {
  if (isCurrent) return <button disabled type="button">Current plan</button>;
  if (!plan.premium) return <button disabled type="button">Free tier</button>;
  return (
    <button
      onClick={() => onSubscribe(plan.plan)}
      disabled={busy === plan.plan}
      type="button"
    >
      {busy === plan.plan ? 'Redirecting...' : 'Subscribe'}
    </button>
  );
}

function formatPlan(plan: string) {
  return plan.charAt(0).toUpperCase() + plan.slice(1);
}
