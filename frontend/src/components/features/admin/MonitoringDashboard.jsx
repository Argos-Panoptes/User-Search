import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
    fetchMonitoringStats,
    fetchKeyUsageStats,
    fetchSystemHealth,
    fetchEndpointUsage,
    fetchUsageTimeline,
    fetchKeyDetailUsage,
    setTimeRange,
    setSelectedKeyId,
    clearKeyDetail,
} from "../../../store/slices/monitoringSlice";
import {
    PiKeyBold,
    PiLightningBold,
    PiChartBarBold,
    PiUsersThreeBold,
    PiCheckCircleBold,
    PiXCircleBold,
    PiWarningBold,
    PiArrowClockwiseBold,
    PiClockBold,
    PiTimerBold,
    PiChartLineBold,
    PiXBold,
    PiFunnelBold,
} from "react-icons/pi";
import {
    AreaChart,
    Area,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

const TIME_RANGES = [
    { value: "1h", label: "1H" },
    { value: "24h", label: "24H" },
    { value: "7d", label: "7D" },
    { value: "30d", label: "30D" },
];

const STAT_COLOR_MAP = {
    electric: { color: 'var(--accent)', bg: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: 'color-mix(in srgb, var(--accent) 20%, transparent)' },
    emerald: { color: 'var(--success)', bg: 'var(--success-bg)', border: 'color-mix(in srgb, var(--success) 20%, transparent)' },
    amber: { color: 'var(--warning)', bg: 'var(--warning-bg)', border: 'color-mix(in srgb, var(--warning) 20%, transparent)' },
    blue: { color: 'var(--accent)', bg: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: 'color-mix(in srgb, var(--accent) 20%, transparent)' },
    red: { color: 'var(--danger)', bg: 'var(--danger-bg)', border: 'color-mix(in srgb, var(--danger) 20%, transparent)' },
    purple: { color: 'var(--accent)', bg: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: 'color-mix(in srgb, var(--accent) 20%, transparent)' },
};

function StatCard({ icon: Icon, label, value, sub, color = "electric" }) {
    const colors = STAT_COLOR_MAP[color] || STAT_COLOR_MAP.electric;

    return (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg" style={{ color: colors.color, background: colors.bg, border: `1px solid ${colors.border}` }}>
                    <Icon className="text-lg" />
                </div>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
            </div>
            <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value ?? "\u2014"}</div>
            {sub && <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{sub}</p>}
        </div>
    );
}

function HealthBadge({ status }) {
    if (!status) return <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Unknown</span>;
    const isOk = status === "ok" || (typeof status === "object" && ["green", "yellow"].includes(status?.status));
    const isNotConfigured = status === "not configured";
    if (isNotConfigured) return <span className="inline-flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}><PiWarningBold /> Not configured</span>;
    if (isOk) return <span className="inline-flex items-center gap-1 text-xs" style={{ color: 'var(--success)' }}><PiCheckCircleBold /> Connected</span>;
    return <span className="inline-flex items-center gap-1 text-xs" style={{ color: 'var(--danger)' }}><PiXCircleBold /> {typeof status === "string" ? status : "Error"}</span>;
}

function CustomTooltip({ active, payload, label, formatter }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="rounded-lg px-3 py-2 shadow-xl text-xs" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <p className="mb-1" style={{ color: 'var(--text-secondary)' }}>{formatter ? formatter(label) : label}</p>
            {payload.map((entry, i) => (
                <p key={i} style={{ color: 'var(--text-primary)' }}>
                    <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: entry.color }} />
                    {entry.name}: <span className="font-medium">{entry.value?.toLocaleString()}</span>
                </p>
            ))}
        </div>
    );
}

