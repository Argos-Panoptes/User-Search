import React, { useEffect, useState } from "react";
import { apiKeyApi } from "../../../services/apiKeyApi";
import {
    PiChartBarBold,
    PiClockBold,
    PiLightningBold,
    PiKeyBold,
} from "react-icons/pi";

function StatCard({ icon: Icon, label, value, subtext, color = "electric" }) {
    const colorMap = {
        electric: { color: 'var(--accent)', bg: 'var(--bg-accent-muted)', border: 'var(--accent)' },
        emerald: { color: 'var(--success)', bg: 'var(--success-bg)', border: 'var(--success)' },
        amber: { color: 'var(--warning)', bg: 'var(--warning-bg)', border: 'var(--warning)' },
        slate: { color: 'var(--text-secondary)', bg: 'var(--bg-hover)', border: 'var(--border)' },
    };

    const c = colorMap[color];

    return (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg" style={{ color: c.color, background: c.bg, border: `1px solid ${c.border}` }}>
                    <Icon className="text-lg" />
                </div>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
            </div>
            <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</div>
            {subtext && <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{subtext}</p>}
        </div>
    );
}

function SimpleBarChart({ data, maxValue }) {
    if (!data || data.length === 0) return null;
    const max = maxValue || Math.max(...data.map(d => d.value), 1);

    return (
        <div className="flex items-end gap-1 h-32">
            {data.map((item, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full relative flex items-end justify-center" style={{ height: '100px' }}>
                        <div
                            className="w-full rounded-t transition-all"
                            style={{ height: `${Math.max((item.value / max) * 100, 2)}%`, background: 'color-mix(in srgb, var(--accent) 30%, transparent)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}
                            title={`${item.label}: ${item.value}`}
                        />
                    </div>
                    <span className="text-[10px] truncate w-full text-center" style={{ color: 'var(--text-tertiary)' }}>{item.label}</span>
                </div>
            ))}
        </div>
    );
}

export default function UsageStatsPanel() {
    const [keys, setKeys] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const res = await apiKeyApi.getMyApiKeys({ limit: 50 });
            setKeys(res.data?.data || []);
        } catch {
            // silently fail
        } finally {
            setLoading(false);
        }
    };

    const totalKeys = keys.length;
    const activeKeys = keys.filter(k => k.is_active).length;
    const totalRequests = keys.reduce((sum, k) => sum + (k.request_count || 0), 0);
    const lastUsed = keys
        .filter(k => k.last_used_at)
        .sort((a, b) => new Date(b.last_used_at) - new Date(a.last_used_at))[0];

    const topKeys = [...keys]
        .sort((a, b) => (b.request_count || 0) - (a.request_count || 0))
        .slice(0, 7)
        .map(k => ({ label: k.name?.slice(0, 8) || k.key_id.slice(0, 6), value: k.request_count || 0 }));

    if (loading) {
        return (
            <div className="space-y-6">
                <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Usage Statistics</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="rounded-lg p-4 animate-pulse" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                            <div className="h-4 rounded w-20 mb-3" style={{ background: 'var(--border)' }} />
                            <div className="h-8 rounded w-16" style={{ background: 'var(--border)' }} />
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Usage Statistics</h3>
                <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>Overview of your API key usage</p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={PiKeyBold} label="Total Keys" value={totalKeys} color="electric" />
                <StatCard icon={PiLightningBold} label="Active Keys" value={activeKeys} color="emerald" />
                <StatCard icon={PiChartBarBold} label="Total Requests" value={totalRequests.toLocaleString()} color="amber" />
                <StatCard
                    icon={PiClockBold}
                    label="Last Activity"
                    value={lastUsed ? new Date(lastUsed.last_used_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "N/A"}
                    subtext={lastUsed ? lastUsed.name : "No API calls yet"}
                    color="slate"
                />
            </div>

            {/* Top Keys Chart */}
            {topKeys.length > 0 && (
                <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                    <h4 className="text-sm font-medium mb-4" style={{ color: 'var(--text-primary)' }}>Requests by Key</h4>
                    <SimpleBarChart data={topKeys} />
                </div>
            )}

            {/* Keys Breakdown Table */}
            {keys.length > 0 && (
                <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                    <table className="si-data-table">
                        <thead>
                            <tr>
                                <th className="px-4 py-3 text-left">Key Name</th>
                                <th className="px-4 py-3 text-left">Requests</th>
                                <th className="px-4 py-3 text-left">Quota</th>
                                <th className="px-4 py-3 text-left">Last Used</th>
                                <th className="px-4 py-3 text-left">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {keys.map((key) => (
                                <tr key={key.key_id}>
                                    <td className="px-4 py-3 font-medium">{key.name}</td>
                                    <td className="px-4 py-3 font-mono text-xs">{(key.request_count || 0).toLocaleString()}</td>
                                    <td className="px-4 py-3 text-xs">{key.quota_limit || "Default"}/min</td>
                                    <td className="px-4 py-3 text-xs">
                                        {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}
                                    </td>
                                    <td className="px-4 py-3">
                                        {key.is_active ? (
                                            <span className="si-badge-success text-xs">Active</span>
                                        ) : (
                                            <span className="si-badge-danger text-xs">Revoked</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
