# Configuration Guide

## Overview

This application uses multiple configuration files for different deployment environments.

## Configuration Files

### `app.yaml` (Primary Development Config)
**Runtime**: Python 3.11  
**Project**: `cloudtasks-app-473120`  
**Environment**: Development  
**Purpose**: Local development and testing

**Key Settings**:
- Uses Python 3.11
- Minimal scaling (1-2 instances)
- Development secret keys
- All environment variables defined

**Usage**: `gcloud app deploy app.yaml`

### `config/development.yaml` (Legacy Development Config)
**Runtime**: Python 3.9  
**Project**: `crucial-haiku-473123-r7`  
**Environment**: Development (Legacy)  
**Purpose**: Older development environment

**Key Settings**:
- Uses Python 3.9
- Limited scaling (1-3 instances)
- Minimal environment variables

**Usage**: `gcloud app deploy config/development.yaml`

**Note**: This appears to be an older development configuration. Consider consolidating with `app.yaml`.

### `app.production.yaml` (Production Config)
**Runtime**: Python 3.11  
**Project**: `cloudtasks-app-473120`  
**Environment**: Production  
**Purpose**: Production deployment (`python app.py --deploy` uses this file when present)

**Key Settings**:
- Uses Python 3.11
- `min_instances: 1` (one warm instance)
- `max_instances: 2`
- flask-base auth keys: `CT_KEY_*` (same format as `app.yaml`)

**Usage**: `gcloud app deploy app.production.yaml` or `.venv\Scripts\python.exe app.py --deploy`

## Environment Variables

### Required Variables

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
FLASK_SECRET=your-flask-secret-key
ADMIN_KEY=your-admin-key
FLASK_BASE_KEY_PREFIX=CT_KEY_
OPENAI_API_KEY=your-openai-api-key
```

### User Authentication (flask-base)

```bash
FLASK_BASE_KEY_PREFIX=CT_KEY_
CT_KEY_IAN=user1-secret-key
CT_KEY_KARLEIGH=user2-secret-key
CT_KEY_USER3=user3-secret-key
```

Username is derived from the env var name after the prefix (underscores become spaces).

### Optional Variables

```bash
FLASK_ENV=development  # or production
```

## Configuration Differences

### Projects
- **cloudtasks-app-473120**: Primary project (development and production)
- **crucial-haiku-473123-r7**: Legacy development project

### Python Versions
- **Python 3.11**: Used in `app.yaml` and `app.production.yaml`
- **Python 3.9**: Used in legacy `config/development.yaml` only

### Scaling
- **Development** (`app.yaml`): 1-2 instances
- **Production** (`app.production.yaml`): 1-2 instances (`min_instances: 1`)

## Recommendations

### Consolidation
1. **Remove Legacy Config**: Consider removing `config/development.yaml` if not actively used
2. **Standardize Python Version**: Use Python 3.11 for all environments
3. **Single Development Config**: Use `app.yaml` as the single development config

### Production Deployment
1. **Update Secret Keys**: Replace placeholder values in `app.production.yaml`
2. **Validate Environment**: Ensure all required variables are set
3. **Test Deployment**: `python app.py --deploy` (deploys `app.production.yaml` automatically)

## Deployment Commands

### `python app.py --deploy` (flask-base)

The deploy helper ([flask_base/deploy.py](https://github.com/toscino/flaskbase)) picks:

1. **`app.production.yaml`** if present (recommended for production deploys)
2. Else **`app.yaml`**

`app.production.yaml` uses `min_instances: 1` to keep one warm instance (reduces cold starts).

After deploy, confirm in **GCP Console → App Engine → Versions** that the active version shows `min instances: 1`.

### Manual deploy

```bash
# Local / dev
gcloud app deploy app.yaml

# Production
gcloud app deploy app.production.yaml
```

### Endpoint timing (local)

With the server running:

```powershell
.venv\Scripts\python.exe scripts\perf_check_endpoints.py
```

## Configuration Validation

Before deployment, ensure:
- [ ] All secret keys are set (not placeholder values)
- [ ] Project ID matches your GCP project
- [ ] Python version is compatible
- [ ] Environment variables are properly configured

## Troubleshooting

### "Project not found" Error
- Check `GOOGLE_CLOUD_PROJECT` in config file
- Verify project exists in GCP Console
- Ensure you have access to the project

### "Secret key not found" Error
- Check `CT_KEY_*` entries in `app.yaml` / `app.production.yaml` (or `.env` locally)
- Verify `.env` file exists locally
- Check environment variables in deployment console

### "OpenAI API key not found" Warning
- Set `OPENAI_API_KEY` in environment variables
- Verify API key is valid
- Check quota and billing

## Security Notes

- **Never commit secret keys to Git**
- Use `.env` file for local development
- Use GCP Secrets Manager for production
- Rotate secret keys regularly
- Use different keys for development and production

