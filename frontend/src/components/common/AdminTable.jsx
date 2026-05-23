import React from "react";
import { PiCaretLeftBold, PiCaretRightBold } from "react-icons/pi";
import useIsMobile from "../../hooks/useIsMobile";

export default function AdminTable({
    columns,
    data,
    rowKey,
    renderCell,
    renderMobileCard,
    loading = false,
    emptyIcon = null,
    emptyMessage = "No results found",
    skeletonRows = 5,
    skeletonWidths = {},
    page = 0,
    pageSize = 20,
    total = 0,
    onPageChange,
    rowClassName,
    onRowClick,
}) {
    const isMobile = useIsMobile();
    const totalPages = Math.ceil(total / pageSize);
    const getRowKey = typeof rowKey === "function" ? rowKey : (row) => row[rowKey];

    const pagination = totalPages > 1 && (
        <div className="flex items-center justify-between text-sm mt-4" style={{ color: 'var(--text-secondary)' }}>
            <span>
                Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
            </span>
            <div className="flex items-center gap-2">
                <button
                    onClick={() => onPageChange(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="p-1.5 rounded"
                    style={page === 0 ? { color: 'var(--text-tertiary)', cursor: 'not-allowed' } : { color: 'var(--text-secondary)' }}
                    onMouseEnter={(e) => { if (page !== 0) { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; } }}
                    onMouseLeave={(e) => { if (page !== 0) { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = ''; } }}
                >
                    <PiCaretLeftBold />
                </button>
                <span style={{ color: 'var(--text-primary)' }}>Page {page + 1} of {totalPages}</span>
                <button
                    onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
                    disabled={page >= totalPages - 1}
                    className="p-1.5 rounded"
                    style={page >= totalPages - 1 ? { color: 'var(--text-tertiary)', cursor: 'not-allowed' } : { color: 'var(--text-secondary)' }}
                    onMouseEnter={(e) => { if (page < totalPages - 1) { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; } }}
                    onMouseLeave={(e) => { if (page < totalPages - 1) { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = ''; } }}
                >
                    <PiCaretRightBold />
                </button>
            </div>
        </div>
    );

    // Mobile card layout
    if (isMobile && renderMobileCard) {
        if (loading) {
            return (
                <div className="space-y-3">
                    {Array.from({ length: skeletonRows }).map((_, i) => (
                        <div key={i} className="animate-pulse rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                            <div className="flex justify-between">
                                <div className="h-4 w-28 rounded" style={{ background: 'var(--bg-hover)' }} />
                                <div className="h-5 w-16 rounded-full" style={{ background: 'var(--bg-hover)' }} />
                            </div>
                            <div className="h-3 w-40 rounded" style={{ background: 'var(--bg-hover)' }} />
                            <div className="h-3 w-32 rounded" style={{ background: 'var(--bg-hover)' }} />
                            <div className="h-3 w-24 rounded" style={{ background: 'var(--bg-hover)' }} />
                        </div>
                    ))}
                </div>
            );
        }

        if (data.length === 0) {
            return (
                <div className="rounded-xl py-12 text-center" style={{ border: '1px solid var(--border)' }}>
                    {emptyIcon && <div className="text-3xl mx-auto mb-2 flex justify-center" style={{ color: 'var(--text-tertiary)' }}>{emptyIcon}</div>}
                    <p style={{ color: 'var(--text-secondary)' }}>{emptyMessage}</p>
                </div>
            );
        }

        return (
            <>
                <div className="space-y-3">
                    {data.map((row, idx) => (
                        <div key={getRowKey(row, idx)} onClick={onRowClick ? () => onRowClick(row) : undefined} className={onRowClick ? "cursor-pointer" : ""}>
                            {renderMobileCard(row)}
                        </div>
                    ))}
                </div>
                {pagination}
            </>
        );
    }

    // Desktop table layout
    return (
        <>
            <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                <div className="overflow-x-auto">
                    <table className="si-data-table w-full text-sm">
                        <thead>
                            <tr style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }} className="text-left">
                                {columns.map((col) => (
                                    <th
                                        key={col.key}
                                        className={`px-4 py-3 font-medium ${col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""} ${col.headerClassName || ""}`}
                                    >
                                        {col.label}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                Array.from({ length: skeletonRows }).map((_, i) => (
                                    <tr key={i} className="animate-pulse" style={{ borderBottom: '1px solid var(--border)' }}>
                                        {columns.map((col) => (
                                            <td key={col.key} className="px-4 py-3">
                                                <div className={`h-4 rounded ${skeletonWidths[col.key] || "w-16"} ${col.align === "center" ? "mx-auto" : ""}`} style={{ background: 'var(--bg-hover)', opacity: 0.5 }} />
                                            </td>
                                        ))}
                                    </tr>
                                ))
                            ) : data.length === 0 ? (
                                <tr>
                                    <td colSpan={columns.length} className="px-4 py-12 text-center">
                                        {emptyIcon && <div className="text-3xl mx-auto mb-2 flex justify-center" style={{ color: 'var(--text-tertiary)' }}>{emptyIcon}</div>}
                                        <p style={{ color: 'var(--text-secondary)' }}>{emptyMessage}</p>
                                    </td>
                                </tr>
                            ) : (
                                data.map((row, idx) => (
                                    <tr
                                        key={getRowKey(row, idx)}
                                        className={`${onRowClick ? "cursor-pointer" : ""} ${rowClassName ? rowClassName(row) : ""}`}
                                        style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border)' }}
                                        onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                        onMouseLeave={(e) => e.currentTarget.style.background = ''}
                                        onClick={onRowClick ? () => onRowClick(row) : undefined}
                                    >
                                        {columns.map((col) => (
                                            <td
                                                key={col.key}
                                                className={`px-4 py-3 ${col.align === "center" ? "text-center" : col.align === "right" ? "text-right" : ""} ${col.className || ""}`}
                                            >
                                                {renderCell(row, col)}
                                            </td>
                                        ))}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            {pagination}
        </>
    );
}
