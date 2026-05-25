# ── QueryMind Frontend Dockerfile (React 

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci


COPY . .

ARG VITE_API_URL=http://localhost:8000
ARG VITE_WS_URL=ws://localhost:8000

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

RUN npx vite build

FROM nginx:alpine AS runtime

RUN apk add --no-cache curl

 
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]