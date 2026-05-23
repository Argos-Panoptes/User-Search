import React from "react";
import { PiXBold } from "react-icons/pi";

/**
 * Reusable modal overlay for admin panels.
 *
 * Props:
 *  open      - Boolean to show/hide
 *  onClose   - () => void
 *  title     - String header title
 *  maxWidth  - Tailwind max-width class (default: "max-w-md")
 *  children  - Modal body content
 *  footer    - Optional ReactNode for action buttons
 */
export default function AdminModal({
    open,
    onClose,
    title,
    maxWidth = "max-w-md",
    children,
    footer,
}) {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60" onClick={onClose} />
            <div className={`relative rounded-xl ${maxWidth} w-full shadow-2xl`} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
                    <button onClick={onClose} className="transition-colors si-icon-button" style={{ color: 'var(--text-tertiary)' }}>
                        <PiXBold />
                    </button>
                </div>

                {/* Body */}
                <div className="px-6 py-5">
                    {children}
                </div>

                {/* Footer */}
                {footer && (
                    <div className="flex items-center justify-end gap-3 px-6 py-4" style={{ borderTop: '1px solid var(--border)' }}>
                        {footer}
                    </div>
                )}
            </div>
        </div>
    );
}

/**
 * Reusable confirm dialog built on AdminModal.
 *
 * Props:
 *  open           - Boolean
 *  onClose        - () => void
 *  onConfirm      - () => void
 *  title          - String
 *  message        - ReactNode
 *  subMessage     - Optional small text below message
 *  confirmLabel   - String (default: "Confirm")
 *  confirmVariant - "danger" | "primary" (default: "danger")
 *  loading        - Boolean for confirm button
 */
export function AdminConfirmModal({
    open,
    onClose,
    onConfirm,
    title,
    message,
    subMessage,
    confirmLabel = "Confirm",
    confirmVariant = "danger",
    loading = false,
}) {
    if (!open) return null;

    const btnStyle = confirmVariant === "danger"
        ? { background: 'var(--danger)', color: 'var(--text-on-accent)' }
        : { background: 'var(--accent)', color: 'var(--text-on-accent)' };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60" onClick={onClose} />
            <div className="relative rounded-xl p-6 w-full max-w-sm shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>{title}</h3>
                <div className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>{message}</div>
                {subMessage && <p className="text-xs mb-5" style={{ color: 'var(--danger)' }}>{subMessage}</p>}
                {!subMessage && <div className="mb-5" />}
                <div className="flex items-center gap-3 justify-end">
                    <button
                        onClick={onClose}
                        className="si-button-secondary px-4 py-2 text-sm rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium transition-colors disabled:opacity-50"
                        style={btnStyle}
                    >
                        {loading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
