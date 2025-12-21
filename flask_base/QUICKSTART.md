read# FlaskBase Quickstart Guide

FlaskBase is a minimal library for quickly creating Flask web apps with Firestore, authentication, and GCP deployment.

## Installation

Copy the `flask_base/` folder into your project directory.

## Your First App

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

## Services Pattern

Services take `app_manager` and extract what they need:

```python
from flask_base import FlaskApp

class MyService:
    def __init__(self, app_manager):
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.collection = self.db.collection('items')
    
    def do_something(self):
        self.logger.info("Doing work")
        # Use self.db and self.colger
```

Initialize in `app.py`:

```python
app_manager = FlaskApp("My App")
my_service = MyService(app_manager)  # That's it!
```

## Authentication

### Setup

1. Set `ADMIN_KEY` environment variable (special admin key)
2. **Required**: Set `FLASK_BASE_KEY_PREFIX` to your project's prefix (e.g., `AID_KEY_`, `MYAPP_KEY_`)
   - This prevents conflicts between different projects using the same library
3. Add user keys with format: `<PREFIX><NAME>=user_id:permission1,permission2`
   - Example: `AID_KEY_ALICE=alice:send,view` (when prefix is `AID_KEY_`)

### Usage in Routes

```python
# Require any auth
@app_manager.route("/profile", auth=True)
def profile():
    user_id = app_manager.current_user  # "alice" or "demo" if not authenticated
    return app_manager.jsonify({"user": user_id})

# Require specific permission
@app_manager.route("/admin", "admin")
def admin():
    return app_manager.jsonify({"admin": True})
```

### Key Formats

**Permission-only project** (shared keys):
```bash
FLASK_BASE_KEY_PREFIX=AID_KEY_
AID_KEY_SENDER=sender:send
AID_KEY_VIEWER=viewer:view
```

**User-based project** (unique users):
```bash
FLASK_BASE_KEY_PREFIX=AID_KEY_
AID_KEY_ALICE=alice:send,view
AID_KEY_BOB=bob:view
```

Usage: Access pages with `?key=SENDER` or `?key=ALICE`

## API Reference

### FlaskApp Class

```python
FlaskApp(app_name: str, demo_user: str = "demo", gcp_project: Optional[str] = None)
```

**Properties:**
- `app_manager.logger` - Access Flask logger
- `app_manager.db` - Access Firestore client (lazy init)
- `app_manager.current_user` - Current user ID or demo_user

**Methods:**
- `page(template, permission)` - Register a page
- `route(path, methods, auth, limit)` - Register an API route
- `get_json()` - Get JSON from request
- `jsonify(*args, **kwargs)` - Create JSON response
- `run()` - Start server or deploy

### Page Registration

```python
app_manager.page("home.html")              # No auth required
app_manager.page("admin.html", "admin")    # Requires admin permission
app_manager.page("profile.html", auth=True) # Any authenticated user
```

Auto-infers route from template name: `home.html` → `/home`

### Route Registration

```python
@app_manager.route("/api/endpoint", ["POST"], "permission", "100 per hour")
def handler():
    data = app_manager.get_json()
    return app_manager.jsonify({"success": True}), 201
```

Parameters:
- `path` - Route path
- `methods` - List of HTTP methods (default: `["GET"]`)
- `auth` - Permission required or `True` for any auth
- `limit` - Rate limit string

## Running

### Local Development

```bash
python app.py --run
```

### Deploy to App Engine

```bash
python app.py --deploy
```

Requires `app.yaml` in project root for deployment.

## File Structure

```
your-project/
├── app.py              # Your application (3 lines minimum!)
├── flask_base/         # Library files (copied from flask_base repo)
├── templates/          # Your HTML templates
├── static/             # Your CSS/JS
├── .env                # Local environment variables
└── app.yaml            # App Engine config
```

## Examples

### Minimal App

```python
from flask_base import FlaskApp

app_manager = FlaskApp("My App")
app_manager.page("index.html")

if __name__ == '__main__':
    app_manager.run()
```

### App with Database

```python
from flask_base import FlaskApp

app_manager = FlaskApp("My App")
notes_service = NotesService(app_manager)

@app_manager.route("/notes", ["POST"], auth=True)
def create_note():
    data = app_manager.get_json()
    note_id = notes_service.create(data)
    return app_manager.jsonify({"id": note_id}), 201
```

### Protected Routes

```python
@app_manager.route("/admin/users", "admin")
def list_users():
    # Only admin can access
    users = user_service.list_all()
    return app_manager.jsonify(users)
```

## Tips

1. **One import**: Only import `FlaskApp` from flask_base
2. **Service pattern**: Always pass `app_manager`, extract `logger` and `db`
3. **Hard fails**: Missing required env vars crash on startup (good for security)
4. **Demo mode**: Unauthenticated users get `current_user = "demo"` for demo data
5. **Navigation**: Auto-generates from registered pages
6. **Static files**: Served from project root `/static` folder

## Common Patterns

### Database Access

```python
class MyService:
    def __init__(self, app_manager):
        self.logger = app_manager.logger
        self.db = app_manager.db
        self.collection = self.db.collection('items')
    
    def save(self, data):
        self.logger.info(f"Saving: {data}")
        doc = self.collection.add(data)[1]
        return doc.id
```

### User-Scoped Data

```python
@app_manager.route("/my-items", auth=True)
def get_my_items():
    user_id = app_manager.current_user
    docs = app_manager.db.collection('items')\
        .where('user_id', '==', user_id)\
        .get()
    items = [doc.to_dict() for doc in docs]
    return app_manager.jsonify(items)
```

### Error Handling

```python
@app_manager.route("/create", ["POST"], "admin")
def create():
    try:
        data = app_manager.get_json()
        result = service.create(data)
        return app_manager.jsonify({"success": True}), 201
    except ValueError as e:
        return app_manager.jsonify({"error": str(e)}), 400
```

## Architecture

FlaskBase provides:
- **Flask initialization** - App, secret key, static files
- **Firestore connection** - Lazy initialization with optional GCP project
- **Authentication** - Unified user-permission model
- **Rate limiting** - Per-route or global
- **Navigation** - Auto-generates from page registrations
- **Logging** - Unified logger via `app_manager.logger`
- **Templates** - Auto-discovery of project templates

You provide:
- **Business logic** - Services, models, validation
- **Templates** - HTML pages
- **Static assets** - CSS, JavaScript
- **Configuration** - Environment variables

## Next Steps

- Read `docs/KEYS.md` for authentication details
- Read `docs/DEPLOYMENT.md` for production deployment
- See the `app.py` in this repo for a complete example

