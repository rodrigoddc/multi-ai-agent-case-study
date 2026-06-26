# Langfuse Integration in Project

This document describes how Langfuse is integrated into the agent ecosystem and how it can be used for observability.

## Overview

Langfuse is integrated as a tracing and observability solution that provides insights into AI agent interactions, including:
- Trace collection from agents
- Prompt logging
- Token usage tracking
- Performance metrics
- Error monitoring

## Integration Points

The integration with the project occurs in several areas:

1. **Main Application**: The Langfuse client is initialized at application startup and configured through environment variables.
2. **Agent Operations**: All agent interactions are traced using Langfuse's instrumentation.
3. **Monitoring**: Traces and metrics are automatically collected and made available via the Langfuse dashboard.

## Configuration

The project expects these environment variables to be set for Langfuse:

- `LANGFUSE_PUBLIC_KEY` - Public key for authentication
- `LANGFUSE_SECRET_KEY` - Secret key for authentication
- `LANGFUSE_HOST` - Host URL for Langfuse API (defaults to production)
- `LANGFUSE_RELEASE` - Release version of your application

## Local Development Setup

For local development, use the Docker Compose setup:

1. Navigate to the container directory:
   ```bash
   cd ./infra/container
   ```

2. Start services using the helper script:
   ```bash
   ../scripts/langfuse-local.sh up
   ```

3. Access the dashboard at http://localhost:3000

## Production Deployment

In production, Langfuse is deployed via Kubernetes manifests located in:
- `./infra/k8s/apps/langfuse/`

Deploy with:
```bash
kubectl apply -f ./infra/k8s/apps/langfuse/
```
