import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { adminApi } from "../../../services/adminApi";
import AdminTable from "../../common/AdminTable";
import AdminFilterBar from "../../common/AdminFilterBar";
import AdminModal from "../../common/AdminModal";
import {
    PiPencilSimpleBold,
    PiEyeBold,
    PiArrowCounterClockwiseBold,
    PiFunnelBold,
} from "react-icons/pi";

const PAGE_SIZE = 20;

const COLUMNS = [
    { key: "user", label: "User" },
    { key: "role", label: "Role" },
    { key: "rate_limit", label: "Rate Limit", align: "center" },
    { key: "max_keys", label: "Max Keys", align: "center" },
    { key: "active_keys", label: "Active Keys", align: "center" },
    { key: "actions", label: "Actions", align: "center" },
];

const SKELETON_WIDTHS = {
    user: "w-40", role: "w-16", rate_limit: "w-20",
    max_keys: "w-12", active_keys: "w-12", actions: "w-16",
};

export default function AdminUserLimits() {
    const [users, setUsers] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [customOnly, setCustomOnly] = useState(false);

    // Edit modal
    const [editingUser, setEditingUser] = useState(null);
    const [editForm, setEditForm] = useState({ rate_limit_per_minute: "", max_api_keys: "" });
    const [saving, setSaving] = useState(false);

    // Detail modal
    const [detailUser, setDetailUser] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);

    const fetchUsers = useCallback(async () => {
        setLoading(true);
        try {
            const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
            if (search) params.search = search;
            if (customOnly) params.has_custom_limits = true;
            const res = await adminApi.getUserLimits(params);
            setUsers(res.data?.data || []);
            setTotal(res.data?.pagination?.total || res.data?.data?.length || 0);
        } catch (err) {
            toast.error("Failed to load user limits");
        } finally {
            setLoading(false);
        }
    }, [page, search, customOnly]);

    useEffect(() => { fetchUsers(); }, [fetchUsers]);

    const openEdit = (user) => {
        setEditingUser(user);
        setEditForm({
            rate_limit_per_minute: user.rate_limit_per_minute ?? "",
            max_api_keys: user.max_api_keys ?? "",
        });
    };

    const handleSaveEdit = async () => {
        setSaving(true);
        try {
            const data = {};
            const params = {};

            if (editForm.rate_limit_per_minute === "" || editForm.rate_limit_per_minute === null) {
                params.reset_rate_limit = true;
            } else {
                data.rate_limit_per_minute = parseInt(editForm.rate_limit_per_minute);
            }

            if (editForm.max_api_keys === "" || editForm.max_api_keys === null) {
                params.reset_max_api_keys = true;
            } else {
                data.max_api_keys = parseInt(editForm.max_api_keys);
            }

            await adminApi.updateUserLimits(editingUser.user_id, data, params);
            toast.success("User limits updated");
            setEditingUser(null);
            fetchUsers();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to update limits");
        } finally {
            setSaving(false);
        }
    };

    const openDetail = async (userId) => {
        setDetailLoading(true);
        try {
            const res = await adminApi.getUserLimitDetail(userId);
            setDetailUser(res.data?.data || res.data);
        } catch (err) {
            toast.error("Failed to load user details");
        } finally {
            setDetailLoading(false);
        }
    };

    const renderCell = (row, col) => {
        switch (col.key) {
            case "user":
                return (
                    <>
                        <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{row.full_name || "\u2014"}</div>
                        <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{row.email}</div>
                    </>
                );
            case "role":
                return row.is_superuser
                    ? <span className="si-badge si-badge-warning">Admin</span>
                    : <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>User</span>;
            case "rate_limit":
                return (
                    <>
                        <span className="font-mono text-sm" style={{ color: row.rate_limit_per_minute !== null ? 'var(--accent)' : 'var(--text-secondary)' }}>
                            {row.effective_rate_limit}/min
                        </span>
                        {row.rate_limit_per_minute !== null && <span className="ml-1 text-[10px] uppercase" style={{ color: 'var(--accent)' }}>custom</span>}
                    </>
                );
            case "max_keys":
                return (
                    <>
                        <span className="font-mono text-sm" style={{ color: row.max_api_keys !== null ? 'var(--accent)' : 'var(--text-secondary)' }}>
                            {row.effective_max_api_keys}
                        </span>
                        {row.max_api_keys !== null && <span className="ml-1 text-[10px] uppercase" style={{ color: 'var(--accent)' }}>custom</span>}
                    </>
                );
            case "active_keys":
                return (
                    <span className="font-mono text-sm" style={{ color: row.active_api_keys >= row.effective_max_api_keys ? 'var(--danger)' : 'var(--text-primary)' }}>
                        {row.active_api_keys}/{row.effective_max_api_keys}
                    </span>
                );
            case "actions":
                return (
                    <div className="flex items-center justify-center gap-2">
                        <button onClick={() => openDetail(row.user_id)} className="si-icon-button" title="View details">
                            <PiEyeBold size={16} />
                        </button>
                        <button onClick={() => openEdit(row)} className="si-icon-button" title="Edit limits">
                            <PiPencilSimpleBold size={16} />
                        </button>
                    </div>
                );
            default:
                return row[col.key] ?? "\u2014";
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>User API Limits</h3>
                <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>Manage per-user rate limits and maximum API keys</p>
            </div>

            <AdminFilterBar
                search={{
                    value: search,
                    onChange: (v) => { setSearch(v); setPage(0); },
                    placeholder: "Search by email or name...",
                }}
                filters={[
                    {
                        type: "checkbox",
                        checked: customOnly,
                        onChange: (v) => { setCustomOnly(v); setPage(0); },
                        label: "Custom limits only",
                        icon: <PiFunnelBold style={{ color: 'var(--text-tertiary)' }} />,
                    },
                ]}
            />

            <AdminTable
                columns={COLUMNS}
                data={users}
                rowKey="user_id"
                renderCell={renderCell}
                loading={loading}
                emptyMessage="No users found"
                skeletonWidths={SKELETON_WIDTHS}
                page={page}
                pageSize={PAGE_SIZE}
                total={total}
                onPageChange={setPage}
            />

            {/* Edit Modal */}
            <AdminModal
                open={!!editingUser}
                onClose={() => setEditingUser(null)}
                title="Edit User Limits"
                footer={
                    <>
                        <button
                            onClick={() => setEditingUser(null)}
                            className="px-4 py-2 text-sm transition-colors"
                            style={{ color: 'var(--text-secondary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                        >
                            Cancel
                        </button>
                        <button
                            onClick={() => setEditForm({ rate_limit_per_minute: "", max_api_keys: "" })}
                            className="px-4 py-2 text-sm transition-colors flex items-center gap-1"
                            style={{ color: 'var(--text-secondary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--warning)'}
                            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                            title="Reset both to system defaults"
                        >
                            <PiArrowCounterClockwiseBold size={14} /> Reset
                        </button>
                        <button
                            onClick={handleSaveEdit}
                            disabled={saving}
                            className="si-button-primary disabled:opacity-50"
                        >
                            {saving ? "Saving..." : "Save"}
                        </button>
                    </>
                }
            >
                {editingUser && (
                    <>
                        <div className="mb-4 p-3 rounded-lg" style={{ background: 'var(--bg-hover)' }}>
                            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{editingUser.full_name || "\u2014"}</div>
                            <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{editingUser.email}</div>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>Rate Limit (requests/minute)</label>
                                <input
                                    type="number" min="1" max="10000"
                                    placeholder={`System default: ${editingUser.system_defaults?.rate_limit_per_minute || 30}`}
                                    value={editForm.rate_limit_per_minute}
                                    onChange={(e) => setEditForm({ ...editForm, rate_limit_per_minute: e.target.value })}
                                    className="si-input w-full"
                                />
                                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Leave empty to use system default. This applies to JWT/session auth.</p>
                            </div>
                            <div>
                                <label className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>Maximum API Keys</label>
                                <input
                                    type="number" min="1" max="100"
                                    placeholder={`System default: ${editingUser.system_defaults?.max_api_keys || 5}`}
                                    value={editForm.max_api_keys}
                                    onChange={(e) => setEditForm({ ...editForm, max_api_keys: e.target.value })}
                                    className="si-input w-full"
                                />
                                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Leave empty to use system default. Currently has {editingUser.active_api_keys} active keys.</p>
                            </div>
                        </div>
                    </>
                )}
            </AdminModal>

            {/* Detail Modal */}
            <AdminModal
                open={!!detailUser || detailLoading}
                onClose={() => setDetailUser(null)}
                title="User Limit Details"
                maxWidth="max-w-lg"
            >
                {detailLoading ? (
                    <div className="space-y-3 animate-pulse">
                        {[...Array(4)].map((_, i) => <div key={i} className="h-4 rounded w-full" style={{ background: 'var(--bg-hover)' }} />)}
                    </div>
                ) : detailUser ? (
                    <div className="space-y-4">
                        <div className="p-3 rounded-lg" style={{ background: 'var(--bg-hover)' }}>
                            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{detailUser.full_name || "\u2014"}</div>
                            <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{detailUser.email}</div>
                            {detailUser.is_superuser && (
                                <span className="si-badge si-badge-warning inline-block mt-1">Admin</span>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 rounded-lg" style={{ background: 'var(--bg-hover)' }}>
                                <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Rate Limit</div>
                                <div className="text-lg font-mono" style={{ color: 'var(--text-primary)' }}>
                                    {detailUser.effective_rate_limit}<span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>/min</span>
                                </div>
                                <span className="text-[10px] uppercase" style={{ color: detailUser.rate_limit_per_minute !== null ? 'var(--accent)' : 'var(--text-tertiary)' }}>
                                    {detailUser.rate_limit_per_minute !== null ? "custom" : "system default"}
                                </span>
                            </div>
                            <div className="p-3 rounded-lg" style={{ background: 'var(--bg-hover)' }}>
                                <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Max API Keys</div>
                                <div className="text-lg font-mono" style={{ color: 'var(--text-primary)' }}>
                                    {detailUser.active_api_keys}<span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>/{detailUser.effective_max_api_keys}</span>
                                </div>
                                <span className="text-[10px] uppercase" style={{ color: detailUser.max_api_keys !== null ? 'var(--accent)' : 'var(--text-tertiary)' }}>
                                    {detailUser.max_api_keys !== null ? "custom" : "system default"}
                                </span>
                            </div>
                        </div>

                        {detailUser.keys?.length > 0 && (
                            <div>
                                <div className="si-label mb-2">Active API Keys</div>
                                <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                                    {detailUser.keys.map((k) => (
                                        <div key={k.key_id} className="flex items-center justify-between p-2 rounded-lg text-xs" style={{ background: 'var(--bg-hover)' }}>
                                            <div>
                                                <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{k.key_id}</span>
                                                <span className="ml-2" style={{ color: 'var(--text-tertiary)' }}>{k.name}</span>
                                            </div>
                                            <div style={{ color: 'var(--text-tertiary)' }}>
                                                {k.quota_limit}/min | {k.request_count} reqs
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="p-3 rounded-lg text-xs" style={{ background: 'color-mix(in srgb, var(--bg-hover) 50%, transparent)', color: 'var(--text-tertiary)' }}>
                            System defaults: {detailUser.system_defaults?.rate_limit_per_minute}/min rate limit, {detailUser.system_defaults?.max_api_keys} max keys
                        </div>
                    </div>
                ) : null}
            </AdminModal>
        </div>
    );
}
