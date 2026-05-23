import React from "react";

export default function AdminFilterBar({ search, filters = [], actions }) {
    const nonCheckboxFilters = filters.filter(f => f.type !== "checkbox");
    const checkboxFilters = filters.filter(f => f.type === "checkbox");

    const renderFilterControl = (f, i) => {
        if (f.type === "select") {
            return (
                <div key={f.key || i} className="flex flex-col">
                    {f.label && <label className="block text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{f.label}</label>}
                    <select
                        value={f.value}
                        onChange={(e) => f.onChange(e.target.value)}
                        className="si-select w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
                    >
                        {f.placeholder && <option value="">{f.placeholder}</option>}
                        {f.options.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                    </select>
                </div>
            );
        }

        if (f.type === "date") {
            return (
                <div key={f.key || i} className="flex flex-col">
                    {f.label && <label className="block text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{f.label}</label>}
                    <input
                        type="date"
                        value={f.value}
                        onChange={(e) => f.onChange(e.target.value)}
                        className="si-input w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
                    />
                </div>
            );
        }

        if (f.type === "custom") {
            return <React.Fragment key={f.key || i}>{f.render()}</React.Fragment>;
        }

        return null;
    };

    return (
        <div className="space-y-3">
            {/* Row 1: Search (full width) */}
            {search && (
                <div className="w-full">
                    {search.label && <label className="block text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{search.label}</label>}
                    <div className="relative">
                        <input
                            type="text"
                            value={search.value}
                            onChange={(e) => search.onChange(e.target.value)}
                            placeholder={search.placeholder || "Search..."}
                            className="si-input w-full rounded-lg pl-3 pr-9 py-2 text-sm focus:outline-none"
                        />
                        <svg className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 pointer-events-none" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                    </div>
                </div>
            )}

            {/* Row 2: Filters + Actions */}
            {(nonCheckboxFilters.length > 0 || checkboxFilters.length > 0 || actions) && (
                <div className="flex flex-wrap gap-3 items-end">
                    {/* Mobile: 2-col grid for non-checkbox filters; desktop: inline flex */}
                    {nonCheckboxFilters.length > 0 && (
                        <div className="grid grid-cols-2 gap-3 w-full md:contents">
                            {nonCheckboxFilters.map((f, i) => renderFilterControl(f, i))}
                        </div>
                    )}

                    {checkboxFilters.map((f, i) => (
                        <label key={f.key || i} className="flex items-center gap-2 text-xs cursor-pointer self-center" style={{ color: 'var(--text-secondary)' }}>
                            <input
                                type="checkbox"
                                checked={f.checked}
                                onChange={(e) => f.onChange(e.target.checked)}
                                className="rounded"
                                style={{ background: 'var(--bg-hover)', borderColor: 'var(--border)' }}
                            />
                            {f.icon}
                            {f.label}
                        </label>
                    ))}

                    {actions && (
                        <div className="flex items-center gap-2 w-full md:w-auto md:ml-auto">
                            {actions}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
