# Use the official Node.js runtime as a parent image
FROM node:24-alpine AS base

# Set the working directory in the container
WORKDIR /app

# Copy package files first (better cache utilization)
COPY package*.json ./

# Development stage
FROM base AS development
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Build stage
FROM base AS build
RUN npm ci
# Copy source code after installing dependencies (better cache)
COPY . .
RUN npm run build

# Production stage
FROM node:24-alpine AS production
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN npm ci --omit=dev && npm cache clean --force

# Copy built application from build stage
COPY --from=build /app/dist ./dist

# Create a simple ES module server script for SPA
RUN echo 'import http from "http"; import fs from "fs"; import path from "path"; import { fileURLToPath } from "url"; const __filename = fileURLToPath(import.meta.url); const __dirname = path.dirname(__filename); const server = http.createServer((req, res) => { let filePath = path.join(__dirname, "dist", req.url === "/" ? "index.html" : req.url); const ext = path.extname(filePath); const contentType = ext === ".html" ? "text/html" : ext === ".js" ? "text/javascript" : ext === ".css" ? "text/css" : "text/plain"; fs.readFile(filePath, (err, data) => { if (err) { fs.readFile(path.join(__dirname, "dist", "index.html"), (err, indexData) => { if (err) { res.writeHead(404); res.end("Not found"); } else { res.writeHead(200, {"Content-Type": "text/html"}); res.end(indexData); } }); } else { res.writeHead(200, {"Content-Type": contentType}); res.end(data); } }); }); server.listen(5173, "0.0.0.0", () => console.log("Server running on port 5173"));' > server.js

# Expose the port the app runs on
EXPOSE 5173

# Run the custom server
CMD ["node", "server.js"]
