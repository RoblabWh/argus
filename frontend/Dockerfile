# Base image
FROM node:20

# Set working directory
WORKDIR /frontend

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Expose port
EXPOSE 5173

# Start dev server
CMD ["npm", "run", "dev"]