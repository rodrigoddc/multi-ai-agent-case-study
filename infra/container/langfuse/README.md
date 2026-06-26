# Langfuse Container Setup

This directory contains the Docker Compose configuration for running Langfuse locally for development and evaluation.

## Quick Start

### 1. Prepare Environment Variables

Copy the example environment file:

```bash
cp ../../.env.langfuse.example ../../.env.langfuse
```

Edit `../../.env.langfuse` if you need to change any defaults (optional for local dev).

### 2. Start Langfuse Stack

From the `infra/container/langfuse` directory:

```bash
docker compose --env-file ../../.env.langfuse up -d
```

Or from the project root:

```bash
docker compose -f infra/container/langfuse/docker-compose.yml --env-file .env.langfuse up -d
```

### 3. Wait for Services to Be Healthy

Monitor the container startup:

```bash
docker compose -f infra/container/langfuse/docker-compose.yml logs -f
```

Watch for "Ready" message from `langfuse-web-1` container (typically 2-3 minutes).

### 4. Access Langfuse

Open http://localhost:3000 in your browser.

### 5. Stop Langfuse Stack

```bash
docker compose -f infra/container/langfuse/docker-compose.yml down
```

To also remove persistent volumes:

```bash
docker compose -f infra/container/langfuse/docker-compose.yml down -v
```

## Services

The Langfuse stack includes:

- **langfuse-web**: Main Langfuse web application (port 3000)
- **langfuse-worker**: Background job processor
- **langfuse-postgres**: PostgreSQL database
- **langfuse-redis**: Redis cache and message queue
- **langfuse-clickhouse**: ClickHouse analytics database
- **langfuse-minio**: MinIO object storage (S3-compatible)

## Integration with FastAPI App

The Langfuse stack is **completely separate** from the FastAPI app stack:

- **FastAPI App**: `infra/container/docker-compose.yml` - Contains FastAPI, PgBouncer, and PostgreSQL for the hotels app
- **Langfuse Stack**: `infra/container/langfuse/docker-compose.yml` - Contains all Langfuse services

Both can run simultaneously on the same host without conflicts.

### Configure FastAPI App to Use Langfuse

In your `.env` file for the FastAPI app, set:

```env
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=http://localhost:3000
```

To create these keys in Langfuse:
1. Access http://localhost:3000
2. Go to Settings → API Keys
3. Create a new API key
4. Use the provided keys in your `.env`

## Environment Configuration

All services use environment variables from `.env.langfuse`:

- `LANGFUSE_POSTGRES_USER/PASSWORD`: Database credentials
- `LANGFUSE_REDIS_PASSWORD`: Redis authentication
- `LANGFUSE_CLICKHOUSE_USER/PASSWORD`: ClickHouse credentials
- `LANGFUSE_MINIO_ROOT_USER/PASSWORD`: MinIO credentials
- `LANGFUSE_ENCRYPTION_KEY`: Encryption for sensitive data
- `LANGFUSE_SALT`: Salt for password hashing
- `LANGFUSE_NEXTAUTH_SECRET`: NextAuth.js session encryption

**IMPORTANT**: Change these secrets in production!

## Troubleshooting

### Services won't start

Check logs:
```bash
docker compose -f infra/container/langfuse/docker-compose.yml logs
```

### Database connection errors

Ensure PostgreSQL is healthy:
```bash
docker compose -f infra/container/langfuse/docker-compose.yml exec langfuse-postgres pg_isready -U postgres
```

### Multimodal tracing not working

MinIO is configured for local network access only. For external uploads, configure MinIO endpoint in `.env.langfuse`.

### Port 3000 already in use

Either stop other services using port 3000 or modify the port in `docker-compose.yml`:
```yaml
ports:
  - "127.0.0.1:3001:3000"  # Changed from 3000 to 3001
```

## References

- [Langfuse Docker Compose Docs](https://langfuse.com/self-hosting/deployment/docker-compose)
- [Langfuse Configuration Guide](https://langfuse.com/self-hosting/configuration)
- [Langfuse API Reference](https://langfuse.com/docs/api-and-data-platform/overview)
