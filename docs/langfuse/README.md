# Langfuse Integration

This project integrates [Langfuse](https://langfuse.com/) for observability and tracing of AI agent interactions. Langfuse provides comprehensive logging, monitoring, and debugging capabilities for LLM-powered applications.

## Overview

Langfuse consists of several components:
- **Web UI**: The frontend dashboard for viewing traces and metrics
- **Worker**: Background processing for async operations
- **Database**: PostgreSQL for storing trace data
- **ClickHouse**: For fast analytics queries
- **MinIO**: Object storage for media files
- **Redis**: Caching and queueing

## Architecture

The system uses both Docker Compose for local development and Kubernetes for production deployments.

### Local Development (Docker Compose)

The following services run in Docker Compose:
- `langfuse-postgres`: PostgreSQL database (port 5432)
- `langfuse-redis`: Redis instance for caching and queuing (port 6379)
- `langfuse-minio`: MinIO S3-compatible object storage (ports 9000, 9001)
- `langfuse-clickhouse`: ClickHouse for analytics (ports 8123, 9000)
- `langfuse-web`: The main Langfuse web application (port 3000)
- `langfuse-worker`: Background worker processes

### Kubernetes Deployment

The system uses the following Kubernetes resources in `infra/k8s/apps/langfuse/`:
- `langfuse-postgres`: PostgreSQL database for storing traces and metrics
- `langfuse-clickhouse`: ClickHouse for analytics
- `langfuse-minio`: MinIO S3-compatible object storage
- `langfuse-redis`: Redis instance for caching and queuing
- `langfuse-deployment.yml`: The main Langfuse web application
- `langfuse-worker`: Background worker processes
- `langfuse-ingress.yml`: Ingress configuration for external access
- `langfuse-secrets.yml`: Kubernetes secrets for sensitive data

## Configuration

### Environment Variables

Key environment variables used in both deployments:
- `DATABASE_URL` - PostgreSQL connection string
- `SALT` - Salt for encryption
- `ENCRYPTION_KEY` - Encryption key for sensitive data
- `NEXTAUTH_SECRET` - NextAuth secret for authentication
- `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` - ClickHouse credentials
- `LANGFUSE_S3_*` - MinIO configuration for object storage
- `REDIS_HOST`, `REDIS_AUTH` - Redis connection details

### Secrets Management

#### Docker Compose
For local development, create a `.env` file in `infra/container/` using `.env.example` as a template:

```bash
cd infra/container
cp .env.example .env
# Edit .env with your desired configuration
```

#### Kubernetes
All sensitive information is stored in Kubernetes secrets:
- `langfuse-secrets`: Contains database passwords, encryption keys, and other sensitive data
- `langfuse-config`: Configuration parameters for Langfuse components

## Deployment

### Local Development Setup (Docker Compose)

#### Prerequisites
- Docker Desktop (includes Docker and Docker Compose)
- OR Docker Engine + Docker Compose CLI

#### Quick Start

1. **Navigate to the container directory:**
   ```bash
   cd infra/container
   ```

2. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Start all services:**
   ```bash
   docker compose up -d
   ```

4. **Wait for initialization (2-3 minutes):**
   ```bash
   docker compose logs -f langfuse-web
   ```
   Look for "Ready" message in the logs.

5. **Access the UI:**
   - **Langfuse Web**: http://localhost:3000
   - **MinIO Console**: http://localhost:9001 (user: minio, password: miniosecret)

#### Common Operations

**View logs:**
```bash
docker compose logs -f langfuse-web
docker compose logs -f langfuse-worker
```

**Stop services:**
```bash
docker compose down
```

**Stop and remove data:**
```bash
docker compose down -v
```

**Restart a specific service:**
```bash
docker compose restart langfuse-web
```

**Check service health:**
```bash
docker compose ps
```

### Production Deployment (Kubernetes)

The system can be deployed using the provided Kubernetes manifests:

```bash
# Create namespace
kubectl create namespace langfuse

# Apply all Langfuse manifests
kubectl apply -f infra/k8s/apps/langfuse/

# Or deploy via Helm (recommended for production)
helm repo add langfuse https://langfuse.github.io/langfuse-k8s
helm repo update
helm install langfuse langfuse/langfuse -n langfuse -f values.yaml
```

For detailed Kubernetes deployment instructions, refer to the [Kubernetes Helm deployment guide](https://langfuse.com/self-hosting/deployment/kubernetes-helm).

## Usage

Once deployed, Langfuse will automatically start collecting traces from your AI agents and applications. You can access the dashboard at:

- **Local**: http://localhost:3000
- **Production**: https://your-domain.com/langfuse (depending on ingress configuration)

### Dashboard Features

The Langfuse dashboard provides:
- **Traces and Spans**: Detailed view of agent interactions and LLM calls
- **Performance Metrics**: Latency, token usage, and cost analysis
- **Error Tracking**: Monitor failures and issues in your agents
- **Prompt Logging**: Track and version your prompts
- **Token Usage Statistics**: Monitor and optimize token consumption
- **Batch Evaluation**: Run evaluations on traces

## Integration with FastAPI

The FastAPI application integrates with Langfuse through the LLM Adapter. For detailed configuration, see [LLM_ADAPTER_GUIDE.md](./LLM_ADAPTER_GUIDE.md).

### Basic Setup

1. Install Langfuse SDK:
   ```bash
   pip install langfuse
   ```

2. Configure in your FastAPI application:
   ```python
   from langfuse.openai import OpenAI

   client = OpenAI(api_key="your-key")  # Uses LANGFUSE_* env vars
   ```

## Troubleshooting

### Docker Compose Issues

**Containers stuck initializing:**
```bash
# Check service logs
docker compose logs langfuse-postgres
docker compose logs langfuse-clickhouse

# Restart the service
docker compose restart langfuse-web
```

**Database connection errors:**
- Ensure PostgreSQL is healthy: `docker compose ps`
- Check network: `docker network ls`
- Verify DATABASE_URL in .env file

**Multimodal tracing not working:**
- MinIO might not be accessible from outside Docker network
- See [blob storage guide](https://langfuse.com/self-hosting/deployment/infrastructure/blobstorage#minio-media-uploads)

**Port conflicts:**
- If ports are in use, modify port mappings in docker-compose.yml
- Or use environment variables: `POSTGRES_PORT=5433` etc.

### Kubernetes Issues

For Kubernetes-specific troubleshooting:

```bash
# Check pod status
kubectl get pods -n langfuse

# View pod logs
kubectl logs -n langfuse deployment/langfuse-web

# Describe pod for events
kubectl describe pod -n langfuse <pod-name>

# Check service endpoints
kubectl get svc -n langfuse
```

## Health Checks

### Docker Compose

Services include health checks. Verify all are healthy:

```bash
docker compose ps
# All services should show "healthy" status
```

### Kubernetes

```bash
# Check endpoint readiness
kubectl get endpoints -n langfuse

# Check pod readiness
kubectl get pods -n langfuse
```

## Upgrade

### Docker Compose

```bash
cd infra/container
docker compose pull
docker compose up -d
```

### Kubernetes

```bash
helm repo update
helm upgrade langfuse langfuse/langfuse -n langfuse
```

For details on upgrading from previous versions, see [the upgrade guide](https://langfuse.com/self-hosting/upgrade).

## Documentation

- **Langfuse Official Docs**: https://langfuse.com/docs
- **Self-Hosting Guide**: https://langfuse.com/self-hosting
- **Docker Compose Deployment**: https://langfuse.com/self-hosting/deployment/docker-compose
- **Kubernetes Deployment**: https://langfuse.com/self-hosting/deployment/kubernetes-helm
- **Configuration Reference**: https://langfuse.com/self-hosting/configuration
