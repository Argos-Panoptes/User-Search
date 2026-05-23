import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import apiClient from '../services/api';
import { useAuth } from '../context/AuthContext';
import Fuse from 'fuse.js';
import {
    PiDatabaseDuotone,
    PiCopyBold,
    PiCheckBold,
    PiArrowRightBold,
    PiUploadSimpleBold,
    PiUsersBold,
    PiSquaresFourDuotone,
    PiImageBold,
    PiLinkBold,
    PiArrowsClockwiseBold,
    PiFileTextBold,
    PiClockBold,
    PiWarningBold,
    PiMagnifyingGlassBold,
    PiDownloadSimpleBold,
    PiListBold,
    PiCaretDownBold,
    PiXBold,
    PiCommandBold,
    PiKeyBold,
    PiLockKeyBold,
    PiLockOpenBold,
    PiEyeBold,
    PiEyeSlashBold,
} from 'react-icons/pi';

// ── helpers ────────────────────────────────────────────────────────────────

function useCopy(text, timeout = 1800) {
    const [copied, setCopied] = useState(false);
    const copy = () => {
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), timeout);
        });
    };
    return [copied, copy];
}

// ── primitives ─────────────────────────────────────────────────────────────

const METHOD_COLORS = {
    GET: { bg: 'var(--success-bg)', color: 'var(--success)', border: 'color-mix(in srgb, var(--success) 25%, transparent)' },
    POST: { bg: 'var(--bg-accent-muted)', color: 'var(--accent)', border: 'color-mix(in srgb, var(--accent) 25%, transparent)' },
    DELETE: { bg: 'var(--danger-bg)', color: 'var(--danger)', border: 'color-mix(in srgb, var(--danger) 25%, transparent)' },
    PATCH: { bg: 'var(--warning-bg)', color: 'var(--warning)', border: 'color-mix(in srgb, var(--warning) 25%, transparent)' },
};

function MethodBadge({ method }) {
    const c = METHOD_COLORS[method] || METHOD_COLORS.GET;
    return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold tracking-wide"
            style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>
            {method}
        </span>
    );
}

function CodeBlock({ code, language = 'bash' }) {
    const [copied, copy] = useCopy(code);
    return (
        <div className="relative group rounded-xl overflow-hidden mt-3 mb-1"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between px-4 py-2 border-b"
                style={{ borderColor: 'var(--border)', background: 'var(--bg-hover)' }}>
                <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{language}</span>
                <button onClick={copy}
                    className="flex items-center gap-1.5 text-xs px-2 py-1 rounded transition-all"
                    style={{
                        color: copied ? 'var(--success)' : 'var(--text-secondary)',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                    }}>
                    {copied ? <PiCheckBold /> : <PiCopyBold />}
                    {copied ? 'Copied' : 'Copy'}
                </button>
            </div>
            <pre className="px-4 py-4 overflow-x-auto text-sm font-mono leading-relaxed custom-scrollbar m-0"
                style={{ color: 'var(--text-primary)', whiteSpace: 'pre' }}>
                <code>{code}</code>
            </pre>
        </div>
    );
}

function InlineCode({ children }) {
    return (
        <code className="px-1.5 py-0.5 rounded text-xs font-mono"
            style={{ background: 'var(--bg-hover)', color: 'var(--accent)', border: '1px solid var(--border)' }}>
            {children}
        </code>
    );
}

function Note({ type = 'info', children }) {
    const styles = {
        info: { bg: 'var(--bg-accent-muted)', border: 'color-mix(in srgb, var(--accent) 30%, transparent)', color: 'var(--accent)', icon: <PiFileTextBold /> },
        warning: { bg: 'var(--warning-bg)', border: 'color-mix(in srgb, var(--warning) 30%, transparent)', color: 'var(--warning)', icon: <PiWarningBold /> },
        tip: { bg: 'var(--success-bg)', border: 'color-mix(in srgb, var(--success) 30%, transparent)', color: 'var(--success)', icon: <PiCheckBold /> },
    };
    const s = styles[type];
    return (
        <div className="flex gap-3 rounded-xl p-4 mt-4 mb-1 text-sm leading-relaxed"
            style={{ background: s.bg, border: `1px solid ${s.border}` }}>
            <span className="mt-0.5 flex-shrink-0" style={{ color: s.color }}>{s.icon}</span>
            <span style={{ color: 'var(--text-primary)' }}>{children}</span>
        </div>
    );
}

function Steps({ steps }) {
    return (
        <div className="mt-4 space-y-0">
            {steps.map((step, i) => (
                <div key={i} className="flex gap-4">
                    <div className="flex flex-col items-center flex-shrink-0">
                        <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                            style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)', minWidth: '28px' }}>
                            {i + 1}
                        </div>
                        {i < steps.length - 1 && (
                            <div className="w-px flex-1 my-1" style={{ background: 'var(--border)', minHeight: '20px' }} />
                        )}
                    </div>
                    <div className="pb-5 pt-0.5 flex-1 min-w-0">
                        <div className="text-sm font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>{step.title}</div>
                        {step.desc && <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{step.desc}</div>}
                    </div>
                </div>
            ))}
        </div>
    );
}

function SectionTitle({ icon: Icon, children }) {
    return (
        <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
                <Icon />
            </div>
            <h2 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>{children}</h2>
        </div>
    );
}

function EndpointCard({ id, method, path, description, children }) {
    return (
        <div id={id} className="rounded-xl overflow-hidden mb-6"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-3 px-5 py-4 border-b min-w-0" style={{ borderColor: 'var(--border)' }}>
                <MethodBadge method={method} />
                <code className="text-sm font-mono font-semibold min-w-0 break-all" style={{ color: 'var(--text-primary)' }}>{path}</code>
                {description && (
                    <span className="text-xs ml-auto flex-shrink-0 hidden sm:block" style={{ color: 'var(--text-secondary)' }}>{description}</span>
                )}
            </div>
            <div className="px-5 py-4 space-y-4">{children}</div>
        </div>
    );
}

function FieldTable({ fields }) {
    return (
        <div className="rounded-lg overflow-x-auto mt-2" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-sm min-w-[480px]">
                <thead>
                    <tr style={{ background: 'var(--bg-hover)' }}>
                        <th className="text-left px-4 py-2.5 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Field</th>
                        <th className="text-left px-4 py-2.5 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Type</th>
                        <th className="text-left px-4 py-2.5 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Required</th>
                        <th className="text-left px-4 py-2.5 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {fields.map((f, i) => (
                        <tr key={i} style={{ borderTop: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'var(--bg-table-row-alt)' }}>
                            <td className="px-4 py-2.5"><InlineCode>{f.name}</InlineCode></td>
                            <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--warning)' }}>{f.type}</td>
                            <td className="px-4 py-2.5">
                                <span className="text-xs font-medium px-2 py-0.5 rounded"
                                    style={f.required
                                        ? { background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }
                                        : { background: 'var(--bg-hover)', color: 'var(--text-tertiary)' }}>
                                    {f.required ? 'required' : 'optional'}
                                </span>
                            </td>
                            <td className="px-4 py-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>{f.desc}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function Divider() {
    return <div className="my-10" style={{ height: '1px', background: 'var(--border)' }} />;
}

// ── nav config ─────────────────────────────────────────────────────────────

const SEARCH_NAV = [
    { id: 'overview', label: 'Overview', icon: PiDatabaseDuotone, endpoints: [] },
    { id: 'auth', label: 'Authentication', icon: PiFileTextBold, endpoints: [] },
    {
        id: 'user-search', label: 'User Search', icon: PiMagnifyingGlassBold,
        endpoints: [
            { id: 'ep-users-search', method: 'POST', path: '/users/search' },
            { id: 'ep-users-details', method: 'POST', path: '/users/details' },
            { id: 'ep-users-timeline', method: 'POST', path: '/users/timeline' },
            { id: 'ep-users-history-profile', method: 'POST', path: '/users/history/profile' },
            { id: 'ep-users-history-memberships', method: 'POST', path: '/users/history/memberships' },
            { id: 'ep-users-export', method: 'POST', path: '/users/export' },
        ],
    },
    {
        id: 'group-search', label: 'Group Search', icon: PiSquaresFourDuotone,
        endpoints: [
            { id: 'ep-groups-retention', method: 'GET', path: '/groups/retention-periods' },
            { id: 'ep-groups-search', method: 'POST', path: '/groups/search' },
            { id: 'ep-groups-details', method: 'POST', path: '/groups/details' },
            { id: 'ep-groups-timeline', method: 'POST', path: '/groups/timeline' },
            { id: 'ep-groups-history', method: 'POST', path: '/groups/history' },
            { id: 'ep-groups-history-members', method: 'POST', path: '/groups/history-members' },
            { id: 'ep-groups-export', method: 'POST', path: '/groups/export' },
        ],
    },
    {
        id: 'media', label: 'Media & Avatars', icon: PiImageBold,
        endpoints: [
            { id: 'ep-media-download', method: 'GET', path: '/media/{mediaId}/download' },
        ],
    },
];

