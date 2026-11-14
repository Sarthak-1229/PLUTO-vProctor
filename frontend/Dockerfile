# Stage 1: Build React/Vite Frontend
FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Serve via Hardened Nginx
FROM nginx:alpine

# Remove default nginx config and replace with custom production config
RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled SPA static assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/index.html > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
