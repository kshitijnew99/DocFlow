# Deploy DocFlow To Render

This repository now includes a Render Blueprint at render.yaml for a one-click multi-service deploy.

## Why this setup

DocFlow stores uploaded files on local disk before Celery processes them. On Render, separate services do not share filesystem state. To keep processing reliable without refactoring storage to S3/GCS, the backend and Celery worker run in the same Render web service via backend/start_render.sh.

## Services created by render.yaml

- docflow-backend (Python web service)
- docflow-frontend (Node web service)
- docflow-redis (Render Key Value)
- docflow-postgres (Render Postgres)

## Deploy steps

1. Push this code to GitHub/GitLab.
2. In Render Dashboard, open Blueprints and create a New Blueprint Instance.
3. Connect your repo and deploy.
4. Render will prompt for variables marked with sync: false:
   - CORS_ORIGINS
   - NEXT_PUBLIC_API_URL

Use these values (replace service names if yours differ):

- CORS_ORIGINS = https://docflow-frontend.onrender.com
- NEXT_PUBLIC_API_URL = https://docflow-backend.onrender.com

If you use a custom domain later, update both values accordingly.

## Post-deploy checks

- Backend health: https://docflow-backend.onrender.com/api/v1/health
- Backend docs: https://docflow-backend.onrender.com/docs
- Frontend: https://docflow-frontend.onrender.com

## Optional Clerk env vars (when auth is integrated)

Frontend service:
- NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

Backend service:
- CLERK_SECRET_KEY

## Notes

- Uploaded files are stored on a persistent disk mounted at /opt/render/project/src/backend/uploads.
- If you want to scale worker independently, migrate file storage to object storage (S3/GCS/R2) and run worker as a separate Render background worker service.
