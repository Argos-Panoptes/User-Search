import React, { useState } from "react";
import DeleteUserForm from "./DeleteUserForm";
import AuditLogTable from "./AuditLogTable";
import AdminApiKeyManagement from "./AdminApiKeyManagement";
import MonitoringDashboard from "./MonitoringDashboard";
import AdminUserLimits from "./AdminUserLimits";
import PageTabBar from "../../common/PageTabBar";
import { FaUserSlash, FaClipboardList } from "react-icons/fa";
import { PiKeyBold, PiChartBarBold, PiSlidersHorizontalBold } from "react-icons/pi";

const TABS = [
    { id: "delete",     label: "Delete Users", shortLabel: "Delete",  icon: FaUserSlash },
    { id: "audit",      label: "Audit Log",    shortLabel: "Audit",   icon: FaClipboardList },
    { id: "apikeys",    label: "API Keys",     shortLabel: "Keys",    icon: PiKeyBold },
    { id: "userlimits", label: "User Limits",  shortLabel: "Limits",  icon: PiSlidersHorizontalBold },
    { id: "monitoring", label: "Monitoring",   shortLabel: "Monitor", icon: PiChartBarBold },
];

export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState("delete");

    const renderContent = () => {
        switch (activeTab) {
            case "delete":     return <DeleteUserForm />;
            case "audit":      return <AuditLogTable />;
            case "apikeys":    return <AdminApiKeyManagement />;
            case "userlimits": return <AdminUserLimits />;
            case "monitoring": return <MonitoringDashboard />;
            default:           return <DeleteUserForm />;
        }
    };

    return (
        <div className="flex flex-col h-full">
            <div className="px-4 md:px-6 pt-4 md:pt-6 flex-shrink-0">
                <PageTabBar
                    tabs={TABS}
                    activeTab={activeTab}
                    onChange={setActiveTab}
                />
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar pb-[60px] md:pb-0 px-4 md:px-6">
                {renderContent()}
            </div>
        </div>
    );
}
