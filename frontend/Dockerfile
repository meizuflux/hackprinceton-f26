FROM oven/bun:1.4.4 AS build

# The default build uses the live adapter at /api, which nginx proxies to the backend service
# (see nginx.conf and the root compose.yaml). For a standalone mock-only image:
#   docker build --build-arg VITE_API_BASE_URL=mock frontend
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run --bun build

FROM nginx:stable-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
