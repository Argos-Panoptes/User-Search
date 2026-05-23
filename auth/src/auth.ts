import { betterAuth, APIError } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { magicLink } from "better-auth/plugins";
import { db } from "./db.js";
import { Resend } from "resend";
import * as schema from "./schema.js";
import * as dotenv from "dotenv";

dotenv.config();

const resend = new Resend(process.env.RESEND_API_KEY);

export const auth = betterAuth({
    database: drizzleAdapter(db, {
        provider: "pg",
        schema: schema,
    }),
    emailAndPassword: {
        enabled: false, // Using magic link only
    },
    plugins: [
        magicLink({
            sendMagicLink: async ({ email, url }) => {
                console.log(`Sending magic link to ${email}...`);
                try {
                    // Enforce server-side callback URL generation
                    const urlObj = new URL(url);
                    urlObj.searchParams.set("callbackURL", process.env.FRONTEND_URL + "/app/");
                    const secureUrl = urlObj.toString();
                    // console.log("Generated magic link URL:", secureUrl); // For development debugging

                    const { data, error } = await resend.emails.send({
                        // from: "Signal Intel <noreply@signal-users.com>",
                        from: "Signal Intel <onboarding@resend.dev>", // Using testing domain for now
                        to: email,
                        subject: "Sign in to Signal Intel",
                        html: `<p>Click the link below to sign in:</p><a href="${secureUrl}">${secureUrl}</a>`,
                    });

                    if (error) {
                        console.error("Resend error:", error);
                        throw new APIError("INTERNAL_SERVER_ERROR", { message: error.message });
                    } else {
                        console.log("Resend success:", data);
                    }
                } catch (err) {
                    console.error("Failed to send email:", err);
                    if (err instanceof APIError) throw err;
                    throw new APIError("INTERNAL_SERVER_ERROR", { message: err instanceof Error ? err.message : "Failed to send magic link" });
                }
            },
        }),
    ],
    hooks: {
        before: async (context) => {
            // Simplified logic: domain check can happen here
            // Note: Better Auth documentation suggests checking context.endpoint
            return;
        },
    },
    trustedOrigins: [process.env.FRONTEND_URL!],
    advanced: {
        cookiePrefix: "better-auth",
    }
});
