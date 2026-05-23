import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import toast from "react-hot-toast";
import { adminApi } from "../../../services/adminApi";
import AdminTable from "../../common/AdminTable";
import AdminFilterBar from "../../common/AdminFilterBar";
import AdminModal, { AdminConfirmModal } from "../../common/AdminModal";
import {
    PiPlusBold,
    PiCopyBold,
    PiTrashBold,
    PiPencilSimpleBold,
    PiKeyBold,
    PiCheckCircleBold,
    PiXCircleBold,
    PiClockBold,
    PiEyeBold,
    PiBookOpenBold,
} from "react-icons/pi";
import { API_DOCS_URL } from "../../../config";

const PAGE_SIZE = 20;

const EXPIRY_OPTIONS = [
    { value: "30", label: "30 days" },
    { value: "90", label: "90 days" },
    { value: "365", label: "1 year" },
];

const ENDPOINT_OPTIONS = [
    { label: "Users",  value: "/v1/users" },
    { label: "Groups", value: "/v1/groups" },
    { label: "Media",  value: "/v1/media" },
];

const COLUMNS = [
    { key: "key_id", label: "Key ID" },
    { key: "name", label: "Name" },
    { key: "created_by_id", label: "Owner ID" },
    { key: "created_at", label: "Created" },
    { key: "last_used_at", label: "Last Used" },
    { key: "quota_limit", label: "Quota" },
    { key: "request_count", label: "Requests" },
    { key: "allowed_endpoints", label: "Endpoints" },
    { key: "status", label: "Status" },
    { key: "actions", label: "Actions", align: "right" },
];

const SKELETON_WIDTHS = {
    key_id: "w-24", name: "w-20", created_by_id: "w-12", created_at: "w-20",
    last_used_at: "w-20", quota_limit: "w-14", request_count: "w-14",
    allowed_endpoints: "w-20", status: "w-16", actions: "w-16",
};

