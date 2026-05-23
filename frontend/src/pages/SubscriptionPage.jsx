import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Navigate } from 'react-router';
import {
    PiCrownBold,
    PiCheckCircleFill,
    PiXCircleBold,
    PiCreditCardBold,
    PiArrowRightBold,
    PiSpinnerGapBold,
    PiSignOutBold,
    PiUserBold,
    PiShieldCheckBold,
    PiReceiptBold,
    PiArrowSquareOutBold,
} from "react-icons/pi";

export default function SubscriptionPage() {
    const { user, logout, isAuthenticated } = useAuth();
    const [processingPlan, setProcessingPlan] = useState(null);
    const [error, setError] = useState(null);

    const isSubscribed = user?.subscription && ['active', 'trialing'].includes(user.subscription.status);

    if (user?.is_superuser) {
        return <Navigate to="/users" replace />;
    }

    const handleSubscribe = async (hasTrial) => {
        const planType = hasTrial ? 'trial' : 'standard';
        setProcessingPlan(planType);
        setError(null);
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
            const response = await fetch(`${API_BASE}/stripe/create-checkout-session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ has_trial: hasTrial })
            });
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to create session");
            }
            const data = await response.json();
            if (data.url) window.location.href = data.url;
        } catch (err) {
            setError(err.message || "Failed to initialize checkout. Please try again.");
            setProcessingPlan(null);
        }
    };

    const handleManageSubscription = async () => {
        setProcessingPlan('portal');
        setError(null);
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
            const response = await fetch(`${API_BASE}/stripe/create-portal-session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
            });
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to create portal session");
            }
            const data = await response.json();
            if (data.url) window.location.href = data.url;
        } catch (err) {
            setError(err.message || "Failed to open subscription management.");
            setProcessingPlan(null);
        }
    };

    if (isSubscribed) {
        const sub = user.subscription;
        const transactions = user.payment_transactions || [];

        return (
            <div className="min-h-full" style={{ background: 'var(--bg-primary)' }}>
                <div className="max-w-7xl mx-auto px-6 lg:px-10 py-10">

                    {/* Page header */}
                    <div className="mb-8">
                        <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                            Billing &amp; Subscription
                        </h1>
                        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                            Manage your plan, payments, and invoices.
                        </p>
                    </div>

                    {error && (
                        <div className="mb-6 px-5 py-3 rounded-xl flex items-center gap-3 text-sm font-medium"
                            style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)', color: 'var(--danger)' }}>
                            <PiXCircleBold className="text-lg flex-shrink-0" />
                            {error}
                        </div>
                    )}

                    {/* Compact summary strip */}
                    <div className="glass-panel rounded-2xl mb-8 px-6 py-5 flex flex-col md:flex-row md:items-center gap-5 md:gap-0 md:justify-between"
                        style={{ border: '1px solid var(--border)' }}>
                        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
                            {/* Status */}
                            <div className="flex items-center gap-2.5">
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ring-1 ring-inset"
                                    style={sub.status === 'active'
                                        ? { background: 'var(--success-bg)', color: 'var(--success)', '--tw-ring-color': 'color-mix(in srgb, var(--success) 20%, transparent)' }
                                        : { background: 'var(--bg-accent-muted)', color: 'var(--accent)', '--tw-ring-color': 'color-mix(in srgb, var(--accent) 20%, transparent)' }
                                    }>
                                    {sub.status.toUpperCase()}
                                </span>
                            </div>

                            <Divider />

                            {/* Next billing */}
                            <SummaryItem
                                label={sub.status === 'trialing' ? 'Trial Ends' : 'Next Billing'}
                                value={new Date(sub.current_period_end).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                            />

                            <Divider />

                            {/* Member since */}
                            <SummaryItem
                                label="Member Since"
                                value={sub.created_at
                                    ? new Date(sub.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
                                    : '—'}
                            />

                            <Divider />

                            {/* Total paid */}
                            <SummaryItem
                                label="Total Paid"
                                value={`$${(user.total_spent || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
                                valueStyle={{ color: 'var(--success)', fontWeight: 700 }}
                            />

                            <Divider />

                            {/* Transaction count */}
                            <SummaryItem
                                label="Invoices"
                                value={`${user.total_payments || 0} paid`}
                            />
                        </div>

                        {/* Manage button */}
                        <button
                            onClick={handleManageSubscription}
                            disabled={processingPlan !== null}
                            className="flex-shrink-0 flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-[0.98] disabled:opacity-50"
                            style={{ background: 'var(--bg-hover)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                        >
                            {processingPlan === 'portal'
                                ? <PiSpinnerGapBold className="animate-spin" />
                                : <><PiCreditCardBold /><span>Manage Billing</span><PiArrowRightBold className="text-xs opacity-60" /></>
                            }
                        </button>
                    </div>

                    {/* Billing history — full width, dominant */}
                    <div className="glass-panel rounded-2xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                        {/* Table header */}
                        <div className="flex items-center justify-between px-6 py-5" style={{ borderBottom: '1px solid var(--border)' }}>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                    style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                    <PiReceiptBold style={{ color: 'var(--accent)' }} />
                                </div>
                                <div>
                                    <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Billing History</h2>
                                    <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>All payments processed securely via Stripe</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                                <PiShieldCheckBold style={{ color: 'var(--success)' }} />
                                <span>Stripe Secured</span>
                            </div>
                        </div>

                        {/* Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-left" style={{ minWidth: '700px' }}>
                                <thead>
                                    <tr style={{ background: 'var(--bg-hover)', borderBottom: '1px solid var(--border)' }}>
                                        <th className="px-6 py-3.5 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-tertiary)', width: '180px' }}>Date</th>
                                        <th className="px-6 py-3.5 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-tertiary)' }}>Description</th>
                                        <th className="px-6 py-3.5 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-tertiary)', width: '160px' }}>Amount</th>
                                        <th className="px-6 py-3.5 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-tertiary)', width: '130px' }}>Status</th>
                                        <th className="px-6 py-3.5 text-[11px] font-bold uppercase tracking-widest text-right" style={{ color: 'var(--text-tertiary)', width: '140px' }}>Invoice</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {transactions.length > 0 ? (
                                        transactions.map((payment, idx) => (
                                            <tr
                                                key={payment.id}
                                                style={{
                                                    borderBottom: idx < transactions.length - 1 ? '1px solid var(--border)' : 'none',
                                                    height: '60px',
                                                }}
                                                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                                                onMouseLeave={e => e.currentTarget.style.background = ''}
                                            >
                                                <td className="px-6 text-sm" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                                    {new Date(payment.created_at).toLocaleDateString(undefined, {
                                                        year: 'numeric', month: 'short', day: 'numeric'
                                                    })}
                                                    <span className="ml-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                                                        {new Date(payment.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                                    </span>
                                                </td>
                                                <td className="px-6 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                                    Pro Annual Subscription
                                                </td>
                                                <td className="px-6 text-sm font-bold" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                                                    ${(payment.amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                    <span className="ml-1 text-xs font-normal" style={{ color: 'var(--text-tertiary)' }}>
                                                        {(payment.currency ?? 'USD').toUpperCase()}
                                                    </span>
                                                </td>
                                                <td className="px-6">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold ${payment.status === 'succeeded' ? 'si-badge-success' : 'si-badge-danger'}`}
                                                        style={{ border: `1px solid color-mix(in srgb, ${payment.status === 'succeeded' ? 'var(--success)' : 'var(--danger)'} 25%, transparent)` }}>
                                                        <span className="w-1.5 h-1.5 rounded-full inline-block"
                                                            style={{ background: payment.status === 'succeeded' ? 'var(--success)' : 'var(--danger)' }} />
                                                        {payment.status === 'succeeded' ? 'Paid' : 'Failed'}
                                                    </span>
                                                </td>
                                                <td className="px-6 text-right">
                                                    {payment.invoice_url ? (
                                                        <a
                                                            href={payment.invoice_url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                                                            style={{ color: 'var(--accent)', background: 'var(--bg-accent-muted)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}
                                                        >
                                                            <PiArrowSquareOutBold />
                                                            View Invoice
                                                        </a>
                                                    ) : (
                                                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>—</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))
                                    ) : (
                                        <tr>
                                            <td colSpan="5" className="px-6 py-16 text-center" style={{ color: 'var(--text-tertiary)' }}>
                                                <PiReceiptBold className="mx-auto text-3xl mb-2 opacity-40" />
                                                <p className="text-sm">No payment records found.</p>
                                                <p className="text-xs mt-1">Payments may take a moment to appear after checkout.</p>
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="mt-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            {user?.picture ? (
                                <img src={user.picture} alt="" className="w-8 h-8 rounded-full" style={{ border: '1px solid var(--border)' }} />
                            ) : (
                                <div className="w-8 h-8 rounded-full flex items-center justify-center"
                                    style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                                    <PiUserBold className="text-sm" />
                                </div>
                            )}
                            <div>
                                <p className="text-sm font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>{user?.name || user?.full_name}</p>
                                <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{user?.email}</p>
                            </div>
                        </div>
                        <button
                            onClick={logout}
                            className="flex items-center gap-2 text-sm font-medium transition-colors py-1.5 px-3 rounded-lg"
                            style={{ color: 'var(--text-tertiary)' }}
                            onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
                            onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = ''; }}
                        >
                            <PiSignOutBold />
                            <span>Sign Out</span>
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // ── Unauthenticated / unsubscribed state ──────────────────────────────────
    return (
        <div className="min-h-full p-6 lg:p-10 flex flex-col items-center relative">
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] blur-[160px] rounded-full"
                    style={{ background: 'color-mix(in srgb, var(--accent) 4%, transparent)' }} />
            </div>

            <div className="w-full max-w-5xl relative z-10 flex flex-col items-center">
                <div className="text-center mb-10">
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest mb-6"
                        style={{ background: 'var(--bg-accent-muted)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)', color: 'var(--accent)' }}>
                        <PiCrownBold className="text-lg" />
                        <span>Professional Access</span>
                    </div>
                    <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight mb-3" style={{ color: 'var(--text-primary)' }}>
                        Scale your Intelligence
                    </h2>
                    <p className="text-lg max-w-2xl mx-auto leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        The ultimate OSINT toolkit for Signal. Search extensive records, track historical changes, and export actionable data.
                    </p>
                </div>

                {error && (
                    <div className="w-full max-w-md px-6 py-4 rounded-xl mb-12 flex items-center gap-4 animate-in fade-in slide-in-from-top-4"
                        style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)', color: 'var(--danger)' }}>
                        <PiXCircleBold className="text-2xl flex-shrink-0" />
                        <p className="text-sm font-medium">{error}</p>
                    </div>
                )}

                <div className="w-full max-w-lg">
                    <div className="glass-panel rounded-3xl shadow-2xl relative group overflow-hidden flex flex-col" style={{ border: '1px solid var(--border)' }}>
                        <div className="absolute top-0 inset-x-0 h-1.5" style={{ background: 'linear-gradient(to right, var(--accent), var(--accent-hover))' }} />

                        <div className="p-8 flex-1">
                            <div className="flex justify-between items-center mb-8">
                                <div>
                                    <h3 className="text-2xl font-extrabold" style={{ color: 'var(--text-primary)' }}>Pro Annual</h3>
                                    <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Full feature set for organizations.</p>
                                </div>
                                <span className="text-[10px] font-bold uppercase tracking-widest px-3 py-1 rounded-lg"
                                    style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
                                    Recommended
                                </span>
                            </div>

                            <div className="mb-8 p-6 rounded-2xl" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                <div className="flex items-baseline" style={{ color: 'var(--text-primary)' }}>
                                    <span className="text-5xl font-black tracking-tighter">$1299</span>
                                    <span className="ml-3 text-lg font-medium" style={{ color: 'var(--text-tertiary)' }}>/ year</span>
                                </div>
                                <p className="text-xs font-medium mt-3 uppercase tracking-wider italic" style={{ color: 'var(--text-tertiary)' }}>No hidden fees. Full platform access.</p>
                            </div>

                            <div className="space-y-3.5 mb-8">
                                <FeatureItem text="Comprehensive User & Group Search" />
                                <FeatureItem text="Deep Historical Membership Logs" />
                                <FeatureItem text="Advanced Data Export (CSV/JSON/PDF)" />
                                <FeatureItem text="Full Portal Access & Web Interface" />
                                <FeatureItem text="Priority 24/7 Technical Support" />
                            </div>

                            <button
                                onClick={() => handleSubscribe(false)}
                                disabled={processingPlan !== null}
                                className="w-full h-16 relative overflow-hidden rounded-2xl font-bold text-lg transition-all shadow-glow active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed group/btn flex items-center justify-center gap-3"
                                style={{ background: 'linear-gradient(to bottom right, var(--accent), var(--accent-hover))', color: 'var(--text-on-accent)' }}
                            >
                                {processingPlan === 'standard'
                                    ? <PiSpinnerGapBold className="text-2xl animate-spin" />
                                    : <><span>Upgrade to Pro Now</span><PiArrowRightBold className="group-hover/btn:translate-x-1.5 transition-transform" /></>
                                }
                            </button>
                        </div>
                    </div>
                </div>

                <div className="mt-16 text-center text-sm max-w-md mx-auto leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
                    By upgrading, you agree to our Terms of Service and Privacy Policy. Secure processing provided by <strong>Stripe</strong>.
                </div>

                <div className="mt-12">
                    <button
                        onClick={logout}
                        className="flex items-center gap-2 text-sm font-medium transition-colors py-2 px-4 rounded-lg"
                        style={{ color: 'var(--text-tertiary)' }}
                        onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = ''; }}
                    >
                        <PiSignOutBold />
                        <span>Sign Out of {user?.name || user?.email}</span>
                    </button>
                </div>
            </div>
        </div>
    );
}

function SummaryItem({ label, value, valueStyle = {} }) {
    return (
        <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)', ...valueStyle }}>{value}</p>
        </div>
    );
}

function Divider() {
    return <div className="hidden md:block w-px h-8 self-center" style={{ background: 'var(--border)' }} />;
}

function FeatureItem({ text }) {
    return (
        <div className="flex items-center gap-4 group/item">
            <div className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center"
                style={{ background: 'var(--success-bg)', border: '1px solid color-mix(in srgb, var(--success) 20%, transparent)' }}>
                <PiCheckCircleFill className="text-sm" style={{ color: 'var(--success)' }} />
            </div>
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{text}</span>
        </div>
    );
}
