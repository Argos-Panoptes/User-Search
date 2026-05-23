import { Hono } from "hono";
import { auth } from "./auth.js";
import { cors } from "hono/cors";
import { serve } from "@hono/node-server";

const app = new Hono();

app.use(
    "*",
    cors({
        origin: [process.env.FRONTEND_URL || "http://localhost:5173"],
        allowMethods: ["GET", "POST", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
        credentials: true,
    })
);

app.use("*", async (c, next) => {
    console.log(`[${new Date().toISOString()}] ${c.req.method} ${c.req.url}`);
    await next();
});

app.get("/health", async (c) => {
    console.log("Internal Health Check Request Received");
    try {
        const { db } = await import("./db.js");
        const { sql } = await import("drizzle-orm");
        await db.execute(sql`SELECT 1`);
        console.log("Health Check: DB Connection OK");
        return c.text("OK", 200);
    } catch (e) {
        console.error("Health Check Failed:", e);
        return c.text("Service Unavailable", 503);
    }
});

app.on(["POST", "GET"], "/api/auth/*", (c) => {
    return auth.handler(c.req.raw);
});

const port = 9000;
console.log(`Auth server running on http://localhost:${port}`);
console.log("Attempting to bind to 0.0.0.0");

serve({
    fetch: app.fetch,
    port,
    hostname: "0.0.0.0",
}, (info) => {
    console.log(`Listening on http://${info.address}:${info.port}`);
});