const INGESTION_NAV = [
    {
        id: 'upload', label: 'File Upload Flow', icon: PiUploadSimpleBold,
        endpoints: [
            { id: 'ep-upload-init', method: 'POST', path: '/uploads/init' },
            { id: 'ep-upload-chunk', method: 'POST', path: '/uploads/{id}/chunk' },
            { id: 'ep-upload-complete', method: 'POST', path: '/uploads/{id}/complete' },
        ],
    },
    {
        id: 'ingest-users', label: 'Ingest Users', icon: PiUsersBold,
        endpoints: [
            { id: 'ep-ingest-users', method: 'POST', path: '/ingest/users' },
        ],
    },
    {
        id: 'ingest-groups', label: 'Ingest Groups', icon: PiListBold,
        endpoints: [
            { id: 'ep-ingest-groups', method: 'POST', path: '/ingest/groups' },
        ],
    },
    {
        id: 'ingest-avatars', label: 'Ingest Avatars', icon: PiImageBold,
        endpoints: [
            { id: 'ep-ingest-avatars', method: 'POST', path: '/ingest/avatars' },
        ],
    },
    {
        id: 'links', label: 'Link Reconstruction', icon: PiLinkBold,
        endpoints: [
            { id: 'ep-links-reconstruct', method: 'POST', path: '/ingest/reconstruct-links' },
        ],
    },
    {
        id: 'avatar-sync', label: 'Avatar Sync', icon: PiArrowsClockwiseBold,
        endpoints: [
            { id: 'ep-sync-start', method: 'POST', path: '/ingest/avatar-sync' },
            { id: 'ep-sync-stop', method: 'POST', path: '/ingest/avatar-sync/{id}/stop' },
            { id: 'ep-sync-failures', method: 'GET', path: '/ingest/avatar-sync/{id}/failures' },
        ],
    },
    {
        id: 'jobs', label: 'Job Status & Logs', icon: PiClockBold,
        endpoints: [
            { id: 'ep-jobs-status', method: 'GET', path: '/jobs/{job_id}' },
            { id: 'ep-jobs-logs', method: 'GET', path: '/jobs/{job_id}/logs' },
        ],
    },
];

// ── section components ─────────────────────────────────────────────────────

function OverviewSection() {
    return (
        <section id="overview">
            <SectionTitle icon={PiDatabaseDuotone}>Overview</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                The API covers two main areas. <strong style={{ color: 'var(--text-primary)' }}>Search & Query</strong> — search users and groups, retrieve full details, fetch timeline history, and download avatars. These endpoints are available to any authenticated user with an active subscription. <strong style={{ color: 'var(--text-primary)' }}>Ingestion</strong> — bulk-load users, groups, avatars, reconstruct invite links, and run avatar sync. Ingestion endpoints are admin-only.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
                {[
                    { label: 'Base URL', value: '/app/api/v1' },
                    { label: 'Auth Required', value: 'Yes — Admin only' },
                    { label: 'Auth Method', value: 'X-API-Key header or Bearer JWT' },
                    { label: 'Content-Type', value: 'application/json' },
                ].map(item => (
                    <div key={item.label} className="rounded-xl p-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--text-tertiary)' }}>{item.label}</div>
                        <div className="text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{item.value}</div>
                    </div>
                ))}
            </div>
            <Note type="info">
                All ingestion endpoints kick off asynchronous background jobs. The response returns a <InlineCode>job_id</InlineCode> you use to poll for status and stream logs.
            </Note>
        </section>
    );
}

// ── password strength ──────────────────────────────────────────────────────

const PASSWORD_RULES = [
    { key: 'len',   label: 'At least 12 characters',       test: p => p.length >= 12 },
    { key: 'upper', label: 'At least 2 uppercase letters', test: p => (p.match(/[A-Z]/g) || []).length >= 2 },
    { key: 'lower', label: 'At least 2 lowercase letters', test: p => (p.match(/[a-z]/g) || []).length >= 2 },
    { key: 'digit', label: 'At least 2 numbers',           test: p => (p.match(/[0-9]/g) || []).length >= 2 },
    { key: 'sym',   label: 'At least 2 special characters', test: p => (p.match(/[^A-Za-z0-9]/g) || []).length >= 2 },
];

function PasswordStrengthChecklist({ password }) {
    if (!password) return null;
    return (
        <ul className="mt-2 space-y-1">
            {PASSWORD_RULES.map(rule => {
                const ok = rule.test(password);
                return (
                    <li key={rule.key} className="flex items-center gap-1.5 text-xs" style={{ color: ok ? 'var(--success, #22c55e)' : 'var(--text-tertiary)' }}>
                        <PiCheckBold className={ok ? '' : 'opacity-0'} style={{ flexShrink: 0 }} />
                        <span style={{ textDecoration: ok ? 'none' : 'none' }}>{rule.label}</span>
                    </li>
                );
            })}
        </ul>
    );
}

function isPasswordValid(password) {
    return PASSWORD_RULES.every(r => r.test(password));
}

// ── set/reset password modal ────────────────────────────────────────────────

