# Base Stage for dependencies
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Development Stage
FROM base AS dev
COPY . ./
EXPOSE 80
CMD ["npm", "run", "dev", "--", "--host", "--port", "80"]

# Build Stage
FROM base AS build
ENV NODE_ENV=production
COPY . ./
RUN npm run build

# Production Stage
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
