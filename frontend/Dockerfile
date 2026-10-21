FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy frontend source
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start Vite with --host so it's accessible outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