function formatBucketLabel(bucket, timeRange) {
    if (!bucket) return "";
    const d = new Date(bucket);
    if (timeRange === "1h" || timeRange === "24h") {
        return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
    }
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function shortenEndpoint(ep) {
    return ep?.replace(/^\/v1\/public/, "").replace(/^\/v1/, "") || ep;
}

export default function MonitoringDashboard() {
    const dispatch = useDispatch();
    const {
        stats, keyUsage, health, endpointUsage, timeline,
        keyDetail, timeRange, selectedKeyId, loading,
    } = useSelector((s) => s.monitoring);
    const [showKeyDetail, setShowKeyDetail] = useState(false);

    const loadAll = () => {
        dispatch(fetchMonitoringStats());
        dispatch(fetchKeyUsageStats());
        dispatch(fetchSystemHealth());
        dispatch(fetchEndpointUsage({ time_range: timeRange, api_key_id: selectedKeyId || undefined }));
        dispatch(fetchUsageTimeline({ time_range: timeRange, api_key_id: selectedKeyId || undefined }));
    };

    useEffect(() => {
        loadAll();
    }, [timeRange, selectedKeyId]);

    const handleTimeRange = (range) => {
        dispatch(setTimeRange(range));
    };

    const handleKeyFilter = (e) => {
        const val = e.target.value || null;
        dispatch(setSelectedKeyId(val));
    };

    const handleKeyDrillDown = (keyId) => {
        dispatch(fetchKeyDetailUsage({ keyId, params: { time_range: timeRange } }));
        setShowKeyDetail(true);
    };

    const closeKeyDetail = () => {
        setShowKeyDetail(false);
        dispatch(clearKeyDetail());
    };

    if (loading && !stats) {
        return (
            <div className="space-y-6">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className="rounded-lg p-4 animate-pulse" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                            <div className="h-4 rounded w-24 mb-3" style={{ background: 'var(--bg-card)' }} />
                            <div className="h-8 rounded w-16" style={{ background: 'var(--bg-card)' }} />
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    const maxRequests = Math.max(...(keyUsage || []).map(k => k.request_count || 0), 1);
    const timelineData = (timeline || []).map(t => ({
        ...t,
        label: formatBucketLabel(t.bucket, timeRange),
    }));

    return (
        <div className="space-y-6">
            {/* Header with controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>System Monitoring</h3>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>API usage and system health overview</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {/* Key filter */}
                    {keyUsage && keyUsage.length > 0 && (
                        <div className="relative">
                            {/* <PiFunnelBold className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm" style={{ color: 'var(--text-tertiary)' }} /> */}
                            <select
                                value={selectedKeyId || ""}
                                onChange={handleKeyFilter}
                                className="si-select pl-8 pr-3 py-1.5 text-sm appearance-none cursor-pointer min-w-[140px]"
                            >
                                <option value="">All Keys</option>
                                {keyUsage.map(k => (
                                    <option key={k.key_id} value={k.key_id}>{k.name}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    {/* Time range */}
                    <div className="flex items-center rounded-lg overflow-hidden flex-shrink-0" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        {TIME_RANGES.map(r => (
                            <button
                                key={r.value}
                                onClick={() => handleTimeRange(r.value)}
                                className="px-3 py-1.5 text-xs font-medium transition-colors"
                                style={{
                                    background: timeRange === r.value ? 'var(--accent)' : 'transparent',
                                    color: timeRange === r.value ? 'var(--text-primary)' : 'var(--text-secondary)',
                                }}
                                onMouseEnter={(e) => { if (timeRange !== r.value) { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; } }}
                                onMouseLeave={(e) => { if (timeRange !== r.value) { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'transparent'; } }}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>

                    {/* Refresh */}
                    <button
                        onClick={loadAll}
                        className="si-button-secondary flex items-center gap-2"
                    >
                        <PiArrowClockwiseBold /> Refresh
                    </button>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <StatCard icon={PiKeyBold} label="Total API Keys" value={stats?.total_api_keys?.toLocaleString()} color="electric" />
                <StatCard icon={PiLightningBold} label="Active Keys" value={stats?.active_api_keys?.toLocaleString()} color="emerald" />
                <StatCard icon={PiChartBarBold} label="Total Requests" value={stats?.total_api_requests?.toLocaleString()} color="amber" />
                <StatCard icon={PiClockBold} label="Today's Requests" value={stats?.today_requests?.toLocaleString()} color="blue" />
                <StatCard
                    icon={PiTimerBold}
                    label="Avg Response"
                    value={stats?.avg_response_time_ms != null ? `${stats.avg_response_time_ms}ms` : "\u2014"}
                    sub="Today"
                    color="purple"
                />
                <StatCard
                    icon={PiXCircleBold}
                    label="Errors Today"
                    value={stats?.today_errors?.toLocaleString()}
                    sub={stats?.today_requests > 0
                        ? `${((stats.today_errors / stats.today_requests) * 100).toFixed(1)}% rate`
                        : null}
                    color="red"
                />
            </div>

            {/* Request Timeline Chart */}
            {timelineData.length > 0 && (
                <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <PiChartLineBold style={{ color: 'var(--accent)' }} />
                            <h4 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Request Volume</h4>
                        </div>
                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                            {timeRange === "1h" || timeRange === "24h" ? "Hourly" : "Daily"} breakdown
                        </span>
                    </div>
                    <ResponsiveContainer width="100%" height={240}>
                        <AreaChart data={timelineData}>
                            <defs>
                                <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="colorErrors" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis
                                dataKey="label"
                                tick={{ fontSize: 11, fill: "#94a3b8" }}
                                tickLine={false}
                                axisLine={{ stroke: "#334155" }}
                            />
                            <YAxis
                                tick={{ fontSize: 11, fill: "#94a3b8" }}
                                tickLine={false}
                                axisLine={false}
                                width={40}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Area
                                type="monotone"
                                dataKey="request_count"
                                name="Requests"
                                stroke="#6366f1"
                                strokeWidth={2}
                                fill="url(#colorRequests)"
                            />
                            <Area
                                type="monotone"
                                dataKey="error_count"
                                name="Errors"
                                stroke="#ef4444"
                                strokeWidth={1.5}
                                fill="url(#colorErrors)"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}

            {/* Top Endpoints */}
            {endpointUsage && endpointUsage.length > 0 && (
                <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                    <h4 className="text-sm font-medium mb-4" style={{ color: 'var(--text-primary)' }}>Top Endpoints</h4>
                    <div className="overflow-x-auto">
                        <table className="si-data-table w-full text-sm">
                            <thead>
                                <tr>
                                    <th className="pb-2 font-medium">#</th>
                                    <th className="pb-2 font-medium">Method</th>
                                    <th className="pb-2 font-medium">Endpoint</th>
                                    <th className="pb-2 font-medium text-right">Hits</th>
                                    <th className="pb-2 font-medium text-right">Avg Time</th>
                                    <th className="pb-2 font-medium text-right">Errors</th>
                                    <th className="pb-2 font-medium pl-4 w-1/3"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {endpointUsage.map((ep, i) => {
                                    const maxHits = endpointUsage[0]?.hit_count || 1;
                                    const methodStyle = ep.method === "GET"
                                        ? { background: 'var(--success-bg)', color: 'var(--success)' }
                                        : ep.method === "POST"
                                            ? { background: 'color-mix(in srgb, var(--accent) 10%, transparent)', color: 'var(--accent)' }
                                            : { background: 'var(--warning-bg)', color: 'var(--warning)' };
                                    return (
                                        <tr key={`${ep.method}-${ep.endpoint}`}>
                                            <td className="py-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>{i + 1}</td>
                                            <td className="py-2">
                                                <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={methodStyle}>
                                                    {ep.method}
                                                </span>
                                            </td>
                                            <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-primary)' }} title={ep.endpoint}>
                                                {shortenEndpoint(ep.endpoint)}
                                            </td>
                                            <td className="py-2 text-right font-mono text-xs">{ep.hit_count.toLocaleString()}</td>
                                            <td className="py-2 text-right text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                {ep.avg_response_ms != null ? `${ep.avg_response_ms}ms` : "\u2014"}
                                            </td>
                                            <td className="py-2 text-right text-xs">
                                                <span style={{ color: ep.error_count > 0 ? 'var(--danger)' : 'var(--text-tertiary)' }}>
                                                    {ep.error_count}
                                                </span>
                                            </td>
                                            <td className="py-2 pl-4">
                                                <div className="w-full rounded-full h-1.5" style={{ background: 'var(--bg-card)' }}>
                                                    <div
                                                        className="rounded-full h-1.5 transition-all"
                                                        style={{ width: `${Math.max((ep.hit_count / maxHits) * 100, 2)}%`, background: 'color-mix(in srgb, var(--accent) 60%, transparent)' }}
                                                    />
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* System Health */}
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                <div className="flex items-center justify-between mb-4">
                    <h4 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>System Health</h4>
                    {health && (
                        <span
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
                            style={
                                health.status === "healthy"
                                    ? { background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid color-mix(in srgb, var(--success) 20%, transparent)' }
                                    : { background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid color-mix(in srgb, var(--warning) 20%, transparent)' }
                            }
                        >
                            {health.status === "healthy" ? <PiCheckCircleBold /> : <PiWarningBold />}
                            {health.status === "healthy" ? "All Systems Operational" : "Degraded"}
                        </span>
                    )}
                </div>
                {health?.components ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        {Object.entries(health.components).map(([name, status]) => (
                            <div key={name} className="rounded-lg p-3" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                <p className="text-xs uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-secondary)' }}>{name}</p>
                                <HealthBadge status={status} />
                                {typeof status === "object" && status?.status && (
                                    <p className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                                        Cluster: {status.status} | Nodes: {status.number_of_nodes}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Health data unavailable</p>
                )}
            </div>

            {/* Top Keys by Usage */}
            {keyUsage && keyUsage.length > 0 && (
                <div className="rounded-lg p-4" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                    <h4 className="text-sm font-medium mb-4" style={{ color: 'var(--text-primary)' }}>Top API Keys by Request Count</h4>
                    <div className="space-y-2">
                        {keyUsage.map((key, i) => (
                            <button
                                key={key.key_id}
                                onClick={() => handleKeyDrillDown(key.key_id)}
                                className="w-full flex items-center gap-3 rounded-lg px-2 py-1 transition-colors group text-left"
                                onMouseEnter={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--bg-card) 50%, transparent)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                                <span className="text-xs w-5 text-right" style={{ color: 'var(--text-tertiary)' }}>{i + 1}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm truncate transition-colors" style={{ color: 'var(--text-primary)' }}>{key.name}</span>
                                        <span className="text-xs font-mono ml-2" style={{ color: 'var(--text-secondary)' }}>{(key.request_count || 0).toLocaleString()}</span>
                                    </div>
                                    <div className="w-full rounded-full h-1.5" style={{ background: 'var(--bg-card)' }}>
                                        <div
                                            className="rounded-full h-1.5 transition-all"
                                            style={{ width: `${Math.max(((key.request_count || 0) / maxRequests) * 100, 1)}%`, background: 'color-mix(in srgb, var(--accent) 60%, transparent)' }}
                                        />
                                    </div>
                                </div>
                                <span className="text-xs font-mono w-16 text-right" style={{ color: 'var(--text-tertiary)' }}>{key.quota_limit || "\u2014"}/min</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Key Detail Drill-Down Modal */}
            {showKeyDetail && keyDetail && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/60" onClick={closeKeyDetail} />
                    <div className="relative rounded-xl w-full max-w-2xl shadow-2xl max-h-[85vh] overflow-y-auto" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="sticky top-0 flex items-center justify-between px-6 py-4 z-10" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                            <div>
                                <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{keyDetail.name}</h3>
                                <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{keyDetail.key_id}</span>
                            </div>
                            <button onClick={closeKeyDetail} className="si-icon-button"><PiXBold /></button>
                        </div>
                        <div className="p-6 space-y-6">
                            {/* Key Stats */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div className="rounded-lg p-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                    <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>All-Time Requests</p>
                                    <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{(keyDetail.total_requests_all_time || 0).toLocaleString()}</p>
                                </div>
                                <div className="rounded-lg p-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                    <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>In Range</p>
                                    <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{(keyDetail.requests_in_range || 0).toLocaleString()}</p>
                                </div>
                                <div className="rounded-lg p-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                    <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Avg Response</p>
                                    <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{keyDetail.avg_response_ms != null ? `${keyDetail.avg_response_ms}ms` : "\u2014"}</p>
                                </div>
                                <div className="rounded-lg p-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                    <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Error Rate</p>
                                    <p className="text-lg font-bold" style={{ color: keyDetail.error_rate > 5 ? 'var(--danger)' : 'var(--text-primary)' }}>
                                        {keyDetail.error_rate != null ? `${keyDetail.error_rate}%` : "\u2014"}
                                    </p>
                                </div>
                            </div>

                            {/* Key Timeline */}
                            {keyDetail.timeline && keyDetail.timeline.length > 0 && (
                                <div>
                                    <h4 className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>Request Timeline</h4>
                                    <ResponsiveContainer width="100%" height={180}>
                                        <AreaChart data={keyDetail.timeline.map(t => ({
                                            ...t,
                                            label: formatBucketLabel(t.bucket, timeRange),
                                        }))}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={{ stroke: "#334155" }} />
                                            <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} width={35} />
                                            <Tooltip content={<CustomTooltip />} />
                                            <Area type="monotone" dataKey="request_count" name="Requests" stroke="#6366f1" strokeWidth={2} fill="url(#colorRequests)" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            )}

                            {/* Key Top Endpoints */}
                            {keyDetail.top_endpoints && keyDetail.top_endpoints.length > 0 && (
                                <div>
                                    <h4 className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>Top Endpoints</h4>
                                    <div className="space-y-2">
                                        {keyDetail.top_endpoints.map((ep, i) => {
                                            const maxHits = keyDetail.top_endpoints[0]?.hit_count || 1;
                                            return (
                                                <div key={ep.endpoint} className="flex items-center gap-3">
                                                    <span className="text-xs w-4 text-right" style={{ color: 'var(--text-tertiary)' }}>{i + 1}</span>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <span className="text-xs font-mono truncate" style={{ color: 'var(--text-primary)' }}>{shortenEndpoint(ep.endpoint)}</span>
                                                            <span className="text-xs font-mono ml-2" style={{ color: 'var(--text-secondary)' }}>{ep.hit_count.toLocaleString()}</span>
                                                        </div>
                                                        <div className="w-full rounded-full h-1" style={{ background: 'var(--bg-card)' }}>
                                                            <div
                                                                className="rounded-full h-1 transition-all"
                                                                style={{ width: `${Math.max((ep.hit_count / maxHits) * 100, 2)}%`, background: 'color-mix(in srgb, var(--accent) 60%, transparent)' }}
                                                            />
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {keyDetail.requests_in_range === 0 && (
                                <p className="text-sm text-center py-4" style={{ color: 'var(--text-tertiary)' }}>No requests recorded in the selected time range.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
