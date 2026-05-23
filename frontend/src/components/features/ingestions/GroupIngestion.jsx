import React, { useState } from "react";
import { GenericIngestionLayout } from "./IngestionComponents";

export default function GroupIngestion() {
    const [currentJobId, setCurrentJobId] = useState(null);

    const handleJobStarted = (jobId) => {
        setCurrentJobId(jobId);
    };

    const handleSelectJob = (jobId, job) => {
        setCurrentJobId(jobId);
    };

    const config = {
        title: "Group Ingestion",
        description: "Upload Group Excel/CSV File (.xlsx,.csv)",
        fileLabel: "Upload Excel/CSV",
        supportedFormats: "Supported formats: .xlsx,.csv",
        directoryMode: false,
        multiple: false,
        accept: ".xlsx,.csv",
        dualManifest: false,
        chunked: true,
        sendJson: true,
        endpoints: {
            uploadFile: "/ingest/groups",
        }
    };

    const endpoints = {
        jobs: "/jobs/?ingestion_type=groups,rollback",
        progress: "/jobs",
        logs: "/jobs",
        rollback: "/jobs"
    };

    return (
        <GenericIngestionLayout
            config={config}
            endpoints={endpoints}
            currentJobId={currentJobId}
            onSelectJob={handleSelectJob}
            onJobStarted={handleJobStarted}
        />
    );
}
