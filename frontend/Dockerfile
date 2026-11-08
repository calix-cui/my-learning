# syntax=docker/dockerfile:1
# 前端镜像：先构建静态产物，再交给 nginx 托管，并把 /api 反代到后端容器。

# ---------- 构建层 ----------
FROM node:22-alpine AS build

# corepack 会按 package.json 的 packageManager 字段拉取 pnpm 12.10.1
RUN corepack enable

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# ---------- 运行层 ----------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