function SetApiPasswordModal({ onClose, onSuccess }) {
    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const valid = isPasswordValid(password) && password === confirm;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!valid) return;
        setSubmitting(true);
        setError('');
        try {
            await apiClient.post('/auth/set-api-password', { password, confirm_password: confirm });
            onSuccess();
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to set password');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[300] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60" onClick={onClose} />
            <div className="relative rounded-xl w-full max-w-md shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2">
                        <PiLockKeyBold style={{ color: 'var(--accent)' }} />
                        <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Set API Password</h3>
                    </div>
                    <button onClick={onClose} className="si-icon-button"><PiXBold /></button>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        This password is used only for obtaining JWT tokens via the <code style={{ fontSize: 11 }}>POST /auth/password-token</code> endpoint — not for signing in to the app.
                    </p>
                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Password</label>
                        <div className="relative">
                            <input
                                type={showPw ? 'text' : 'password'}
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                className="si-input pr-10"
                                placeholder="New password"
                                autoFocus
                            />
                            <button type="button" onClick={() => setShowPw(s => !s)} className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }}>
                                {showPw ? <PiEyeSlashBold /> : <PiEyeBold />}
                            </button>
                        </div>
                        <PasswordStrengthChecklist password={password} />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Confirm Password</label>
                        <input
                            type={showPw ? 'text' : 'password'}
                            value={confirm}
                            onChange={e => setConfirm(e.target.value)}
                            className="si-input"
                            placeholder="Repeat password"
                        />
                        {confirm && password !== confirm && (
                            <p className="text-xs mt-1" style={{ color: 'var(--danger)' }}>Passwords do not match</p>
                        )}
                    </div>
                    {error && <p className="text-xs" style={{ color: 'var(--danger)' }}>{error}</p>}
                    <div className="flex gap-3 justify-end pt-2">
                        <button type="button" onClick={onClose} className="si-button-secondary">Cancel</button>
                        <button type="submit" disabled={!valid || submitting} className="si-button-primary" style={{ opacity: !valid || submitting ? 0.4 : 1 }}>
                            {submitting ? 'Saving…' : 'Save Password'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── auth section ────────────────────────────────────────────────────────────

function AuthSection() {
    const { user } = useAuth();
    const isAdmin = user?.is_superuser;
    const [hasPassword, setHasPassword] = useState(null); // null = loading
    const [showModal, setShowModal] = useState(false);
    const [removing, setRemoving] = useState(false);

    useEffect(() => {
        apiClient.get('/auth/api-password-status')
            .then(r => setHasPassword(r.data.has_api_password))
            .catch(() => setHasPassword(false));
    }, []);

    const handleRemove = async () => {
        if (!confirm('Remove your API password? You will no longer be able to get tokens via email/password.')) return;
        setRemoving(true);
        try {
            await apiClient.delete('/auth/api-password');
            setHasPassword(false);
        } finally {
            setRemoving(false);
        }
    };

    return (
        <section id="auth">
            <SectionTitle icon={PiFileTextBold}>Authentication</SectionTitle>
            <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--text-secondary)' }}>
                {isAdmin
                    ? 'Admin access supports two methods: API keys for B2B/internal automation, and JWT Bearer tokens for programmatic access.'
                    : 'Paid user access uses JWT Bearer tokens obtained via email + API password. Set your password below to enable scripted access.'}
            </p>

            {/* ── API Key section — admin only ── */}
            {isAdmin && (
                <>
                    <h3 className="text-base font-bold mb-3" style={{ color: 'var(--text-primary)' }}>
                        API Key Authentication
                        <span className="text-xs font-normal ml-2 px-2 py-0.5 rounded-full" style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>Admin only</span>
                    </h3>
                    <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                        API keys are for B2B and internal integrations. They grant access to ingestion and job endpoints.
                    </p>
                    <Steps steps={[
                        { title: 'Go to API Keys in the admin panel', desc: 'Navigate to Admin → API Keys. Only admin accounts can create API keys.' },
                        { title: 'Click "Create Key"', desc: 'Give the key a name, set an expiry and per-minute quota, then click Create.' },
                        { title: 'Copy the key immediately', desc: 'The full key (usk_xxx.secret) is shown only once. Store it securely.' },
                        { title: 'Use it in the X-API-Key header', desc: 'Pass the full key string in every request.' },
                    ]} />
                    <Note type="warning">API keys are shown in full only at creation time. If you lose it, revoke and create a new one.</Note>
                    <h3 className="text-sm font-semibold mb-2 mt-6" style={{ color: 'var(--text-primary)' }}>Using an API Key</h3>
                    <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/users \\
  -H "X-API-Key: usk_abcd1234.your_secret_here" \\
  -H "Content-Type: application/json" \\
  -d '{"upload_id": "..."}'`} />
                </>
            )}

            {/* ── JWT Bearer section ── */}
            <h3 className={`text-base font-bold mb-3 ${isAdmin ? 'mt-8' : ''}`} style={{ color: 'var(--text-primary)' }}>
                JWT Bearer Authentication
                {!isAdmin && <span className="text-xs font-normal ml-2 px-2 py-0.5 rounded-full" style={{ background: 'var(--accent-bg)', color: 'var(--accent)' }}>Paid users</span>}
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                {isAdmin
                    ? 'Admins can also use JWT Bearer tokens. Obtain one via email + API password.'
                    : 'Use your email and API password to get a short-lived JWT for scripted access to the search APIs.'}
            </p>

            {/* ── Set/reset password card ── */}
            <div className="rounded-xl p-4 mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" style={{ background: 'var(--bg-accent-muted)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3 min-w-0">
                    {hasPassword ? <PiLockKeyBold className="text-xl flex-shrink-0" style={{ color: 'var(--accent)' }} /> : <PiLockOpenBold className="text-xl flex-shrink-0" style={{ color: 'var(--text-tertiary)' }} />}
                    <div className="min-w-0">
                        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                            {hasPassword === null ? 'Checking…' : hasPassword ? 'API password is set' : 'No API password set'}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                            {hasPassword ? 'You can get JWT tokens via email + password.' : 'Set a password to enable email + password JWT auth.'}
                        </p>
                    </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                    <button onClick={() => setShowModal(true)} className="si-button-primary text-xs" style={{ height: 32, padding: '0 12px' }}>
                        {hasPassword ? 'Reset Password' : 'Set Password'}
                    </button>
                    {hasPassword && (
                        <button onClick={handleRemove} disabled={removing} className="si-button-secondary text-xs" style={{ height: 32, padding: '0 12px', color: 'var(--danger)' }}>
                            {removing ? '…' : 'Remove'}
                        </button>
                    )}
                </div>
            </div>

            <EndpointCard method="POST" path="/auth/password-token" description="Get a JWT using email + API password">
                <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                    Exchange your email and API password for a short-lived JWT. No browser session required — suitable for scripts and automation.
                </p>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/auth/password-token \\
  -H "Content-Type: application/json" \\
  -d '{"email": "you@example.com", "password": "your_api_password"}'`} />
                <CodeBlock language="json" code={`{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}`} />
            </EndpointCard>

            <h3 className="text-sm font-semibold mb-2 mt-6" style={{ color: 'var(--text-primary)' }}>Using the JWT Token</h3>
            <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                Pass the token in the <InlineCode>Authorization</InlineCode> header as a Bearer token. Tokens expire — re-request when needed.
            </p>
            <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/search \\
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \\
  -H "Content-Type: application/json" \\
  -d '{"name": "john"}'`} />

            {!isAdmin && (
                <Note type="info">
                    JWT tokens grant access to <strong>users</strong>, <strong>groups</strong>, and <strong>media</strong> endpoints. Ingestion and job endpoints require an admin API key.
                </Note>
            )}
            {isAdmin && (
                <Note type="tip">
                    For long-running automations, prefer an <strong>API key</strong> — it doesn't expire and is designed for B2B/internal use.
                </Note>
            )}

            {showModal && (
                <SetApiPasswordModal
                    onClose={() => setShowModal(false)}
                    onSuccess={() => { setShowModal(false); setHasPassword(true); }}
                />
            )}
        </section>
    );
}

function UploadSection() {
    return (
        <section id="upload">
            <SectionTitle icon={PiUploadSimpleBold}>File Upload Flow</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Before triggering any data ingestion, you need to upload the source file. The upload API supports chunked uploads for large files. Complete all three steps to get an <InlineCode>upload_id</InlineCode>.
            </p>
            <Steps steps={[
                { title: 'Initialize the upload', desc: 'POST /uploads/init — registers a new upload session and returns an upload_id.' },
                { title: 'Upload the file in chunks', desc: 'POST /uploads/{upload_id}/chunk — send the file in parts using multipart/form-data.' },
                { title: 'Complete the upload', desc: 'POST /uploads/{upload_id}/complete — signals that all chunks have been received.' },
                { title: 'Trigger ingestion', desc: 'Pass the upload_id in your ingestion request body to start the pipeline.' },
            ]} />
            <EndpointCard id="ep-upload-init" method="POST" path="/uploads/init" description="Start a new upload session">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Creates a new upload session. Returns an <InlineCode>upload_id</InlineCode> used in subsequent chunk and complete calls.</p>
                <FieldTable fields={[
                    { name: 'filename', type: 'string', required: true, desc: 'Original filename with extension (e.g. users.sql)' },
                    { name: 'file_size', type: 'integer', required: true, desc: 'Total file size in bytes' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/uploads/init \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "filename": "users_export.sql",
    "file_size": 1048576
  }'`} />
                <CodeBlock language="json" code={`{
  "upload_id": "a3f2c1d0-8b4e-4f5a-9c2d-1e3b7f6a0d9c",
  "status": "initialized"
}`} />
            </EndpointCard>

            <EndpointCard id="ep-upload-chunk" method="POST" path="/uploads/{upload_id}/chunk" description="Upload a file chunk">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Send one chunk at a time as <InlineCode>multipart/form-data</InlineCode>. Repeat for all chunks in order.</p>
                <FieldTable fields={[
                    { name: 'chunk', type: 'file', required: true, desc: 'The binary chunk data' },
                    { name: 'chunk_index', type: 'integer', required: true, desc: 'Zero-based index of this chunk' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/uploads/a3f2c1d0.../chunk \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -F "chunk=@/path/to/users_chunk_0.bin" \\
  -F "chunk_index=0"`} />
            </EndpointCard>

            <EndpointCard id="ep-upload-complete" method="POST" path="/uploads/{upload_id}/complete" description="Finalize the upload">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Signals that all chunks have been uploaded. The server assembles the file and makes it ready for ingestion.</p>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/uploads/a3f2c1d0.../complete \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "upload_id": "a3f2c1d0-8b4e-4f5a-9c2d-1e3b7f6a0d9c",
  "status": "complete",
  "file_path": "/uploads/a3f2c1d0.../users_export.sql"
}`} />
            </EndpointCard>
        </section>
    );
}

function UsersSection() {
    return (
        <section id="ingest-users">
            <SectionTitle icon={PiUsersBold}>User Ingestion</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Ingests a bulk user SQL dump into the platform. The pipeline automatically extracts embedded group data, builds membership mappings, and indexes everything into the search index.
            </p>
            <h3 className="text-sm font-semibold mb-3 mt-2" style={{ color: 'var(--text-primary)' }}>Pipeline Steps</h3>
            <Steps steps={[
                { title: 'Process users', desc: 'Parse the SQL dump and upsert rows into the users staging table.' },
                { title: 'Extract groups', desc: 'Pull out any group references embedded in the user data.' },
                { title: 'Extract memberships', desc: 'Build the user ↔ group membership mapping table.' },
                { title: 'Index users', desc: 'Bulk-index all users into OpenSearch (batches of 5,000).' },
                { title: 'Index groups', desc: 'Bulk-index all groups into OpenSearch (batches of 5,000).' },
                { title: 'Record history', desc: 'Write a timeline ledger entry for change tracking.' },
                { title: 'Cleanup staging', desc: 'Drop temporary staging tables.' },
            ]} />
            <EndpointCard id="ep-ingest-users" method="POST" path="/ingest/users" description="Trigger user ingestion">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Starts the user ingestion pipeline. Supply either an <InlineCode>upload_id</InlineCode> (from the upload flow) or a server-side <InlineCode>file_path</InlineCode>.</p>
                <FieldTable fields={[
                    { name: 'upload_id', type: 'string', required: false, desc: 'UUID from the upload flow — use this for web uploads' },
                    { name: 'file_path', type: 'string', required: false, desc: 'Server-side absolute path — use this for files already on disk' },
                ]} />
                <Note type="warning">Provide either <InlineCode>upload_id</InlineCode> or <InlineCode>file_path</InlineCode>. At least one is required.</Note>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/users \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"upload_id": "a3f2c1d0-8b4e-4f5a-9c2d-1e3b7f6a0d9c"}'`} />
                <CodeBlock language="json" code={`{
  "message": "User ingestion pipeline started",
  "task_id": "celery-task-uuid-here",
  "job_id": 42
}`} />
            </EndpointCard>
            <Note type="tip">After triggering, poll <InlineCode>GET /jobs/42</InlineCode> to track each pipeline step and its progress percentage.</Note>
        </section>
    );
}

function GroupsSection() {
    return (
        <section id="ingest-groups">
            <SectionTitle icon={PiSquaresFourDuotone}>Group Ingestion</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Ingests a bulk group SQL dump. Use this when you have standalone group data separate from user exports.
            </p>
            <h3 className="text-sm font-semibold mb-3 mt-2" style={{ color: 'var(--text-primary)' }}>Pipeline Steps</h3>
            <Steps steps={[
                { title: 'Process groups', desc: 'Parse the SQL dump and upsert rows into the groups staging table.' },
                { title: 'Index groups', desc: 'Bulk-index all groups into OpenSearch (batches of 5,000).' },
                { title: 'Record history', desc: 'Write a timeline ledger entry for change tracking.' },
                { title: 'Cleanup staging', desc: 'Drop temporary staging tables.' },
            ]} />
            <EndpointCard id="ep-ingest-groups" method="POST" path="/ingest/groups" description="Trigger group ingestion">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Starts the group ingestion pipeline. Same request format as user ingestion.</p>
                <FieldTable fields={[
                    { name: 'upload_id', type: 'string', required: false, desc: 'UUID from the upload flow' },
                    { name: 'file_path', type: 'string', required: false, desc: 'Server-side absolute path to the SQL dump' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/groups \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"upload_id": "a3f2c1d0-8b4e-4f5a-9c2d-1e3b7f6a0d9c"}'`} />
                <CodeBlock language="json" code={`{
  "message": "Group ingestion pipeline started",
  "task_id": "celery-task-uuid-here",
  "job_id": 43
}`} />
            </EndpointCard>
        </section>
    );
}

function AvatarsSection() {
    return (
        <section id="ingest-avatars">
            <SectionTitle icon={PiImageBold}>Avatar Ingestion</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Ingests an avatar manifest JSON file. The pipeline uses Apache Spark to process large manifests, resolves the latest avatar per user, and stores S3 metadata.
            </p>
            <Note type="info">
                The avatar manifest is a JSON file where each entry maps a <InlineCode>service_id</InlineCode> to S3 metadata (key, URL, file size, timestamp). The pipeline deduplicates by <InlineCode>service_id</InlineCode>, keeping the most recent timestamp.
            </Note>
            <h3 className="text-sm font-semibold mb-3 mt-6" style={{ color: 'var(--text-primary)' }}>Pipeline Steps</h3>
            <Steps steps={[
                { title: 'Process avatars via Spark', desc: 'Parse the JSON manifest, deduplicate by service_id + latest timestamp.' },
                { title: 'Index users', desc: 'Re-index affected users in OpenSearch to reflect updated has_avatar flags.' },
                { title: 'Record history', desc: 'Write a timeline ledger entry for change tracking.' },
                { title: 'Cleanup staging', desc: 'Drop temporary staging tables.' },
            ]} />
            <EndpointCard id="ep-ingest-avatars" method="POST" path="/ingest/avatars" description="Trigger avatar ingestion">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Starts the avatar ingestion pipeline. Expects a JSON manifest file from the upload flow.</p>
                <FieldTable fields={[
                    { name: 'upload_id', type: 'string', required: false, desc: 'UUID from the upload flow — manifest JSON file' },
                    { name: 'file_path', type: 'string', required: false, desc: 'Server-side absolute path to the JSON manifest' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/avatars \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"upload_id": "b5e3d2f1-9c5f-5a6b-0d3e-2f4c8g7b1e0d"}'`} />
                <CodeBlock language="json" code={`{
  "message": "Avatar ingestion pipeline started",
  "task_id": "celery-task-uuid-here",
  "job_id": 44
}`} />
            </EndpointCard>
        </section>
    );
}

function LinksSection() {
    return (
        <section id="links">
            <SectionTitle icon={PiLinkBold}>Link Reconstruction</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Reconstructs Signal group invite links for all groups in the database. This endpoint does not require a file upload — it operates on data already present in the database.
            </p>
            <h3 className="text-sm font-semibold mb-3 mt-2" style={{ color: 'var(--text-primary)' }}>How it works</h3>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Each group stores a <InlineCode>master_key</InlineCode> and <InlineCode>invite_link_password</InlineCode>. The link reconstruction job derives the invite URL from these two fields in batches of 100 groups at a time.
            </p>
            <h3 className="text-sm font-semibold mb-3 mt-4" style={{ color: 'var(--text-primary)' }}>Configuration Required</h3>
            <div className="rounded-xl overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
                <table className="w-full text-sm min-w-[420px]">
                    <thead>
                        <tr style={{ background: 'var(--bg-hover)' }}>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Field (in DB)</th>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Required</th>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[
                            { field: 'groups.master_key', req: true, desc: 'Raw master key bytes for the group' },
                            { field: 'groups.invite_link_password', req: true, desc: 'Invite link password bytes — combined with master_key to derive the invite URL' },
                        ].map((r, i) => (
                            <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                                <td className="px-4 py-2.5"><InlineCode>{r.field}</InlineCode></td>
                                <td className="px-4 py-2.5">
                                    <span className="text-xs font-medium px-2 py-0.5 rounded"
                                        style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}>
                                        required
                                    </span>
                                </td>
                                <td className="px-4 py-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>{r.desc}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <EndpointCard id="ep-links-reconstruct" method="POST" path="/ingest/reconstruct-links" description="Trigger link reconstruction">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No request body needed. Processes all groups in batches of 100.</p>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/reconstruct-links \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "status": "success",
  "job_id": 45,
  "task_id": "celery-task-uuid-here"
}`} />
            </EndpointCard>
        </section>
    );
}

function AvatarSyncSection() {
    return (
        <section id="avatar-sync">
            <SectionTitle icon={PiArrowsClockwiseBold}>Avatar Sync</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Revalidates known avatars against S3 storage. For each avatar, it performs an S3 HEAD request to verify the file still exists and check if its content has changed (via ETag comparison). No file upload needed.
            </p>
            <h3 className="text-sm font-semibold mb-3 mt-2" style={{ color: 'var(--text-primary)' }}>Configuration Required</h3>
            <div className="rounded-xl overflow-x-auto" style={{ border: '1px solid var(--border)' }}>
                <table className="w-full text-sm min-w-[420px]">
                    <thead>
                        <tr style={{ background: 'var(--bg-hover)' }}>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Config</th>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Required</th>
                            <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {[
                            { field: 'AWS_ACCESS_KEY_ID', req: true, desc: 'AWS credentials for S3 access' },
                            { field: 'AWS_SECRET_ACCESS_KEY', req: true, desc: 'AWS secret key' },
                            { field: 'S3_BUCKET_NAME', req: true, desc: 'Bucket where avatars are stored' },
                            { field: 'S3_REGION', req: false, desc: 'AWS region (default: us-east-1)' },
                        ].map((r, i) => (
                            <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                                <td className="px-4 py-2.5"><InlineCode>{r.field}</InlineCode></td>
                                <td className="px-4 py-2.5">
                                    <span className="text-xs font-medium px-2 py-0.5 rounded"
                                        style={r.req
                                            ? { background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }
                                            : { background: 'var(--bg-hover)', color: 'var(--text-tertiary)' }}>
                                        {r.req ? 'required' : 'optional'}
                                    </span>
                                </td>
                                <td className="px-4 py-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>{r.desc}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <Note type="warning">
                Only one avatar sync job can run at a time. If you trigger a second sync while one is running, the API returns <InlineCode>409 Conflict</InlineCode>.
            </Note>
            <EndpointCard id="ep-sync-start" method="POST" path="/ingest/avatar-sync" description="Start an avatar sync job">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No request body needed. Processes avatars in self-re-queuing batches using the <InlineCode>avatars</InlineCode> Celery queue.</p>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/avatar-sync \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "status": "success",
  "job_id": 46,
  "task_id": "celery-task-uuid-here"
}`} />
            </EndpointCard>
            <EndpointCard id="ep-sync-stop" method="POST" path="/ingest/avatar-sync/{job_id}/stop" description="Stop a running sync">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Marks the job as stopped and revokes its Celery task. The job will not process any more batches.</p>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/ingest/avatar-sync/46/stop \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "status": "stopped",
  "job_id": 46
}`} />
            </EndpointCard>
            <EndpointCard id="ep-sync-failures" method="GET" path="/ingest/avatar-sync/{job_id}/failures" description="Get sync failures">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Returns per-user failure details from the sync audit log. Useful for diagnosing missing or changed avatars.</p>
                <FieldTable fields={[
                    { name: 'action', type: 'string', required: false, desc: 'Filter by action: error | missing | all (default: all)' },
                    { name: 'limit', type: 'integer', required: false, desc: 'Number of results (1–1000, default: 100)' },
                    { name: 'offset', type: 'integer', required: false, desc: 'Pagination offset (default: 0)' },
                ]} />
                <CodeBlock language="bash" code={`curl "https://your-domain.com/app/api/v1/ingest/avatar-sync/46/failures?action=missing&limit=50" \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "job_id": 46,
  "total_errors": 3,
  "total_missing": 12,
  "results": [
    {
      "service_id": "abc123",
      "action": "missing",
      "detail": "S3 HEAD returned 404",
      "timestamp": "2026-04-19T10:23:00Z"
    }
  ]
}`} />
            </EndpointCard>
        </section>
    );
}

function JobsSection() {
    return (
        <section id="jobs">
            <SectionTitle icon={PiClockBold}>Job Status &amp; Logs</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Every ingestion trigger returns a <InlineCode>job_id</InlineCode>. Use these endpoints to poll progress and stream logs for any job.
            </p>
            <h3 className="text-sm font-semibold mb-2 mt-2" style={{ color: 'var(--text-primary)' }}>Job Status Values</h3>
            <div className="flex flex-wrap gap-2 mb-6">
                {[
                    { label: 'pending', color: 'var(--text-tertiary)', bg: 'var(--bg-hover)' },
                    { label: 'running', color: 'var(--accent)', bg: 'var(--bg-accent-muted)' },
                    { label: 'completed', color: 'var(--success)', bg: 'var(--success-bg)' },
                    { label: 'failed', color: 'var(--danger)', bg: 'var(--danger-bg)' },
                ].map(s => (
                    <span key={s.label} className="px-3 py-1 rounded-full text-xs font-semibold font-mono"
                        style={{ background: s.bg, color: s.color, border: `1px solid color-mix(in srgb, ${s.color} 25%, transparent)` }}>
                        {s.label}
                    </span>
                ))}
            </div>
            <EndpointCard id="ep-jobs-status" method="GET" path="/jobs/{job_id}" description="Poll job progress">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Returns the current job status, each pipeline step's progress, and any error message. Poll every 1–2 seconds while the job is running.</p>
                <CodeBlock language="bash" code={`curl https://your-domain.com/app/api/v1/jobs/42 \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "id": 42,
  "status": "running",
  "ingestion_type": "users",
  "created_at": "2026-04-19T10:00:00Z",
  "started_at": "2026-04-19T10:00:02Z",
  "completed_at": null,
  "error_message": null,
  "steps": [
    {
      "step_name": "process_users_step",
      "status": "completed",
      "progress_percentage": 100.0,
      "current_action": null
    },
    {
      "step_name": "index_users_step",
      "status": "running",
      "progress_percentage": 42.5,
      "current_action": "Indexing batch 3 of 7"
    }
  ]
}`} />
            </EndpointCard>
            <EndpointCard id="ep-jobs-logs" method="GET" path="/jobs/{job_id}/logs" description="Fetch job logs">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Returns timestamped log entries for the job. Includes INFO, WARN, and ERROR levels.</p>
                <CodeBlock language="bash" code={`curl https://your-domain.com/app/api/v1/jobs/42/logs \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "job_id": 42,
  "logs": [
    {
      "timestamp": "2026-04-19T10:00:03Z",
      "log_level": "INFO",
      "step_name": "process_users_step",
      "message": "Starting SQL dump parsing..."
    },
    {
      "timestamp": "2026-04-19T10:00:15Z",
      "log_level": "INFO",
      "step_name": "process_users_step",
      "message": "Upserted 125,000 users into staging"
    }
  ]
}`} />
            </EndpointCard>
        </section>
    );
}

// ── query sections ─────────────────────────────────────────────────────────

function UserSearchSection() {
    return (
        <section id="user-search">
            <SectionTitle icon={PiMagnifyingGlassBold}>User Search</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Search, retrieve, and export user records. All endpoints require a valid API key or session token.
            </p>

            <EndpointCard id="ep-users-search" method="POST" path="/users/search" description="Search users">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Full-text and filtered search across all indexed users. Returns a paginated list.
                </p>
                <FieldTable fields={[
                    { name: 'limit', type: 'integer', required: false, desc: 'Results per page (default: 25, max: 100)' },
                    { name: 'offset', type: 'integer', required: false, desc: 'Pagination offset (default: 0)' },
                    { name: 'name', type: 'string', required: false, desc: 'Full-text search on display name and profile name' },
                    { name: 'about', type: 'string', required: false, desc: 'Full-text search on the about/bio field' },
                    { name: 'e164', type: 'string', required: false, desc: 'Phone number in E.164 format (e.g. +12025550100)' },
                    { name: 'service_id', type: 'string', required: false, desc: 'Exact match on Signal service ID (UUID)' },
                    { name: 'group_id', type: 'integer', required: false, desc: 'Filter users who are members of this group (internal DB id)' },
                    { name: 'group_name', type: 'string', required: false, desc: 'Filter users who are members of a group matching this name' },
                    { name: 'min_group_count', type: 'integer', required: false, desc: 'Minimum number of groups the user belongs to' },
                    { name: 'max_group_count', type: 'integer', required: false, desc: 'Maximum number of groups the user belongs to' },
                    { name: 'is_admin', type: 'boolean', required: false, desc: 'Filter users who are admins in at least one group' },
                    { name: 'has_phone', type: 'boolean', required: false, desc: 'Filter users who have a phone number on record' },
                    { name: 'has_avatar', type: 'boolean', required: false, desc: 'Filter users who have a profile avatar' },
                    { name: 'sort_by', type: 'string', required: false, desc: 'Sort field: relevance | name | group_count | first_observed | last_observed' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/search \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "john",
    "has_avatar": true,
    "min_group_count": 2,
    "limit": 25,
    "offset": 0,
    "sort_by": "last_observed"
  }'`} />
                <CodeBlock language="json" code={`{
  "data": [
    {
      "service_id": "abc123-uuid",
      "user_id": "xyz789",
      "name": "John",
      "profile_full_name": "John Smith",
      "about": "Hey there",
      "e164": "+12025550100",
      "has_avatar": true,
      "avatar_media_id": "media_id_here",
      "group_count": 5,
      "admin_group_count": 1,
      "is_admin": true,
      "first_observed": "2024-01-15T10:00:00Z",
      "last_observed": "2026-04-10T08:23:00Z"
    }
  ],
  "total": 142,
  "limit": 25,
  "offset": 0
}`} />
            </EndpointCard>

            <EndpointCard id="ep-users-details" method="POST" path="/users/details" description="Get single user detail">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Fetch full details for a single user including observed dates, all group memberships, and profile metadata.
                </p>
                <FieldTable fields={[
                    { name: 'serviceId', type: 'string', required: true, desc: 'Signal service ID (UUID) of the user' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/details \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"serviceId": "abc123-uuid"}'`} />
                <CodeBlock language="json" code={`{
  "service_id": "abc123-uuid",
  "user_id": "xyz789",
  "name": "John",
  "profile_full_name": "John Smith",
  "about": "Hey there",
  "e164": "+12025550100",
  "has_avatar": true,
  "avatar_media_id": "media_id_here",
  "group_count": 5,
  "admin_group_count": 1,
  "first_observed": "2024-01-15T10:00:00Z",
  "last_observed": "2026-04-10T08:23:00Z",
  "memberships": [
    {
      "group_id": 12,
      "group_name": "Signal Group A",
      "role": "admin",
      "joined_at": "2024-02-01T00:00:00Z"
    }
  ]
}`} />
            </EndpointCard>

            <EndpointCard id="ep-users-timeline" method="POST" path="/users/timeline" description="User observation timeline">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns chronological events tracking when a user was observed, what changed (profile, memberships, avatar), and which ingestion job recorded it.
                </p>
                <FieldTable fields={[
                    { name: 'serviceId', type: 'string', required: true, desc: 'Signal service ID of the user' },
                    { name: 'limit', type: 'integer', required: false, desc: 'Events per page (default: 10)' },
                    { name: 'offset', type: 'integer', required: false, desc: 'Pagination offset (default: 0)' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/timeline \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"serviceId": "abc123-uuid", "limit": 10, "offset": 0}'`} />
                <CodeBlock language="json" code={`[
  {
    "export_timestamp": "2026-04-10T08:23:00Z",
    "job_id": 42,
    "has_profile_change": true,
    "has_membership_change": false,
    "has_avatar_change": false
  }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-users-history-profile" method="POST" path="/users/history/profile" description="Profile change history">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns a history of profile field changes for a user — name, about, phone number, etc. — across all ingestions.
                </p>
                <FieldTable fields={[
                    { name: 'serviceId', type: 'string', required: true, desc: 'Signal service ID of the user' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/history/profile \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"serviceId": "abc123-uuid"}'`} />
                <CodeBlock language="json" code={`[
  {
    "job_id": 42,
    "observed_at": "2026-04-10T08:23:00Z",
    "name": "John",
    "profile_full_name": "John Smith",
    "about": "Hey there",
    "e164": "+12025550100"
  }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-users-history-memberships" method="POST" path="/users/history/memberships" description="Membership change history">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns the full Type-2 SCD membership history for a user — every group join, role change, and departure with timestamps.
                </p>
                <FieldTable fields={[
                    { name: 'serviceId', type: 'string', required: true, desc: 'Signal service ID of the user' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/history/memberships \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"serviceId": "abc123-uuid"}'`} />
                <CodeBlock language="json" code={`[
  {
    "group_id": 12,
    "group_name": "Signal Group A",
    "role": "admin",
    "is_active": true,
    "valid_from": "2024-02-01T00:00:00Z",
    "valid_to": null
  },
  {
    "group_id": 7,
    "group_name": "Old Group",
    "role": "member",
    "is_active": false,
    "valid_from": "2023-06-01T00:00:00Z",
    "valid_to": "2024-01-10T00:00:00Z"
  }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-users-export" method="POST" path="/users/export" description="Export users to CSV">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Exports users matching the given filters as a CSV file download. Accepts the same filter fields as <InlineCode>/users/search</InlineCode>.
                </p>
                <Note type="info">Response is a <InlineCode>text/csv</InlineCode> file attachment, not JSON.</Note>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/users/export \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"has_avatar": true, "min_group_count": 2}' \\
  --output users_export.csv`} />
            </EndpointCard>
        </section>
    );
}

function GroupSearchSection() {
    return (
        <section id="group-search">
            <SectionTitle icon={PiSquaresFourDuotone}>Group Search</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Search, retrieve, and export group records. Includes membership snapshots at historical points in time.
            </p>

            <EndpointCard id="ep-groups-retention" method="GET" path="/groups/retention-periods" description="List available retention periods">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns the distinct retention period values present in the groups index. Used to populate filter dropdowns.
                </p>
                <CodeBlock language="bash" code={`curl https://your-domain.com/app/api/v1/groups/retention-periods \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`["UNKNOWN", "MESSAGES_DISAPPEAR_AFTER_1_DAY", "MESSAGES_DISAPPEAR_AFTER_1_WEEK", "MESSAGES_DISAPPEAR_AFTER_1_MONTH"]`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-search" method="POST" path="/groups/search" description="Search groups">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Full-text and filtered search across all indexed groups. Returns a paginated list.
                </p>
                <FieldTable fields={[
                    { name: 'limit', type: 'integer', required: false, desc: 'Results per page (default: 25, max: 100)' },
                    { name: 'offset', type: 'integer', required: false, desc: 'Pagination offset (default: 0)' },
                    { name: 'group_name', type: 'string', required: false, desc: 'Full-text search on group name' },
                    { name: 'description', type: 'string', required: false, desc: 'Full-text search on group description' },
                    { name: 'group_id', type: 'string', required: false, desc: 'Exact match on Signal group ID (master_id)' },
                    { name: 'min_members', type: 'integer', required: false, desc: 'Minimum member count' },
                    { name: 'max_members', type: 'integer', required: false, desc: 'Maximum member count' },
                    { name: 'has_link', type: 'boolean', required: false, desc: 'Filter groups that have a reconstructed invite link' },
                    { name: 'retention_period', type: 'string', required: false, desc: 'Filter by message retention period value' },
                    { name: 'admin_approval_required', type: 'boolean', required: false, desc: 'Filter groups requiring admin approval to join' },
                    { name: 'sort_by', type: 'string', required: false, desc: 'Sort field: relevance | name | member_count | first_observed | last_observed' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/search \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "group_name": "news",
    "has_link": true,
    "min_members": 10,
    "limit": 25,
    "offset": 0,
    "sort_by": "member_count"
  }'`} />
                <CodeBlock language="json" code={`{
  "data": [
    {
      "id": 12,
      "master_id": "group-uuid",
      "name": "Breaking News",
      "description": "Latest updates",
      "member_count": 342,
      "invite_link": "https://signal.group/#...",
      "has_link": true,
      "admin_approval_required": false,
      "retention_period": "MESSAGES_DISAPPEAR_AFTER_1_WEEK",
      "first_observed": "2024-01-10T00:00:00Z",
      "last_observed": "2026-04-18T12:00:00Z"
    }
  ],
  "total": 8,
  "limit": 25,
  "offset": 0
}`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-details" method="POST" path="/groups/details" description="Get single group detail">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Fetch full details for a single group including current member list, invite link, and all metadata.
                </p>
                <FieldTable fields={[
                    { name: 'groupId', type: 'string', required: true, desc: 'Signal group master_id (UUID)' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/details \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"groupId": "group-uuid"}'`} />
                <CodeBlock language="json" code={`{
  "id": 12,
  "master_id": "group-uuid",
  "name": "Breaking News",
  "description": "Latest updates",
  "member_count": 342,
  "invite_link": "https://signal.group/#...",
  "has_link": true,
  "admin_approval_required": false,
  "retention_period": "MESSAGES_DISAPPEAR_AFTER_1_WEEK",
  "first_observed": "2024-01-10T00:00:00Z",
  "last_observed": "2026-04-18T12:00:00Z",
  "members": [
    { "service_id": "abc123", "name": "John", "role": "admin" }
  ]
}`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-timeline" method="POST" path="/groups/timeline" description="Group observation timeline">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns chronological events tracking when a group was observed across ingestion jobs.
                </p>
                <FieldTable fields={[
                    { name: 'groupId', type: 'string', required: true, desc: 'Signal group master_id' },
                    { name: 'limit', type: 'integer', required: false, desc: 'Events per page (default: 10)' },
                    { name: 'offset', type: 'integer', required: false, desc: 'Pagination offset (default: 0)' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/timeline \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"groupId": "group-uuid", "limit": 10, "offset": 0}'`} />
                <CodeBlock language="json" code={`[
  {
    "export_timestamp": "2026-04-18T12:00:00Z",
    "job_id": 43,
    "member_count": 342
  }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-history" method="POST" path="/groups/history" description="Group metadata history">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns the history of group name, description, and setting changes across all ingestions.
                </p>
                <FieldTable fields={[
                    { name: 'groupId', type: 'string', required: true, desc: 'Signal group master_id' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/history \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"groupId": "group-uuid"}'`} />
                <CodeBlock language="json" code={`[
  {
    "job_id": 43,
    "observed_at": "2026-04-18T12:00:00Z",
    "name": "Breaking News",
    "description": "Latest updates",
    "member_count": 342
  }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-history-members" method="POST" path="/groups/history-members" description="Members snapshot at a point in time">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns the member list for a group as it was at a specific historical timestamp. Pass a timestamp from the timeline or history response.
                </p>
                <FieldTable fields={[
                    { name: 'groupId', type: 'string', required: true, desc: 'Signal group master_id' },
                    { name: 'timestamp', type: 'number', required: true, desc: 'Unix timestamp (ms) of the point in time' },
                ]} />
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/history-members \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"groupId": "group-uuid", "timestamp": 1713441600000}'`} />
                <CodeBlock language="json" code={`[
  { "service_id": "abc123", "name": "John", "role": "admin" },
  { "service_id": "def456", "name": "Alice", "role": "member" }
]`} />
            </EndpointCard>

            <EndpointCard id="ep-groups-export" method="POST" path="/groups/export" description="Export groups to CSV">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Exports groups matching the given filters as a CSV file download. Accepts the same filter fields as <InlineCode>/groups/search</InlineCode>.
                </p>
                <Note type="info">Response is a <InlineCode>text/csv</InlineCode> file attachment, not JSON.</Note>
                <CodeBlock language="bash" code={`curl -X POST https://your-domain.com/app/api/v1/groups/export \\
  -H "X-API-Key: usk_abcd1234.secret" \\
  -H "Content-Type: application/json" \\
  -d '{"has_link": true, "min_members": 50}' \\
  --output groups_export.csv`} />
            </EndpointCard>
        </section>
    );
}

function MediaSection() {
    return (
        <section id="media">
            <SectionTitle icon={PiDownloadSimpleBold}>Media &amp; Avatars</SectionTitle>
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text-secondary)' }}>
                Retrieve avatar images for users. The media endpoint returns a short-lived CDN URL that proxies the image from S3.
            </p>
            <Note type="info">
                Avatar media IDs (<InlineCode>avatar_media_id</InlineCode>) are returned on user records from <InlineCode>/users/search</InlineCode> and <InlineCode>/users/details</InlineCode>. Pass them here to get the actual image URL.
            </Note>
            <EndpointCard id="ep-media-download" method="GET" path="/media/{mediaId}/download" description="Get avatar download URL">
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Returns a short-lived signed URL for the avatar image. Fetch the URL immediately — it expires within minutes.
                </p>
                <FieldTable fields={[
                    { name: 'mediaId', type: 'string (path)', required: true, desc: 'The avatar_media_id from a user record' },
                ]} />
                <CodeBlock language="bash" code={`curl https://your-domain.com/app/api/v1/media/media_id_here/download \\
  -H "X-API-Key: usk_abcd1234.secret"`} />
                <CodeBlock language="json" code={`{
  "url": "https://s3.amazonaws.com/your-bucket/avatars/abc123.jpg?X-Amz-Signature=..."
}`} />
            </EndpointCard>
            <Steps steps={[
                { title: 'Search or look up a user', desc: 'POST /users/search or /users/details — the response includes avatar_media_id if the user has an avatar.' },
                { title: 'Request the download URL', desc: 'GET /media/{avatar_media_id}/download — returns a signed S3 URL.' },
                { title: 'Fetch the image', desc: 'Make a GET request to the returned URL to download or display the avatar.' },
            ]} />
        </section>
    );
}

// ── main page ──────────────────────────────────────────────────────────────

// ── search index ───────────────────────────────────────────────────────────
// Flat list of every searchable item (sections + endpoints)
// Built from nav config + hand-written descriptions so Fuse can rank well.

const SEARCH_ITEMS = [
    // ── Search & Query ──
    { id: 'overview', section: 'Overview', label: 'Overview', desc: 'Base URL, auth methods, response format', tags: 'overview intro base url' },
    { id: 'auth', section: 'Authentication', label: 'Authentication', desc: 'API key header, Bearer JWT token auth', tags: 'auth login api key bearer jwt' },
    // user search
    { id: 'ep-users-search', section: 'User Search', label: 'POST /users/search', method: 'POST', path: '/users/search', desc: 'Full-text and filtered search across all users. Filter by name, phone, group, avatar, admin status.' },
    { id: 'ep-users-details', section: 'User Search', label: 'POST /users/details', method: 'POST', path: '/users/details', desc: 'Fetch full profile for a single user including all group memberships and observed dates.' },
    { id: 'ep-users-timeline', section: 'User Search', label: 'POST /users/timeline', method: 'POST', path: '/users/timeline', desc: 'Chronological observation events for a user — profile changes, membership changes, avatar changes.' },
    { id: 'ep-users-history-profile', section: 'User Search', label: 'POST /users/history/profile', method: 'POST', path: '/users/history/profile', desc: 'History of profile field changes: name, about, phone number across ingestions.' },
    { id: 'ep-users-history-memberships', section: 'User Search', label: 'POST /users/history/memberships', method: 'POST', path: '/users/history/memberships', desc: 'Type-2 SCD membership history — every group join, role change, and departure with timestamps.' },
    { id: 'ep-users-export', section: 'User Search', label: 'POST /users/export', method: 'POST', path: '/users/export', desc: 'Export users matching filters as a CSV file download.' },
    // group search
    { id: 'ep-groups-retention', section: 'Group Search', label: 'GET /groups/retention-periods', method: 'GET', path: '/groups/retention-periods', desc: 'List distinct message retention period values for filter dropdowns.' },
    { id: 'ep-groups-search', section: 'Group Search', label: 'POST /groups/search', method: 'POST', path: '/groups/search', desc: 'Full-text and filtered search across all groups. Filter by name, member count, invite link, retention.' },
    { id: 'ep-groups-details', section: 'Group Search', label: 'POST /groups/details', method: 'POST', path: '/groups/details', desc: 'Fetch full details for a single group including current member list and invite link.' },
    { id: 'ep-groups-timeline', section: 'Group Search', label: 'POST /groups/timeline', method: 'POST', path: '/groups/timeline', desc: 'Chronological observation events tracking when a group was seen across ingestion jobs.' },
    { id: 'ep-groups-history', section: 'Group Search', label: 'POST /groups/history', method: 'POST', path: '/groups/history', desc: 'History of group name, description, and settings changes across ingestions.' },
    { id: 'ep-groups-history-members', section: 'Group Search', label: 'POST /groups/history-members', method: 'POST', path: '/groups/history-members', desc: 'Snapshot of group members at a specific historical timestamp.' },
    { id: 'ep-groups-export', section: 'Group Search', label: 'POST /groups/export', method: 'POST', path: '/groups/export', desc: 'Export groups matching filters as a CSV file download.' },
    // media
    { id: 'ep-media-download', section: 'Media & Avatars', label: 'GET /media/{mediaId}/download', method: 'GET', path: '/media/{mediaId}/download', desc: 'Get a short-lived signed S3 URL for a user avatar image.' },
    // ── Ingestion (admin) ──
    { id: 'ep-upload-init', section: 'File Upload', label: 'POST /uploads/init', method: 'POST', path: '/uploads/init', desc: 'Initialize a chunked upload session, returns upload_id.' },
    { id: 'ep-upload-chunk', section: 'File Upload', label: 'POST /uploads/{id}/chunk', method: 'POST', path: '/uploads/{id}/chunk', desc: 'Upload one chunk of a file using multipart/form-data.' },
    { id: 'ep-upload-complete', section: 'File Upload', label: 'POST /uploads/{id}/complete', method: 'POST', path: '/uploads/{id}/complete', desc: 'Finalize upload — server assembles chunks and makes file ready for ingestion.' },
    { id: 'ep-ingest-users', section: 'Ingest Users', label: 'POST /ingest/users', method: 'POST', path: '/ingest/users', desc: 'Trigger bulk user ingestion pipeline from SQL dump. Extracts groups, memberships, and indexes to OpenSearch.' },
    { id: 'ep-ingest-groups', section: 'Ingest Groups', label: 'POST /ingest/groups', method: 'POST', path: '/ingest/groups', desc: 'Trigger bulk group ingestion pipeline from SQL dump.' },
    { id: 'ep-ingest-avatars', section: 'Ingest Avatars', label: 'POST /ingest/avatars', method: 'POST', path: '/ingest/avatars', desc: 'Trigger avatar ingestion from a JSON manifest file using Apache Spark.' },
    { id: 'ep-links-reconstruct', section: 'Link Reconstruction', label: 'POST /ingest/reconstruct-links', method: 'POST', path: '/ingest/reconstruct-links', desc: 'Reconstruct Signal group invite links from master_key and invite_link_password in batches.' },
    { id: 'ep-sync-start', section: 'Avatar Sync', label: 'POST /ingest/avatar-sync', method: 'POST', path: '/ingest/avatar-sync', desc: 'Start an avatar sync job — revalidates all known avatars against S3 via ETag comparison.' },
    { id: 'ep-sync-stop', section: 'Avatar Sync', label: 'POST /ingest/avatar-sync/{id}/stop', method: 'POST', path: '/ingest/avatar-sync/{id}/stop', desc: 'Stop a running avatar sync job. Marks job as failed and revokes Celery task.' },
    { id: 'ep-sync-failures', section: 'Avatar Sync', label: 'GET /ingest/avatar-sync/{id}/failures', method: 'GET', path: '/ingest/avatar-sync/{id}/failures', desc: 'Get per-user failure details from avatar sync audit log — missing or changed avatars.' },
    { id: 'ep-jobs-status', section: 'Jobs', label: 'GET /jobs/{job_id}', method: 'GET', path: '/jobs/{job_id}', desc: 'Poll job status and step-by-step progress. Returns running, completed, or failed.' },
    { id: 'ep-jobs-logs', section: 'Jobs', label: 'GET /jobs/{job_id}/logs', method: 'GET', path: '/jobs/{job_id}/logs', desc: 'Fetch timestamped log entries for a job. INFO, WARN, ERROR levels.' },
];

const INGESTION_IDS = new Set([
    'auth',
    'ep-upload-init','ep-upload-chunk','ep-upload-complete',
    'ep-ingest-users','ep-ingest-groups','ep-ingest-avatars',
    'ep-links-reconstruct','ep-sync-start','ep-sync-stop','ep-sync-failures',
    'ep-jobs-status','ep-jobs-logs',
]);

const fuse = new Fuse(SEARCH_ITEMS, {
    keys: [
        { name: 'path', weight: 3 },
        { name: 'label', weight: 2.5 },
        { name: 'section', weight: 1.5 },
        { name: 'desc', weight: 1 },
        { name: 'method', weight: 1 },
        { name: 'tags', weight: 0.5 },
    ],
    threshold: 0.35,
    includeScore: true,
    ignoreLocation: true,
    minMatchCharLength: 2,
});

// ── doc search overlay ─────────────────────────────────────────────────────

function DocSearch({ onNavigate, isAdmin, compact = false }) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [cursor, setCursor] = useState(0);
    const inputRef = useRef(null);
    const listRef = useRef(null);

    const items = useMemo(() => {
        const pool = isAdmin ? SEARCH_ITEMS : SEARCH_ITEMS.filter(i => !INGESTION_IDS.has(i.id));
        if (!query.trim()) return pool.slice(0, 8);
        const src = isAdmin ? SEARCH_ITEMS : pool;
        return fuse.search(query, { limit: 10 }).map(r => r.item).filter(i => isAdmin || !INGESTION_IDS.has(i.id));
    }, [query, isAdmin]);

    // Keyboard shortcut to open
    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setOpen(v => !v);
            }
            if (e.key === 'Escape') setOpen(false);
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    useEffect(() => {
        if (open) { setTimeout(() => inputRef.current?.focus(), 50); setCursor(0); }
        else setQuery('');
    }, [open]);

    useEffect(() => { setCursor(0); }, [query]);

    const handleKeyDown = (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, items.length - 1)); }
        if (e.key === 'ArrowUp') { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)); }
        if (e.key === 'Enter' && items[cursor]) { pick(items[cursor]); }
    };

    // Scroll cursor into view
    useEffect(() => {
        const el = listRef.current?.children[cursor];
        el?.scrollIntoView({ block: 'nearest' });
    }, [cursor]);

    const pick = useCallback((item) => {
        setOpen(false);
        onNavigate(item.id);
    }, [onNavigate]);

    const isMac = navigator.platform.toUpperCase().includes('MAC');

    if (!open) {
        return (
            <button
                onClick={() => setOpen(true)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${compact ? '' : 'mb-3'}`}
                style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <PiMagnifyingGlassBold className="text-sm flex-shrink-0" />
                <span className="flex-1 text-left text-xs">Search endpoints…</span>
                <span className="flex items-center gap-0.5 text-[10px] font-mono px-1.5 py-0.5 rounded"
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                    {isMac ? '⌘' : 'Ctrl'}K
                </span>
            </button>
        );
    }

    return (
        <div className="fixed inset-0 z-[300] flex items-start justify-center pt-[10vh]"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            onClick={() => setOpen(false)}>
            <div className="w-full max-w-xl mx-4 rounded-2xl overflow-hidden shadow-2xl"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                onClick={e => e.stopPropagation()}>

                {/* Input */}
                <div className="flex items-center gap-3 px-4 py-3.5 border-b" style={{ borderColor: 'var(--border)' }}>
                    <PiMagnifyingGlassBold className="text-lg flex-shrink-0" style={{ color: 'var(--text-tertiary)' }} />
                    <input
                        ref={inputRef}
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Search endpoints, methods, descriptions…"
                        className="flex-1 bg-transparent outline-none text-sm"
                        style={{ color: 'var(--text-primary)', caretColor: 'var(--accent)' }}
                        spellCheck={false}
                    />
                    {query && (
                        <button onClick={() => setQuery('')} style={{ color: 'var(--text-tertiary)', background: 'none', border: 'none', cursor: 'pointer' }}>
                            <PiXBold className="text-sm" />
                        </button>
                    )}
                    <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}>
                        Esc
                    </kbd>
                </div>

                {/* Results */}
                <div ref={listRef} className="max-h-[420px] overflow-y-auto custom-scrollbar py-2">
                    {items.length === 0 && (
                        <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            No results for <strong style={{ color: 'var(--text-secondary)' }}>"{query}"</strong>
                        </div>
                    )}
                    {items.map((item, i) => {
                        const isActive = i === cursor;
                        const mc = METHOD_DOT[item.method] || 'var(--text-tertiary)';
                        return (
                            <button
                                key={item.id}
                                onClick={() => pick(item)}
                                onMouseEnter={() => setCursor(i)}
                                className="w-full flex items-start gap-3 px-4 py-3 text-left transition-all"
                                style={{
                                    background: isActive ? 'var(--bg-accent-muted)' : 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                    borderLeft: isActive ? `2px solid var(--accent)` : '2px solid transparent',
                                }}>
                                <div className="flex-shrink-0 mt-1">
                                    {item.method ? (
                                        <span className="inline-block text-[10px] font-mono font-bold w-10 text-center px-1 py-0.5 rounded"
                                            style={{ background: `color-mix(in srgb, ${mc} 15%, transparent)`, color: mc, border: `1px solid color-mix(in srgb, ${mc} 25%, transparent)` }}>
                                            {item.method}
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center justify-center w-10 h-5 rounded"
                                            style={{ background: 'var(--bg-hover)' }}>
                                            <PiDatabaseDuotone className="text-xs" style={{ color: 'var(--accent)' }} />
                                        </span>
                                    )}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-0.5">
                                        <span className="text-xs font-mono font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                                            {item.path || item.label}
                                        </span>
                                        <span className="text-[10px] flex-shrink-0 px-1.5 py-0.5 rounded"
                                            style={{ background: 'var(--bg-hover)', color: 'var(--text-tertiary)' }}>
                                            {item.section}
                                        </span>
                                    </div>
                                    <p className="text-xs leading-relaxed line-clamp-1" style={{ color: 'var(--text-secondary)' }}>
                                        {item.desc}
                                    </p>
                                </div>
                                {isActive && <PiArrowRightBold className="text-xs flex-shrink-0 mt-1.5" style={{ color: 'var(--accent)' }} />}
                            </button>
                        );
                    })}
                </div>

                {/* Footer */}
                <div className="flex items-center gap-4 px-4 py-2.5 border-t text-[10px]"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-tertiary)' }}>
                    <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded font-mono" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>↑↓</kbd> navigate</span>
                    <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded font-mono" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>↵</kbd> go to</span>
                    <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded font-mono" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>Esc</kbd> close</span>
                </div>
            </div>
        </div>
    );
}

function NavGroupLabel({ label }) {
    return (
        <div className="px-3 pt-5 pb-1">
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
        </div>
    );
}

const METHOD_DOT = {
    GET: 'var(--success)',
    POST: 'var(--accent)',
    DELETE: 'var(--danger)',
    PATCH: 'var(--warning)',
};

function NavAccordion({ section, activeId, scrollTo }) {
    const hasEndpoints = section.endpoints?.length > 0;
    const isSectionActive = activeId === section.id;
    const isChildActive = hasEndpoints && section.endpoints.some(ep => ep.id === activeId);
    const isOpen = isSectionActive || isChildActive;
    const [manualOpen, setManualOpen] = useState(false);
    const expanded = isOpen || manualOpen;

    return (
        <div>
            <button
                onClick={() => { scrollTo(section.id); if (hasEndpoints) setManualOpen(v => !v); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-all"
                style={{
                    background: isSectionActive ? 'var(--bg-accent-muted)' : 'transparent',
                    color: isSectionActive || isChildActive ? 'var(--accent)' : 'var(--text-secondary)',
                    fontWeight: isSectionActive || isChildActive ? 600 : 400,
                    border: 'none',
                    cursor: 'pointer',
                }}>
                <section.icon className="text-base flex-shrink-0" />
                <span className="flex-1 truncate">{section.label}</span>
                {hasEndpoints && (
                    <PiCaretDownBold
                        className="text-xs flex-shrink-0 transition-transform duration-200"
                        style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', opacity: 0.5 }}
                    />
                )}
            </button>

            {hasEndpoints && expanded && (
                <div className="ml-3 pl-3 mb-1 space-y-0.5" style={{ borderLeft: '1px solid var(--border)' }}>
                    {section.endpoints.map(ep => {
                        const isEpActive = activeId === ep.id;
                        return (
                            <button
                                key={ep.id}
                                onClick={() => scrollTo(ep.id)}
                                className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-all"
                                style={{
                                    background: isEpActive ? 'var(--bg-accent-muted)' : 'transparent',
                                    border: 'none',
                                    cursor: 'pointer',
                                }}>
                                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                                    style={{ background: METHOD_DOT[ep.method] || 'var(--text-tertiary)' }} />
                                <span className="text-xs font-mono truncate"
                                    style={{ color: isEpActive ? 'var(--accent)' : 'var(--text-secondary)' }}>
                                    {ep.path}
                                </span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default function IngestionDocsPage() {
    const { user } = useAuth();
    const isAdmin = user?.is_superuser === true;

    const [activeId, setActiveId] = useState('overview');
    const [mobileNavOpen, setMobileNavOpen] = useState(false);
    const contentRef = useRef(null);

    const allNav = [...SEARCH_NAV, ...(isAdmin ? INGESTION_NAV : [])];
    // Flat list of all trackable IDs in document order
    const allIds = allNav.flatMap(s => [s.id, ...(s.endpoints?.map(ep => ep.id) ?? [])]);

    useEffect(() => {
        const el = contentRef.current;
        if (!el) return;
        const handleScroll = () => {
            for (let i = allIds.length - 1; i >= 0; i--) {
                const domEl = document.getElementById(allIds[i]);
                if (domEl && domEl.getBoundingClientRect().top <= 130) {
                    setActiveId(allIds[i]);
                    return;
                }
            }
            setActiveId('overview');
        };
        el.addEventListener('scroll', handleScroll, { passive: true });
        return () => el.removeEventListener('scroll', handleScroll);
    }, [isAdmin]);

    const scrollTo = (id) => {
        const el = document.getElementById(id);
        if (el && contentRef.current) {
            contentRef.current.scrollTo({ top: el.offsetTop - 24, behavior: 'smooth' });
        }
    };

    return (
        <div className="flex h-full overflow-hidden" style={{ background: 'var(--bg-page)' }}>
            {/* Left nav */}
            <aside className="hidden md:flex flex-col flex-shrink-0 w-56 border-r overflow-y-auto custom-scrollbar py-4 px-2"
                style={{ borderColor: 'var(--border)', background: 'var(--bg-sidebar)' }}>
                <div className="flex items-center gap-2.5 px-3 mb-3">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
                        style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)' }}>
                        <PiDatabaseDuotone />
                    </div>
                    <span className="text-sm font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>API Reference</span>
                </div>

                <div className="px-2 mb-1">
                    <DocSearch onNavigate={scrollTo} isAdmin={isAdmin} />
                </div>

                <nav className="space-y-0.5">
                    <NavGroupLabel label="Search & Query" />
                    {SEARCH_NAV.map(s => (
                        <NavAccordion key={s.id} section={s} activeId={activeId} scrollTo={scrollTo} />
                    ))}

                    {isAdmin && (
                        <>
                            <NavGroupLabel label="Ingestion (Admin)" />
                            {INGESTION_NAV.map(s => (
                                <NavAccordion key={s.id} section={s} activeId={activeId} scrollTo={scrollTo} />
                            ))}
                        </>
                    )}
                </nav>
            </aside>

            {/* Mobile nav sheet */}
            {mobileNavOpen && (
                <>
                    <div
                        className="fixed inset-0 z-[150] md:hidden"
                        style={{ background: 'rgba(0,0,0,0.5)' }}
                        onClick={() => setMobileNavOpen(false)}
                    />
                    <div
                        className="fixed inset-y-0 left-0 z-[160] w-72 flex flex-col md:hidden overflow-y-auto custom-scrollbar py-4 px-2"
                        style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--border)' }}
                    >
                        <div className="flex items-center justify-between px-3 mb-4">
                            <div className="flex items-center gap-2">
                                <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm" style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)' }}>
                                    <PiDatabaseDuotone />
                                </div>
                                <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>API Reference</span>
                            </div>
                            <button onClick={() => setMobileNavOpen(false)} className="si-icon-button"><PiXBold /></button>
                        </div>
                        <nav className="space-y-0.5">
                            <NavGroupLabel label="Search & Query" />
                            {SEARCH_NAV.map(s => (
                                <NavAccordion key={s.id} section={s} activeId={activeId} scrollTo={(id) => { scrollTo(id); setMobileNavOpen(false); }} />
                            ))}
                            {isAdmin && (
                                <>
                                    <NavGroupLabel label="Ingestion (Admin)" />
                                    {INGESTION_NAV.map(s => (
                                        <NavAccordion key={s.id} section={s} activeId={activeId} scrollTo={(id) => { scrollTo(id); setMobileNavOpen(false); }} />
                                    ))}
                                </>
                            )}
                        </nav>
                    </div>
                </>
            )}

            {/* Main content */}
            <main ref={contentRef} className="flex-1 overflow-y-auto custom-scrollbar">
                {/* Mobile sticky top bar */}
                <div className="sticky top-0 z-10 flex items-center gap-2 px-4 py-2.5 md:hidden" style={{ background: 'var(--bg-page)', borderBottom: '1px solid var(--border)' }}>
                    <button
                        onClick={() => setMobileNavOpen(true)}
                        className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg flex-shrink-0"
                        style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                    >
                        <PiListBold className="text-sm" />
                        <span>Sections</span>
                    </button>
                    <div className="flex-1 min-w-0">
                        <DocSearch onNavigate={scrollTo} isAdmin={isAdmin} compact />
                    </div>
                </div>

                <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-0">
                    {/* Header */}
                    <div className="flex items-center gap-4 mb-10 pb-8" style={{ borderBottom: '1px solid var(--border)' }}>
                        <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                            style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
                            <PiDatabaseDuotone />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>API Reference</h1>
                            <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>Search, retrieve, export, and ingest Signal user and group data</p>
                        </div>
                    </div>

                    {/* Search & Query section group header */}
                    <div className="flex items-center gap-3 mb-8">
                        <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                        <span className="text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full"
                            style={{ color: 'var(--accent)', background: 'var(--bg-accent-muted)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}>
                            Search &amp; Query
                        </span>
                        <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                    </div>

                    <OverviewSection />
                    <Divider />
                    <AuthSection />
                    <Divider />
                    <UserSearchSection />
                    <Divider />
                    <GroupSearchSection />
                    <Divider />
                    <MediaSection />

                    {/* Ingestion section group header — admin only */}
                    {isAdmin && (
                        <>
                            <div className="flex items-center gap-3 mt-12 mb-8">
                                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                                <span className="text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full"
                                    style={{ color: 'var(--warning)', background: 'var(--warning-bg)', border: '1px solid color-mix(in srgb, var(--warning) 25%, transparent)' }}>
                                    Ingestion — Admin Only
                                </span>
                                <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                            </div>

                            <UploadSection />
                            <Divider />
                            <UsersSection />
                            <Divider />
                            <GroupsSection />
                            <Divider />
                            <AvatarsSection />
                            <Divider />
                            <LinksSection />
                            <Divider />
                            <AvatarSyncSection />
                            <Divider />
                            <JobsSection />
                        </>
                    )}

                    <div className="pb-16" />
                </div>
            </main>
        </div>
    );
}
