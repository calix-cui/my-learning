# syntax=docker/dockerfile:1
# 前端镜像：先构建静态产物，再交给 nginx 托管，并把 /api 反代到后端容器。

# ---------- 构建层 ----------
FROM node:22-alpine AS build

# 包管理器来源可选：默认官方 npm registry，国内可换成镜像加速：
#   docker compose build --build-arg NPM_REGISTRY=https://registry.npmmirror.com frontend
ARG NPM_REGISTRY=https://registry.npmjs.org/
ENV npm_config_registry=${NPM_REGISTRY}

# 用 npm 直接装 pnpm：比 corepack 自带下载器稳（corepack 拉独立二进制超时只有几十秒，
# 慢速网络下容易 `Could not download the pnpm ... binary`）。版本与 package.json 的
# packageManager 字段保持一致，升级时两处一起改。
RUN npm install --global pnpm@12.10.1 \
      --no-fund --no-audit --fetch-retries=5 --fetch-timeout=600000

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --reporter=append-only

COPY . .
RUN pnpm build

# ---------- 运行层 ----------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
