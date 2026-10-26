FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:26-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN npm run build

FROM node:26-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S saasta && adduser -S saasta -G saasta
COPY --from=build --chown=saasta:saasta /app/.next/standalone ./
COPY --from=build --chown=saasta:saasta /app/.next/static ./.next/static
COPY --from=build --chown=saasta:saasta /app/public ./public
USER saasta
EXPOSE 3000
CMD ["node", "server.js"]
