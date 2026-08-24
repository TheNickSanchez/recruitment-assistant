# Recruitment Assistant chat UI (Next.js).
# NEXT_PUBLIC_API_URL is baked in at build time (Next.js client bundle).
# Use the host-reachable backend URL (default localhost:8000), not the
# Compose service hostname — the browser, not the frontend container, calls the API.
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3000"]
