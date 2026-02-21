# Multi-stage build for React SPA

# Stage 1: Build the React app
FROM node:20-alpine AS build
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source files and build
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx config will be copied by nginx Dockerfile
# (nginx service will be rebuilt to include this)

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
