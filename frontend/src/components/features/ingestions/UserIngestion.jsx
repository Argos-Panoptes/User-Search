import React, { useState } from "react";
import { GenericIngestionLayout } from "./IngestionComponents";

export default function UserIngestion() {
    const [currentJobId, setCurrentJobId] = useState(null);

    const handleJobStarted = (jobId) => {
        setCurrentJobId(jobId);
    };

    const handleSelectJob = (jobId, job) => {
        setCurrentJobId(jobId);
    };

    const config = {
        title: "User Ingestion",
        description: "Upload User SQL Dump (.sql)",
        fileLabel: "Upload SQL",
        supportedFormats: "Supported formats: .sql",
        directoryMode: false,
        multiple: false,
        accept: ".sql",
        dualManifest: false,
        chunked: true,
        sendJson: true, // Custom flag we will add support for
        endpoints: {
            uploadFile: "/ingest/users",
        }
    };

    const endpoints = {
        jobs: "/jobs/?ingestion_type=users,rollback", // Fixed path
        progress: "/jobs",
        logs: "/jobs", // Logs are fetching via /jobs/{id}/logs
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
