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

### `config/production.yaml` (Production Config)
**Runtime**: Python 3.9  
**Project**: `cloudtasks-app-473120`  
**Environment**: Production  
**Purpose**: Production deployment

**Key Settings**:
- Uses Python 3.9
- Higher scaling (2-20 instances)
- Production secret keys (placeholder values)
- All environment variables defined

**Usage**: `gcloud app deploy config/production.yaml`

## Environment Variables

### Required Variables

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
FLASK_SECRET=your-flask-secret-key
ADMIN_KEY=your-admin-key
FLASK_BASE_KEY_PREFIX=CT_KEY_
OPENAI_API_KEY=your-openai-api-key
```

### User Authentication

```bash
USER1_SECRET_KEY=user1-secret-key  # Ian's secret key
USER2_SECRET_KEY=user2-secret-key  # Karleigh's secret key
USER3_SECRET_KEY=user3-secret-key  # Third user's secret key
```

### Optional Variables

```bash
FLASK_ENV=development  # or production
```

## Configuration Differences

### Projects
- **cloudtasks-app-473120**: Primary project (development and production)
- **crucial-haiku-473123-r7**: Legacy development project

### Python Versions
- **Python 3.11**: Used in `app.yaml` (current development)
- **Python 3.9**: Used in legacy configs

### Scaling
- **Development**: 1-2 instances (minimal)
- **Production**: 2-20 instances (auto-scaling)

## Recommendations

### Consolidation
1. **Remove Legacy Config**: Consider removing `config/development.yaml` if not actively used
2. **Standardize Python Version**: Use Python 3.11 for all environments
3. **Single Development Config**: Use `app.yaml` as the single development config

### Production Deployment
1. **Update Secret Keys**: Replace placeholder values in `config/production.yaml`
2. **Validate Environment**: Ensure all required variables are set
3. **Test Deployment**: Verify production config before deployment

## Deployment Commands

### Development
```bash
# Deploy to development (using app.yaml)
gcloud app deploy app.yaml

# Or deploy to legacy dev environment
gcloud app deploy config/development.yaml
```

### Production
```bash
# Deploy to production
gcloud app deploy config/production.yaml
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
- Check `USER1_SECRET_KEY`, `USER2_SECRET_KEY`, `USER3_SECRET_KEY`
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

