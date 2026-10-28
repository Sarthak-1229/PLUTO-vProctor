# Stage 1: Build React/Vite Frontend
FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Serve via Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx reverse proxy config for SPA and backend API forwarding
RUN echo 'server {' \
    '    listen 80;' \
    '    server_name localhost;' \
    '    location / {' \
    '        root /usr/share/nginx/html;' \
    '        index index.html index.htm;' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '    location /api/ {' \
    '        proxy_pass http://backend:8000/api/;' \
    '        proxy_set_header Host $host;' \
    '        proxy_set_header X-Real-IP $remote_addr;' \
    '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '        proxy_set_header X-Forwarded-Proto $scheme;' \
    '        client_max_body_size 500M;' \
    '    }' \
    '}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
