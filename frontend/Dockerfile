FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 5173
CMD ["node","node_modules/vite/bin/vite.js","preview","--host","0.0.0.0","--port","5173","--strictPort"]
