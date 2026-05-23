import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import toast from "react-hot-toast";
import { fetchMyApiKeys, revokeApiKey } from "../../../store/slices/apiKeySlice";
import ApiKeyForm from "./ApiKeyForm";
import ApiKeyDetail from "./ApiKeyDetail";
import useIsMobile from "../../../hooks/useIsMobile";
import {
    PiPlusBold,
    PiCopyBold,
    PiTrashBold,
    PiKeyBold,
    PiClockBold,
    PiCheckCircleBold,
    PiXCircleBold,
} from "react-icons/pi";

export default function ApiKeyList() {
    const dispatch = useDispatch();
    const { keys, loading, createdKey } = useSelector((s) => s.apiKeys);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [showCreatedDetail, setShowCreatedDetail] = useState(false);
    const [confirmRevoke, setConfirmRevoke] = useState(null);

    useEffect(() => {
        dispatch(fetchMyApiKeys());
    }, [dispatch]);

    useEffect(() => {
        if (createdKey) {
            setShowCreatedDetail(true);
            setShowCreateForm(false);
            dispatch(fetchMyApiKeys());
        }
    }, [createdKey, dispatch]);

    const handleCopyKeyId = (keyId) => {
        navigator.clipboard.writeText(keyId);
        toast.success("Key ID copied");
    };

    const handleRevoke = async (keyId, keyName) => {
        try {
            await dispatch(revokeApiKey(keyId)).unwrap();
            toast.success(`"${keyName}" revoked`);
            setConfirmRevoke(null);
        } catch (err) {
            toast.error(err || "Failed to revoke key");
        }
    };

    const formatDate = (iso) => {
        if (!iso) return "Never";
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
        });
    };

    const getStatusBadge = (key) => {
        if (!key.is_active) {
            return <span className="si-badge si-badge-danger inline-flex items-center gap-1"><PiXCircleBold /> Revoked</span>;
        }
        if (key.expires_at && new Date(key.expires_at) < new Date()) {
            return <span className="si-badge si-badge-warning inline-flex items-center gap-1"><PiClockBold /> Expired</span>;
        }
        return <span className="si-badge si-badge-success inline-flex items-center gap-1"><PiCheckCircleBold /> Active</span>;
    };

    const isMobile = useIsMobile();

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h3 className="si-section-title text-lg font-bold">API Keys</h3>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>Manage your API access keys</p>
                </div>
                <button
                    onClick={() => setShowCreateForm(true)}
                    className="si-button-primary flex items-center justify-center gap-2 sm:w-auto"
                >
                    <PiPlusBold /> Create New Key
                </button>
            </div>

            {/* Mobile: cards */}
            {isMobile ? (
                loading ? (
                    <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <div key={i} className="animate-pulse rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                <div className="flex justify-between">
                                    <div className="h-4 w-28 rounded" style={{ background: 'var(--bg-hover)' }} />
                                    <div className="h-5 w-16 rounded-full" style={{ background: 'var(--bg-hover)' }} />
                                </div>
                                <div className="h-3 w-40 rounded" style={{ background: 'var(--bg-hover)' }} />
                                <div className="h-3 w-32 rounded" style={{ background: 'var(--bg-hover)' }} />
                            </div>
                        ))}
                    </div>
                ) : keys.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 py-12 rounded-xl" style={{ border: '1px solid var(--border)' }}>
                        <PiKeyBold className="text-3xl" style={{ color: 'var(--text-tertiary)' }} />
                        <p style={{ color: 'var(--text-secondary)' }}>No API keys yet</p>
                        <button onClick={() => setShowCreateForm(true)} className="text-sm" style={{ color: 'var(--accent)' }}>
                            Create your first key
                        </button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {keys.map((key) => (
                            <div key={key.key_id} className="rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                {/* Top: name + status */}
                                <div className="flex items-start justify-between gap-2">
                                    <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{key.name}</span>
                                    {getStatusBadge(key)}
                                </div>

                                {/* Key ID row */}
                                <button
                                    onClick={() => handleCopyKeyId(key.key_id)}
                                    className="flex items-center gap-2 w-full text-left"
                                    title="Tap to copy"
                                >
                                    <span className="font-mono text-xs truncate flex-1" style={{ color: 'var(--text-tertiary)' }}>{key.key_id}</span>
                                    <PiCopyBold className="shrink-0 text-xs" style={{ color: 'var(--text-tertiary)' }} />
                                </button>

                                {/* Details grid */}
                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                    <div><span style={{ color: 'var(--text-tertiary)' }}>Created </span>{formatDate(key.created_at)}</div>
                                    <div><span style={{ color: 'var(--text-tertiary)' }}>Used </span>{formatDate(key.last_used_at)}</div>
                                    <div><span style={{ color: 'var(--text-tertiary)' }}>Expires </span>{key.expires_at ? formatDate(key.expires_at) : "Never"}</div>
                                    <div><span style={{ color: 'var(--text-tertiary)' }}>Requests </span>{key.request_count?.toLocaleString() || 0}</div>
                                </div>

                                {/* Revoke */}
                                {key.is_active && (
                                    <div className="pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                                        <button
                                            onClick={() => setConfirmRevoke(key)}
                                            className="text-xs flex items-center gap-1.5"
                                            style={{ color: 'var(--danger)' }}
                                        >
                                            <PiTrashBold /> Revoke Key
                                        </button>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )
            ) : (
                /* Desktop: table */
                <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                    <div className="overflow-x-auto">
                        <table className="si-data-table">
                            <thead>
                                <tr>
                                    <th className="px-4 text-left">Name</th>
                                    <th className="px-4 text-left">Key ID</th>
                                    <th className="px-4 text-left">Created</th>
                                    <th className="px-4 text-left">Last Used</th>
                                    <th className="px-4 text-left">Expires</th>
                                    <th className="px-4 text-left">Requests</th>
                                    <th className="px-4 text-left">Status</th>
                                    <th className="px-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    Array.from({ length: 4 }).map((_, i) => (
                                        <tr key={i} className="animate-pulse">
                                            {Array.from({ length: 8 }).map((_, j) => (
                                                <td key={j} className="px-4 py-3"><div className="h-4 rounded w-20" style={{ background: 'var(--bg-hover)' }} /></td>
                                            ))}
                                        </tr>
                                    ))
                                ) : keys.length === 0 ? (
                                    <tr>
                                        <td colSpan={8} className="px-4 py-12 text-center">
                                            <div className="flex flex-col items-center gap-3">
                                                <PiKeyBold className="text-3xl" style={{ color: 'var(--text-tertiary)' }} />
                                                <p style={{ color: 'var(--text-secondary)' }}>No API keys yet</p>
                                                <button onClick={() => setShowCreateForm(true)} className="text-sm" style={{ color: 'var(--accent)' }}>
                                                    Create your first key
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    keys.map((key) => (
                                        <tr key={key.key_id}>
                                            <td className="px-4" style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{key.name}</td>
                                            <td className="px-4">
                                                <button
                                                    onClick={() => handleCopyKeyId(key.key_id)}
                                                    className="inline-flex items-center gap-1.5 text-xs transition-colors group"
                                                    style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}
                                                    title="Click to copy"
                                                >
                                                    {key.key_id}
                                                    <PiCopyBold className="opacity-0 group-hover:opacity-100 transition-opacity" />
                                                </button>
                                            </td>
                                            <td className="px-4 text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>{formatDate(key.created_at)}</td>
                                            <td className="px-4 text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>{formatDate(key.last_used_at)}</td>
                                            <td className="px-4 text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>{key.expires_at ? formatDate(key.expires_at) : "Never"}</td>
                                            <td className="px-4 text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-secondary)' }}>{key.request_count?.toLocaleString() || 0}</td>
                                            <td className="px-4">{getStatusBadge(key)}</td>
                                            <td className="px-4 text-right">
                                                {key.is_active && (
                                                    <button
                                                        onClick={() => setConfirmRevoke(key)}
                                                        className="p-1.5 rounded transition-colors"
                                                        style={{ color: 'var(--text-tertiary)' }}
                                                        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'var(--danger-bg)'; }}
                                                        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = 'transparent'; }}
                                                        title="Revoke key"
                                                    >
                                                        <PiTrashBold />
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Create Key Modal */}
            {showCreateForm && (
                <ApiKeyForm onClose={() => setShowCreateForm(false)} />
            )}

            {/* Created Key Detail Modal */}
            {showCreatedDetail && createdKey && (
                <ApiKeyDetail
                    keyData={createdKey}
                    onClose={() => setShowCreatedDetail(false)}
                />
            )}

            {/* Revoke Confirmation Modal */}
            {confirmRevoke && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/60" onClick={() => setConfirmRevoke(null)} />
                    <div className="relative rounded-xl p-6 w-full max-w-sm shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Revoke API Key</h3>
                        <p className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
                            Are you sure you want to revoke <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>"{confirmRevoke.name}"</span>?
                        </p>
                        <p className="text-xs mb-5" style={{ color: 'var(--danger)' }}>This action is permanent and cannot be undone.</p>
                        <div className="flex items-center gap-3 justify-end">
                            <button
                                onClick={() => setConfirmRevoke(null)}
                                className="si-button-secondary"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => handleRevoke(confirmRevoke.key_id, confirmRevoke.name)}
                                className="px-4 py-2 text-sm rounded-lg font-medium text-white transition-colors"
                                style={{ background: 'var(--danger)' }}
                            >
                                Revoke Key
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
