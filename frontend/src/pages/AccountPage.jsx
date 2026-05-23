import React, { useState } from "react";
import { PiKeyBold, PiChartBarBold, PiBookOpenBold } from "react-icons/pi";
import { API_DOCS_URL } from "../config";
import ApiKeyList from "../components/features/apikeys/ApiKeyList";
import UsageStatsPanel from "../components/features/apikeys/UsageStatsPanel";
import PageTabBar from "../components/common/PageTabBar";
import { useAuth } from "../context/AuthContext";

const ALL_TABS = [
    { id: "keys", label: "API Keys", icon: PiKeyBold, adminOnly: true },
    { id: "usage", label: "Usage Stats", shortLabel: "Usage", icon: PiChartBarBold },
];

export default function AccountPage() {
    const { user } = useAuth();
    const isAdmin = user?.is_superuser;
    const TABS = ALL_TABS.filter(t => !t.adminOnly || isAdmin);
    const [activeTab, setActiveTab] = useState(() => TABS[0]?.id ?? "usage");

    return (
        <div className="flex flex-col min-h-full px-4 md:px-6 py-4 md:py-6">
            <PageTabBar
                tabs={TABS}
                activeTab={activeTab}
                onChange={setActiveTab}
                actions={
                    <a
                        href={API_DOCS_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="si-button-secondary flex items-center gap-2"
                    >
                        <PiBookOpenBold /> API Docs
                    </a>
                }
            />

            <div className="flex-1 overflow-y-auto custom-scrollbar pb-[60px] md:pb-0">
                {activeTab === "keys" && <ApiKeyList />}
                {activeTab === "usage" && <UsageStatsPanel />}
            </div>
        </div>
    );
}
