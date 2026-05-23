import React, { useState } from "react";
import { GenericIngestionLayout } from "./IngestionComponents";

export default function AvatarIngestion() {
    const [currentJobId, setCurrentJobId] = useState(null);

    const handleJobStarted = (jobId) => {
        setCurrentJobId(jobId);
    };

    const handleSelectJob = (jobId, job) => {
        setCurrentJobId(jobId);
    };

    const config = {
        title: "Avatar Ingestion",
        description: "Upload Avatar Manifest (.json) from S3",
        fileLabel: "Upload Manifest",
        supportedFormats: "Supported formats: .json",
        directoryMode: false,
        multiple: false,
        accept: ".json",
        dualManifest: false,
        chunked: true,
        sendJson: true,
        endpoints: {
            uploadFile: "/ingest/avatars",
        }
    };

    const endpoints = {
        jobs: "/jobs/?ingestion_type=avatars,rollback",
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
