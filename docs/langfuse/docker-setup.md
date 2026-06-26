# Local Docker Setup for Langfuse

This document explains how to set up and run Langfuse locally using Docker Compose.

## Prerequisites

- Docker installed on your system
- Docker Compose v2 or higher

## Getting Started

1. **Navigate to the container directory:**
   ```bash
   cd ./infra/container
   ```

2. **Copy the example environment file (if needed):**
   ```bash
   cp .env.example .env
   ```

3. **Start all services:**
   ```bash
   docker-compose up -d
   ```

4. **Access the Langfuse dashboard:**
   Open your browser and go to:
   ```
   http://localhost:3000
   ```

## Services

The following services are included:

- `langfuse-web`: The main Langfuse web application (port 3000)
- `langfuse-worker`: Background worker processes
- `langfuse-postgres`: PostgreSQL database for trace data (port 5432)
- `langfuse-redis`: Redis instance for caching and queuing (port 6379)
- `langfuse-minio`: MinIO S3-compatible object storage (ports 9000, 9001)

## Stopping Services

To stop all services:
```bash
docker-compose down
```

To stop and remove data volumes:
```bash
docker-compose down -v
```

## Environment Variables

The `.env` file contains the default configuration. You can override these values by setting environment variables in your shell or modifying the `.env` file directly.

Key variables include:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`: PostgreSQL credentials
- `REDIS_PASSWORD`: Redis password
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: MinIO credentials

## Development Notes

For development purposes, you can modify the docker-compose.yml to use local volumes for persistent data storage and make it easier to debug issues.
