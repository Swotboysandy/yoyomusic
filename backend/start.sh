#!/bin/bash
set -e

# Run migrations
alembic upgrade head

# Start the application
uvicorn app.main:app --host 0.0.0.0 --port $PORT
