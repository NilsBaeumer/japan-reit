# Stage 1: Build the React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our nginx config
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx.conf is mounted via docker-compose from /nginx/nginx.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
