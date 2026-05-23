import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { adminApi } from "../../../services/adminApi";
import AdminTable from "../../common/AdminTable";
import AdminFilterBar from "../../common/AdminFilterBar";
import { PiDownloadBold } from "react-icons/pi";

const REASON_OPTIONS = [
    "Illegal Content",
    "Spam/Abuse",
    "Legal Request",
    "False Persona",
    "Policy Violation",
    "Other",
];

const PAGE_SIZE = 50;

const COLUMNS = [
    { key: "service_id", label: "Service ID" },
    { key: "user_name", label: "User Name" },
    { key: "user_e164", label: "Phone" },
    { key: "reason", label: "Reason" },
    { key: "notes", label: "Notes" },
    { key: "deleted_by", label: "Deleted By" },
    { key: "deleted_at", label: "Deleted At" },
];

const SKELETON_WIDTHS = {
    service_id: "w-28", user_name: "w-24", user_e164: "w-20",
    reason: "w-20", notes: "w-32", deleted_by: "w-16", deleted_at: "w-28",
};

export default function AuditLogTable() {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    // Filters
    const [search, setSearch] = useState("");
    const [reasonFilter, setReasonFilter] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");

    const fetchAuditLog = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
            if (search) params.search = search;
            if (reasonFilter) params.reason = reasonFilter;
            if (dateFrom) params.date_from = dateFrom;
            if (dateTo) params.date_to = dateTo;

            const res = await adminApi.getAuditLog(params);
            setItems(res.data.items);
            setTotal(res.data.total);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to fetch audit log.");
        } finally {
            setLoading(false);
        }
    }, [page, search, reasonFilter, dateFrom, dateTo]);

    useEffect(() => { fetchAuditLog(); }, [fetchAuditLog]);

    const handleExportCsv = async () => {
        try {
            const res = await adminApi.exportAuditLogCsv();
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", "deletion_audit_log.csv");
            document.body.appendChild(link);
            link.click();
            link.remove();
            
            window.URL.revokeObjectURL(url);
        } catch {
            toast.error("Failed to export CSV");
        }
    };

    const formatDate = (isoStr) => {
        if (!isoStr) return "N/A";
        try { return new Date(isoStr).toLocaleString(); } catch { return isoStr; }
    };

    const renderCell = (row, col) => {
        switch (col.key) {
            case "service_id":
                return <span className="font-mono text-xs max-w-[180px] truncate block" style={{ color: 'var(--text-primary)' }} title={row.service_id}>{row.service_id}</span>;
            case "user_name":
                return row.user_name || "N/A";
            case "user_e164":
                return <span className="font-mono text-xs">{row.user_e164 || "N/A"}</span>;
            case "reason":
                return (
                    <span className="si-badge si-badge-warning inline-block">
                        {row.reason}
                    </span>
                );
            case "notes":
                return <span className="max-w-[200px] truncate block" style={{ color: 'var(--text-secondary)' }} title={row.notes}>{row.notes || "-"}</span>;
            case "deleted_by":
                return <span className="text-xs">{row.deleted_by}</span>;
            case "deleted_at":
                return <span className="text-xs whitespace-nowrap">{formatDate(row.deleted_at)}</span>;
            default:
                return row[col.key] ?? "\u2014";
        }
    };

    return (
        <div className="space-y-4">
            <AdminFilterBar
                search={{
                    value: search,
                    onChange: (v) => { setSearch(v); setPage(0); },
                    placeholder: "Search by ID, name, phone, admin...",
                    label: "Search",
                }}
                filters={[
                    {
                        type: "select",
                        key: "reason",
                        label: "Reason",
                        value: reasonFilter,
                        onChange: (v) => { setReasonFilter(v); setPage(0); },
                        placeholder: "All Reasons",
                        options: REASON_OPTIONS.map((r) => ({ value: r, label: r })),
                    },
                    {
                        type: "date",
                        key: "dateFrom",
                        label: "From",
                        value: dateFrom,
                        onChange: (v) => { setDateFrom(v); setPage(0); },
                    },
                    {
                        type: "date",
                        key: "dateTo",
                        label: "To",
                        value: dateTo,
                        onChange: (v) => { setDateTo(v); setPage(0); },
                    },
                ]}
                actions={
                    <button
                        onClick={handleExportCsv}
                        className="si-button-secondary flex items-center gap-2"
                    >
                        <PiDownloadBold /> Export CSV
                    </button>
                }
            />

            {error && (
                <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)', color: 'var(--danger)' }}>
                    {error}
                </div>
            )}

            <AdminTable
                columns={COLUMNS}
                data={items}
                rowKey="id"
                renderCell={renderCell}
                renderMobileCard={(row) => (
                    <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        {/* Top: name + reason */}
                        <div className="flex items-start justify-between gap-2">
                            <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                                {row.user_name || "Unknown User"}
                            </span>
                            <span className="si-badge si-badge-warning shrink-0">{row.reason}</span>
                        </div>

                        {/* Middle: phone + ID */}
                        <div className="space-y-1.5">
                            {row.user_e164 && row.user_e164 !== "N/A" && (
                                <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                    <span className="font-mono">{row.user_e164}</span>
                                </div>
                            )}
                            {row.notes && row.notes !== "-" && (
                                <div className="text-xs truncate" style={{ color: 'var(--text-secondary)' }} title={row.notes}>
                                    {row.notes}
                                </div>
                            )}
                            <div className="font-mono text-xs truncate" style={{ color: 'var(--text-tertiary)' }} title={row.service_id}>
                                {row.service_id}
                            </div>
                        </div>

                        {/* Bottom: deleted by + timestamp */}
                        <div className="pt-2 border-t flex items-center justify-between gap-2" style={{ borderColor: 'var(--border)' }}>
                            <span className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{row.deleted_by}</span>
                            <span className="text-xs shrink-0" style={{ color: 'var(--text-tertiary)' }}>{formatDate(row.deleted_at)}</span>
                        </div>
                    </div>
                )}
                loading={loading}
                emptyMessage="No deletion records found."
                skeletonRows={6}
                skeletonWidths={SKELETON_WIDTHS}
                page={page}
                pageSize={PAGE_SIZE}
                total={total}
                onPageChange={setPage}
            />
        </div>
    );
}