export default function AdminApiKeyManagement() {
    const [keys, setKeys] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(false);
    const [includeInactive, setIncludeInactive] = useState(false);

    // Create form
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [createForm, setCreateForm] = useState({ name: "", description: "", expires_in_days: "30", quota_limit: "", allowed_endpoints: [] });
    const [creating, setCreating] = useState(false);
    const [createdKeyData, setCreatedKeyData] = useState(null);

    // Edit form
    const [editingKey, setEditingKey] = useState(null);
    const [editForm, setEditForm] = useState({});
    const [saving, setSaving] = useState(false);

    // Detail view
    const [detailKey, setDetailKey] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);

    // Revoke
    const [confirmRevoke, setConfirmRevoke] = useState(null);

    const navigate = useNavigate();

    const fetchKeys = useCallback(async () => {
        setLoading(true);
        try {
            const res = await adminApi.getAllApiKeys({
                limit: PAGE_SIZE,
                offset: page * PAGE_SIZE,
                include_inactive: includeInactive,
            });
            setKeys(res.data?.data || []);
            setTotal(res.data?.pagination?.total || 0);
        } catch (err) {
            toast.error("Failed to load API keys");
        } finally {
            setLoading(false);
        }
    }, [page, includeInactive]);

    useEffect(() => { fetchKeys(); }, [fetchKeys]);

    const handleCreate = async (e) => {
        e.preventDefault();
        if (!createForm.name.trim()) return toast.error("Key name is required");
        setCreating(true);
        try {
            const data = {
                name: createForm.name.trim(),
                description: createForm.description.trim() || null,
                expires_in_days: parseInt(createForm.expires_in_days),
                quota_limit: createForm.quota_limit ? parseInt(createForm.quota_limit) : null,
                allowed_endpoints: createForm.allowed_endpoints.length > 0 ? createForm.allowed_endpoints : null,
            };
            const res = await adminApi.createApiKeyOnBehalf(data);
            setCreatedKeyData(res.data?.data || res.data);
            toast.success("API key created");
            fetchKeys();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to create key");
        } finally {
            setCreating(false);
        }
    };

    const handleRevoke = async (keyId) => {
        try {
            await adminApi.revokeApiKey(keyId);
            toast.success("Key revoked");
            setConfirmRevoke(null);
            fetchKeys();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to revoke key");
        }
    };

    const handleViewDetail = async (keyId) => {
        setDetailLoading(true);
        try {
            const res = await adminApi.getAdminApiKeyDetail(keyId);
            setDetailKey(res.data?.data || res.data);
        } catch {
            toast.error("Failed to load key details");
        } finally {
            setDetailLoading(false);
        }
    };

    const handleStartEdit = (key) => {
        setEditingKey(key.key_id);
        setEditForm({ name: key.name || "", quota_limit: key.quota_limit || "", expires_in_days: "30" });
    };

    const handleSaveEdit = async () => {
        setSaving(true);
        try {
            const updates = {};
            if (editForm.name) updates.name = editForm.name;
            if (editForm.quota_limit) updates.quota_limit = parseInt(editForm.quota_limit);
            if (editForm.expires_in_days) updates.expires_in_days = parseInt(editForm.expires_in_days);
            await adminApi.updateApiKey(editingKey, updates);
            toast.success("Key updated");
            setEditingKey(null);
            fetchKeys();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to update key");
        } finally {
            setSaving(false);
        }
    };

    const handleCopy = (text) => {
        navigator.clipboard.writeText(text);
        toast.success("Copied");
    };

    const formatDate = (iso) => {
        if (!iso) return "N/A";
        return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    };

    const getStatusBadge = (key) => {
        if (!key.is_active) return <span className="si-badge si-badge-danger inline-flex items-center gap-1"><PiXCircleBold /> Revoked</span>;
        if (key.expires_at && new Date(key.expires_at) < new Date()) return <span className="si-badge si-badge-warning inline-flex items-center gap-1"><PiClockBold /> Expired</span>;
        return <span className="si-badge si-badge-success inline-flex items-center gap-1"><PiCheckCircleBold /> Active</span>;
    };

    const renderCell = (row, col) => {
        switch (col.key) {
            case "key_id":
                return (
                    <button onClick={() => handleCopy(row.key_id)} className="font-mono text-xs transition-colors" style={{ color: 'var(--text-secondary)' }} onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'} onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'} title="Copy Key ID">
                        {row.key_id}
                    </button>
                );
            case "name":
                return <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{row.name}</span>;
            case "created_by_id":
                return <span className="text-xs font-mono">{row.created_by_id || "\u2014"}</span>;
            case "created_at":
                return <span className="text-xs whitespace-nowrap">{formatDate(row.created_at)}</span>;
            case "last_used_at":
                return <span className="text-xs whitespace-nowrap">{formatDate(row.last_used_at)}</span>;
            case "quota_limit":
                return <span className="text-xs">{row.quota_limit || "Default"}/min</span>;
            case "request_count":
                return <span className="text-xs font-mono">{(row.request_count || 0).toLocaleString()}</span>;
            case "allowed_endpoints":
                return row.allowed_endpoints?.length
                    ? <div className="flex flex-wrap gap-1">{row.allowed_endpoints.map(ep => <span key={ep} className="si-badge si-badge-default text-xs">{ep}</span>)}</div>
                    : <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>All</span>;
            case "status":
                return getStatusBadge(row);
            case "actions":
                return (
                    <div className="flex items-center justify-end gap-1">
                        <button onClick={() => handleViewDetail(row.key_id)} className="si-icon-button" title="View details">
                            <PiEyeBold />
                        </button>
                        {row.is_active && (
                            <>
                                <button onClick={() => handleStartEdit(row)} className="si-icon-button" title="Edit">
                                    <PiPencilSimpleBold />
                                </button>
                                <button onClick={() => setConfirmRevoke(row)} className="si-icon-button" title="Revoke">
                                    <PiTrashBold />
                                </button>
                            </>
                        )}
                    </div>
                );
            default:
                return row[col.key] ?? "\u2014";
        }
    };

    return (
        <div className="space-y-6">
            {/* Header + Filters */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>All API Keys</h3>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => navigate(API_DOCS_URL)}
                        className="si-button-secondary flex items-center gap-2 flex-1 sm:flex-none justify-center"
                    >
                        <PiBookOpenBold /> API Docs
                    </button>
                    <button
                        onClick={() => { setShowCreateForm(true); setCreatedKeyData(null); setCreateForm({ name: "", description: "", expires_in_days: "30", quota_limit: "", allowed_endpoints: [] }); }}
                        className="si-button-primary flex items-center gap-2 flex-1 sm:flex-none justify-center"
                    >
                        <PiPlusBold /> Create Key
                    </button>
                </div>
            </div>

            <AdminFilterBar
                filters={[
                    {
                        type: "checkbox",
                        checked: includeInactive,
                        onChange: (v) => { setIncludeInactive(v); setPage(0); },
                        label: "Show revoked",
                    },
                ]}
            />

            <AdminTable
                columns={COLUMNS}
                data={keys}
                rowKey="key_id"
                renderCell={renderCell}
                renderMobileCard={(row) => (
                    <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        {/* Top: name + status */}
                        <div className="flex items-start justify-between gap-2">
                            <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{row.name}</span>
                            {getStatusBadge(row)}
                        </div>

                        {/* Middle: key details */}
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between gap-2">
                                <button
                                    onClick={() => handleCopy(row.key_id)}
                                    className="font-mono text-xs truncate text-left"
                                    style={{ color: 'var(--text-tertiary)', maxWidth: '70%' }}
                                    title={row.key_id}
                                >
                                    {row.key_id}
                                </button>
                                <button onClick={() => handleCopy(row.key_id)} className="si-icon-button shrink-0" style={{ width: 28, height: 28 }} title="Copy Key ID">
                                    <PiCopyBold className="text-xs" />
                                </button>
                            </div>

                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                <div><span style={{ color: 'var(--text-tertiary)' }}>Owner</span> {row.created_by_id || "—"}</div>
                                <div><span style={{ color: 'var(--text-tertiary)' }}>Quota</span> {row.quota_limit || "Default"}/min</div>
                                <div><span style={{ color: 'var(--text-tertiary)' }}>Requests</span> {(row.request_count || 0).toLocaleString()}</div>
                                <div>
                                    <span style={{ color: 'var(--text-tertiary)' }}>Endpoints </span>
                                    {row.allowed_endpoints?.length ? row.allowed_endpoints.join(", ") : "All"}
                                </div>
                            </div>
                        </div>

                        {/* Bottom: dates + actions */}
                        <div className="pt-2 border-t flex items-center justify-between gap-2" style={{ borderColor: 'var(--border)' }}>
                            <div className="text-xs space-y-0.5" style={{ color: 'var(--text-tertiary)' }}>
                                <div>Created {formatDate(row.created_at)}</div>
                                <div>Used {formatDate(row.last_used_at)}</div>
                            </div>
                            <div className="flex items-center gap-1">
                                <button onClick={() => handleViewDetail(row.key_id)} className="si-icon-button" style={{ width: 30, height: 30 }} title="View details">
                                    <PiEyeBold className="text-xs" />
                                </button>
                                {row.is_active && (
                                    <>
                                        <button onClick={() => handleStartEdit(row)} className="si-icon-button" style={{ width: 30, height: 30 }} title="Edit">
                                            <PiPencilSimpleBold className="text-xs" />
                                        </button>
                                        <button onClick={() => setConfirmRevoke(row)} className="si-icon-button" style={{ width: 30, height: 30 }} title="Revoke">
                                            <PiTrashBold className="text-xs" />
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                )}
                loading={loading}
                emptyIcon={<PiKeyBold />}
                emptyMessage="No API keys found"
                skeletonWidths={SKELETON_WIDTHS}
                page={page}
                pageSize={PAGE_SIZE}
                total={total}
                onPageChange={setPage}
            />

            {/* Create Key Modal */}
            <AdminModal
                open={showCreateForm}
                onClose={() => { setShowCreateForm(false); setCreatedKeyData(null); setCreateForm({ name: "", description: "", expires_in_days: "30", quota_limit: "", allowed_endpoints: [] }); }}
                title={createdKeyData ? "Key Created" : "Create API Key"}
            >
                {createdKeyData ? (
                    <div className="space-y-4">
                        <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning)', color: 'var(--warning)' }}>
                            Copy this key now. It will <strong>not</strong> be shown again.
                        </div>
                        <div>
                            <label className="si-label block mb-1">API Key</label>
                            <div className="flex items-center gap-2">
                                <div className="si-input flex-1 font-mono text-sm break-all select-all" style={{ color: 'var(--accent)' }}>
                                    {createdKeyData.raw_key}
                                </div>
                                <button onClick={() => handleCopy(createdKeyData.raw_key)} className="si-icon-button"><PiCopyBold /></button>
                            </div>
                        </div>
                        <button onClick={() => { setShowCreateForm(false); setCreatedKeyData(null); }} className="si-button-primary w-full">Done</button>
                    </div>
                ) : (
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Key Name <span style={{ color: 'var(--danger)' }}>*</span></label>
                            <input type="text" value={createForm.name} onChange={(e) => setCreateForm(f => ({ ...f, name: e.target.value.slice(0, 50) }))} maxLength={50} placeholder="e.g. Customer API Key" className="si-input w-full" autoFocus />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Description</label>
                            <input type="text" value={createForm.description} onChange={(e) => setCreateForm(f => ({ ...f, description: e.target.value.slice(0, 200) }))} maxLength={200} placeholder="Optional description" className="si-input w-full" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Quota (req/min)</label>
                            <input type="number" value={createForm.quota_limit} onChange={(e) => setCreateForm(f => ({ ...f, quota_limit: e.target.value }))} placeholder="Default" className="si-input w-full" />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Expiration</label>
                            <select value={createForm.expires_in_days} onChange={(e) => setCreateForm(f => ({ ...f, expires_in_days: e.target.value }))} className="si-select w-full">
                                {EXPIRY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Allowed Endpoints</label>
                            <div className="flex flex-wrap gap-2">
                                {ENDPOINT_OPTIONS.map(({ label, value }) => (
                                    <label key={value} className="flex items-center gap-1.5 text-sm cursor-pointer" style={{ color: 'var(--text-primary)' }}>
                                        <input type="checkbox" checked={createForm.allowed_endpoints.includes(value)} onChange={(e) => {
                                            setCreateForm(f => ({
                                                ...f,
                                                allowed_endpoints: e.target.checked
                                                    ? [...f.allowed_endpoints, value]
                                                    : f.allowed_endpoints.filter(x => x !== value)
                                            }));
                                        }} className="rounded" style={{ background: 'var(--bg-hover)', borderColor: 'var(--border)' }} />
                                        {label}
                                    </label>
                                ))}
                            </div>
                        </div>
                        <div className="flex items-center gap-3 justify-end pt-2">
                            <button type="button" onClick={() => setShowCreateForm(false)} className="si-button-secondary">Cancel</button>
                            <button type="submit" disabled={creating || !createForm.name.trim()} className="si-button-primary flex items-center gap-2 disabled:opacity-30">
                                {creating && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                                Create Key
                            </button>
                        </div>
                    </form>
                )}
            </AdminModal>

            {/* Edit Modal */}
            <AdminModal
                open={!!editingKey}
                onClose={() => setEditingKey(null)}
                title="Edit API Key"
                maxWidth="max-w-sm"
                footer={
                    <>
                        <button onClick={() => setEditingKey(null)} className="si-button-secondary">Cancel</button>
                        <button onClick={handleSaveEdit} disabled={saving} className="si-button-primary flex items-center gap-2">
                            {saving && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                            Save
                        </button>
                    </>
                }
            >
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Name</label>
                        <input type="text" value={editForm.name} onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))} className="si-input w-full" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Quota (req/min)</label>
                        <input type="number" value={editForm.quota_limit} onChange={(e) => setEditForm(f => ({ ...f, quota_limit: e.target.value }))} className="si-input w-full" />
                    </div>
                </div>
            </AdminModal>

            {/* Detail Modal */}
            <AdminModal
                open={!!detailKey}
                onClose={() => setDetailKey(null)}
                title="Key Details"
            >
                {detailKey && (
                    <div className="space-y-3 text-sm">
                        {[
                            ["Key ID", detailKey.key_id, true],
                            ["Name", detailKey.name],
                            ["Description", detailKey.description || "\u2014"],
                            ["Owner ID", detailKey.created_by_id],
                            ["Created", formatDate(detailKey.created_at)],
                            ["Last Used", formatDate(detailKey.last_used_at)],
                            ["Expires", detailKey.expires_at ? formatDate(detailKey.expires_at) : "Never"],
                            ["Quota", `${detailKey.quota_limit || "Default"}/min`],
                            ["Requests", (detailKey.request_count || 0).toLocaleString()],
                            ["Endpoints", detailKey.allowed_endpoints?.join(", ") || "All"],
                            ["Status", detailKey.is_active ? "Active" : "Revoked"],
                        ].map(([label, value, mono]) => (
                            <div key={label} className="flex justify-between items-center">
                                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                                <span className={mono ? "font-mono text-xs" : ""} style={{ color: 'var(--text-primary)' }}>{value}</span>
                            </div>
                        ))}
                    </div>
                )}
            </AdminModal>

            {/* Revoke Confirmation */}
            <AdminConfirmModal
                open={!!confirmRevoke}
                onClose={() => setConfirmRevoke(null)}
                onConfirm={() => handleRevoke(confirmRevoke.key_id)}
                title="Revoke API Key"
                message={<>Revoke <span className="font-medium" style={{ color: 'var(--text-primary)' }}>"{confirmRevoke?.name}"</span>?</>}
                subMessage="This action is permanent."
                confirmLabel="Revoke"
                confirmVariant="danger"
            />
        </div>
    );
}
