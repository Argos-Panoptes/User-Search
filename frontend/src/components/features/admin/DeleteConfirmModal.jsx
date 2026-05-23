import React, { useState } from "react";
import { PiWarningBold, PiXBold } from "react-icons/pi";

export default function DeleteConfirmModal({
    isOpen,
    onClose,
    onConfirm,
    previewData,
    reason,
    notes,
    isBulk = false,
    bulkCount = 0,
    isLoading = false,
}) {
    const [confirmed, setConfirmed] = useState(false);
    const [bulkConfirmText, setBulkConfirmText] = useState("");
    const [confirmHover, setConfirmHover] = useState(false);

    if (!isOpen) return null;

    const canConfirm = isBulk
        ? bulkConfirmText === "DELETE"
        : confirmed;

    const handleConfirm = () => {
        if (canConfirm) {
            onConfirm();
        }
    };

    const handleClose = () => {
        setConfirmed(false);
        setBulkConfirmText("");
        onClose();
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={handleClose}
            />

            {/* Modal */}
            <div className="relative rounded-xl shadow-2xl max-w-md w-full mx-4 p-6" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2" style={{ color: 'var(--danger)' }}>
                        <PiWarningBold className="text-xl" />
                        <h3 className="text-lg font-semibold">
                            {isBulk ? "Confirm Bulk Deletion" : "Confirm User Deletion"}
                        </h3>
                    </div>
                    <button
                        onClick={handleClose}
                        className="transition-colors"
                        style={{ color: 'var(--text-secondary)' }}
                        onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                    >
                        <PiXBold className="text-lg" />
                    </button>
                </div>

                {/* Warning */}
                <div className="rounded-lg p-3 mb-4" style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)' }}>
                    <p className="text-sm" style={{ color: 'var(--danger)' }}>
                        This action will permanently hide {isBulk ? `${bulkCount} users` : "this user"} from
                        all search results, API responses, and exports. This cannot be undone.
                    </p>
                </div>

                {/* User details (single mode) */}
                {!isBulk && previewData && (
                    <div className="rounded-lg p-3 mb-4 space-y-1" style={{ background: 'var(--bg-hover)' }}>
                        <div className="flex justify-between text-sm">
                            <span style={{ color: 'var(--text-secondary)' }}>Service ID</span>
                            <span className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{previewData.service_id}</span>
                        </div>
                        {previewData.name && (
                            <div className="flex justify-between text-sm">
                                <span style={{ color: 'var(--text-secondary)' }}>Name</span>
                                <span style={{ color: 'var(--text-primary)' }}>{previewData.name}</span>
                            </div>
                        )}
                        {previewData.e164 && (
                            <div className="flex justify-between text-sm">
                                <span style={{ color: 'var(--text-secondary)' }}>Phone</span>
                                <span style={{ color: 'var(--text-primary)' }}>{previewData.e164}</span>
                            </div>
                        )}
                        <div className="flex justify-between text-sm">
                            <span style={{ color: 'var(--text-secondary)' }}>Groups</span>
                            <span style={{ color: 'var(--text-primary)' }}>{previewData.groupCount ?? previewData.group_count ?? 0}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span style={{ color: 'var(--text-secondary)' }}>Reason</span>
                            <span style={{ color: 'var(--warning)' }}>{reason}</span>
                        </div>
                        {notes && (
                            <div className="flex justify-between text-sm">
                                <span style={{ color: 'var(--text-secondary)' }}>Notes</span>
                                <span className="truncate ml-4" style={{ color: 'var(--text-primary)' }}>{notes}</span>
                            </div>
                        )}
                    </div>
                )}

                {/* Bulk info */}
                {isBulk && (
                    <div className="rounded-lg p-3 mb-4" style={{ background: 'var(--bg-hover)' }}>
                        <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
                            You are about to delete <span className="font-bold" style={{ color: 'var(--danger)' }}>{bulkCount}</span> users
                            with reason: <span style={{ color: 'var(--warning)' }}>{reason}</span>
                        </p>
                    </div>
                )}

                {/* Confirmation */}
                {isBulk ? (
                    <div className="mb-4">
                        <label className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
                            Type <span className="font-mono font-bold" style={{ color: 'var(--danger)' }}>DELETE</span> to confirm
                        </label>
                        <input
                            type="text"
                            value={bulkConfirmText}
                            onChange={(e) => setBulkConfirmText(e.target.value)}
                            className="si-input w-full"
                            style={{ borderColor: 'var(--border)' }}
                            placeholder="DELETE"
                        />
                    </div>
                ) : (
                    <label className="flex items-center gap-2 mb-4 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(e) => setConfirmed(e.target.checked)}
                            className="w-4 h-4 rounded"
                            style={{ borderColor: 'var(--border)' }}
                        />
                        <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                            I understand this action is permanent
                        </span>
                    </label>
                )}

                {/* Actions */}
                <div className="flex gap-3 justify-end">
                    <button
                        onClick={handleClose}
                        className="si-button-secondary"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={!canConfirm || isLoading}
                        className="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
                        style={{
                            background: canConfirm && !isLoading
                                ? (confirmHover ? 'color-mix(in srgb, var(--danger) 85%, black)' : 'var(--danger)')
                                : 'color-mix(in srgb, var(--danger) 30%, transparent)',
                            color: canConfirm && !isLoading
                                ? 'var(--text-primary)'
                                : 'color-mix(in srgb, var(--danger) 50%, transparent)',
                            cursor: canConfirm && !isLoading ? 'pointer' : 'not-allowed',
                        }}
                        onMouseEnter={() => setConfirmHover(true)}
                        onMouseLeave={() => setConfirmHover(false)}
                    >
                        {isLoading ? "Deleting..." : isBulk ? `Delete ${bulkCount} Users` : "Delete User"}
                    </button>
                </div>
            </div>
        </div>
    );
}
