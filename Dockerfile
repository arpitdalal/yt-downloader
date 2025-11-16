# Use Node.js 20 with Python 3.11
FROM node:20-slim

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install pnpm
RUN npm install -g pnpm

# Install Node.js dependencies
RUN pnpm install --frozen-lockfile

# Copy Python requirements and install Python dependencies
COPY python/requirements.txt ./python/
RUN pip3 install -r python/requirements.txt

# Copy Prisma schema
COPY prisma ./prisma

# Generate Prisma client
RUN pnpm db:generate

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Build the application
RUN pnpm build

# Expose port
EXPOSE 3000

# Start the application
CMD ["pnpm", "start"]