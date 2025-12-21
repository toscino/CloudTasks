# FlaskBase

A minimal library for quickly creating Flask web apps with Firestore, authentication, and GCP deployment.

## Installation

### Option 1: Install as Package (Recommended)

```bash
pip install flask-base
```

Or install from source:

```bash
pip install -e /path/to/flask-base
```

### Option 2: Copy Folder (Quick Start)

Copy the `flask_base/` folder into your project directory.

## Quick Start

Create a minimal `app.py`:

```python
from flask_base import FlaskApp

# Initialize the app
app_manager = FlaskApp("My App")

# Register pages (auto-renders templates, auto-populates nav)
app_manager.page("home.html", auth=True)  # Any authenticated user
app_manager.page("admin.html", "admin")   # Admin permission required

# Register API routes
@app_manager.route("/api/data", ["POST"], "admin", "100 per hour")
def create_data():
    data = app_manager.get_json()
    # Your logic here
    return app_manager.jsonify({"success": True}), 201

# Run the app
if __name__ == '__main__':
    app_manager.run()
```

That's it! Total boilerplate: **3 lines**.

## Configuration

Create a `.env` file:

```bash
FLASK_SECRET=your-random-secret-key
ADMIN_KEY=your-admin-key
GOOGLE_CLOUD_PROJECT=your-project-id

# REQUIRED: Set your project's key prefix to avoid conflicts
FLASK_BASE_KEY_PREFIX=AID_KEY_

# User keys with permissions (using your prefix)
# Format: <PREFIX><NAME>=user_id:permission1,permission2
AID_KEY_ALICE=alice:send,view
AID_KEY_BOB=bob:view
```

**For production**, add to `app.yaml`:

```yaml
env_variables:
  FLASK_SECRET: "your-random-secret-key"
  ADMIN_KEY: "your-admin-key"
  FLASK_BASE_KEY_PREFIX: "AID_KEY_"
  AID_KEY_ALICE: "alice:send,view"
```

## Features

- **Flask initialization** - App, secret key, static files
- **Firestore connection** - Lazy initialization with optional GCP project
- **Authentication** - Unified user-permission model with key-based auth
- **Rate limiting** - Per-route or global limits
- **Navigation** - Auto-generates from page registrations
- **Logging** - Unified logger via `app_manager.logger`
- **Templates** - Auto-discovery of project templates
- **Deployment** - Built-in App Engine deployment support

## Documentation

See [QUICKSTART.md](QUICKSTART.md) for complete documentation including:
- API reference
- Authentication patterns
- Service patterns
- Common use cases
- Examples

## Requirements

- Python 3.10+
- Flask 3.0+
- Google Cloud Firestore (optional, for database features)
- Google Cloud SDK (optional, for deployment)

## License

MIT

