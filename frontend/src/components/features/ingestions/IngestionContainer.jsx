import React, { useState } from "react";
import UserIngestion from "./UserIngestion";
import GroupIngestion from "./GroupIngestion";
import AvatarIngestion from "./AvatarIngestion";
import LinkReconstruction from "./LinkReconstruction";
import AvatarSync from "./AvatarSync";
import PageTabBar from "../../common/PageTabBar";
import { FaUser, FaUsers, FaImage, FaLink, FaSyncAlt } from "react-icons/fa";

const TABS = [
    { id: "users",       label: "Users",   shortLabel: "Users",   icon: FaUser },
    { id: "groups",      label: "Groups",  shortLabel: "Groups",  icon: FaUsers },
    { id: "avatars",     label: "Avatars", shortLabel: "Avatars", icon: FaImage },
    { id: "links",       label: "Links",   shortLabel: "Links",   icon: FaLink },
    { id: "avatar-sync", label: "Sync",    shortLabel: "Sync",    icon: FaSyncAlt },
];

export default function IngestionContainer() {
    const [activeTab, setActiveTab] = useState("users");

    const renderContent = () => {
        switch (activeTab) {
            case "users":       return <UserIngestion />;
            case "groups":      return <GroupIngestion />;
            case "avatars":     return <AvatarIngestion />;
            case "links":       return <LinkReconstruction />;
            case "avatar-sync": return <AvatarSync />;
            default:            return <UserIngestion />;
        }
    };

    return (
        <div className="m-4 md:m-[30px]">
            <PageTabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
            <div className="animate-fade-in pb-[60px] md:pb-0">
                {renderContent()}
            </div>
        </div>
    );
}
