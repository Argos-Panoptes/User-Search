# Build the React app
FROM node:24.12-alpine AS builder

WORKDIR /app

# Define ARGs for build time
ARG VITE_API_URL
ARG VITE_ENABLE_AUTH
ARG VITE_LOGOUT_URL
ARG VITE_CHECK_AUTH_URL
ARG VITE_LOGIN_URL

# Set them as ENV so they persist for the build process
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_ENABLE_AUTH=$VITE_ENABLE_AUTH
ENV VITE_LOGOUT_URL=$VITE_LOGOUT_URL
ENV VITE_CHECK_AUTH_URL=$VITE_CHECK_AUTH_URL
ENV VITE_LOGIN_URL=$VITE_LOGIN_URL

# Copy package.json
COPY package*.json ./
RUN npm install

# Copy the rest of the code
COPY . .
RUN npm run build

# Stage 2: Serve using Alpine for asset sharing
FROM alpine:latest
WORKDIR /app

# Copy built assets from builder stage
COPY --from=builder /app/dist /app/dist_stage

# On startup:
# 1. Clear the shared volume directory
# 2. Copy fresh build assets into it
# 3. Keeps the container alive so Nginx can access the volume
CMD ["/bin/sh", "-c", "rm -rf /usr/share/nginx/html/* && cp -r /app/dist_stage/* /usr/share/nginx/html/ && echo 'Frontend assets updated.' && tail -f /dev/null"]
