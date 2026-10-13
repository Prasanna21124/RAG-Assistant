FROM node:18-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

# Build the React app (optional for dev, required for prod, but we will use dev mode for simplicity here so it auto-reloads)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
