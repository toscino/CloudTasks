"""Flask application factory with Firestore and authentication."""

# CRITICAL: Load .env FIRST, before ANY other imports
# This ensures environment variables are available when FlaskApp initializes
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Explicitly load from current working directory (where app.py is run from)
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback: let load_dotenv search automatically
        load_dotenv()
except ImportError:
    pass

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import jinja2
from flask import Flask, jsonify, render_template, request, session, redirect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .auth import AuthService



class FlaskApp:
    """Main Flask application class with Firestore and authentication."""

    def __init__(
        self, 
        app_name: str, 
        demo_user: str = "demo"
    ) -> None:
        """
        Initialize Flask app with Firestore and authentication.
        
        Args:
            app_name: Application name (used in templates)
            demo_user: User ID to use for unauthenticated access (default: "demo")
        """
        self.app_name = app_name
        self.demo_user = demo_user
        # GOOGLE_CLOUD_PROJECT is set by App Engine, or user should set in .env for local
        self.gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        
        # Track registered pages for navigation
        self._pages: list[dict[str, Any]] = []
        self._root_page: Optional[str] = None
        
        # Initialize Flask app with explicit static folder
        # This ensures static files are served from the project root, not the package
        project_root = Path.cwd()
        static_folder = project_root / "static"
        self.app = Flask(__name__, static_folder=str(static_folder))
        
        # Validate FLASK_SECRET
        flask_secret = os.environ.get("FLASK_SECRET")
        if not flask_secret:
            raise ValueError("FLASK_SECRET environment variable is required")
        self.app.secret_key = flask_secret
        
        # Configure template loader to check both project templates and package templates
        self._setup_template_loader()
        
        # Make app_name and pages available to all templates
        @self.app.context_processor
        def inject_template_context() -> dict:
            return {
                "app_name": self.app_name,
                "pages": self._pages
            }
        
        # Configure logging
        self.app.logger.setLevel(logging.DEBUG)
        
        # Initialize rate limiter
        self.limiter = Limiter(
            app=self.app,
            key_func=get_remote_address,
            default_limits=["20 per hour"],
            storage_uri="memory://",
        )
        
        # Initialize authentication service with logger
        self.auth_service = AuthService(self.app.logger)
        
        # Register before_request handler to process key parameter from URL
        # This allows authentication via ?key= parameter on any page, even unprotected ones
        @self.app.before_request
        def process_key_authentication():
            """Process key parameter from URL for authentication on all requests."""
            # Only process if there's a key in the URL and user isn't already authenticated
            if "key" in request.args and not session.get("authenticated"):
                self.auth_service._authenticate_user()
            
            # If user is authenticated and key is in URL, redirect to remove it (for GET requests)
            if request.method == "GET" and "key" in request.args and session.get("authenticated"):
                from urllib.parse import urlencode
                clean_url = request.path
                query_params = dict(request.args)
                query_params.pop("key", None)
                if query_params:
                    clean_url += "?" + urlencode(query_params, doseq=True)
                # Only redirect once per session to avoid loops
                if not session.get("_key_redirected"):
                    session["_key_redirected"] = True
                    return redirect(clean_url, code=302)
                else:
                    session.pop("_key_redirected", None)
        
        # Lazy Firestore initialization
        self._db: Optional[Any] = None
        
        # Register /api/permissions route
        self._register_permissions_route()
        
        # Expose require_auth as a convenience method
        self.require_auth = self.auth_service.require_auth

    def run(self) -> None:
        """Run the app with --run or --deploy flags."""
        import argparse
        import os
        import sys
        
        from .checks import deploy_checks, run_checks
        
        parser = argparse.ArgumentParser(description="Flask App Runner")
        parser.add_argument('--run', action='store_true', help='Run the Flask server')
        parser.add_argument('--deploy', action='store_true', help='Deploy to App Engine')
        
        args = parser.parse_args()
        
        if args.run:
            # Run checks (sets FLASK_BASE_RUN_CHECKS_PASSED)
            host = '0.0.0.0'
            port = int(os.environ.get('PORT', 8080))
            run_checks(host, port)
            
            # Set gcloud project for consistency
            from .deploy import set_gcloud_project
            set_gcloud_project()
            
            # Start app
            self.start(host=host, port=port, debug=True)
        elif args.deploy:
            # Run deploy checks (sets FLASK_BASE_DEPLOY_CHECKS_PASSED)
            deploy_checks()
            
            # Run deploy script
            from .deploy import main as deploy_main
            deploy_main()
        else:
            parser.print_usage()
            print("\nERROR: Must specify --run or --deploy")
            print("  python app.py --run    - Start the Flask server")
            print("  python app.py --deploy - Deploy to App Engine")
            sys.exit(1)

    def _setup_template_loader(self) -> None:
        """Configure template loader to check both project and package templates."""
        # Get current working directory (project root)
        project_templates = Path("templates")
        
        # Get package templates path
        package_dir = Path(__file__).parent
        package_templates = package_dir / "templates"
        
        # Create loaders for both paths
        loaders = []
        
        # Add project templates first (so it can override package templates)
        if project_templates.exists():
            loaders.append(jinja2.FileSystemLoader(str(project_templates.absolute())))
        
        # Add package templates (library defaults)
        if package_templates.exists():
            loaders.append(jinja2.FileSystemLoader(str(package_templates.absolute())))
        
        # Use ChoiceLoader to check both paths
        if loaders:
            self.app.jinja_loader = jinja2.ChoiceLoader(loaders)
        else:
            # Fallback to default if neither exists
            self.app.logger.warning("No template directories found")

    @property
    def current_user(self) -> str:
        """Get current authenticated user ID, or demo_user if not authenticated."""
        # Check for key in URL to authenticate if not already authenticated
        if not session.get("authenticated"):
            self.auth_service._authenticate_user()
        return session.get("user_id", self.demo_user)
    
    @property
    def logger(self) -> logging.Logger:
        """Get the application logger."""
        return self.app.logger
    
    @property
    def db(self) -> Any:
        """Get Firestore client (lazy initialization)."""
        if self._db is None:
            from .firestore_setup import get_db
            self._db = get_db(self.gcp_project)
        return self._db
    
    def get_json(self) -> dict[str, Any]:
        """
        Get JSON data from request body.
        
        Returns:
            Dict parsed from request JSON
        
        Raises:
            ValueError: If request has no JSON data or content-type is not JSON
        """
        if not request.is_json:
            raise ValueError("Request must have Content-Type: application/json")
        data = request.get_json()
        if data is None:
            raise ValueError("Request body is empty or invalid JSON")
        return data
    
    def jsonify(self, *args: Any, **kwargs: Any) -> Any:
        """Create JSON response (wrapper for Flask's jsonify)."""
        return jsonify(*args, **kwargs)
    
    def route(
        self, 
        path: str, 
        methods: list[str] | None = None,
        auth: str | bool | None = None,
        limit: str | None = None
    ) -> Callable:
        """
        Register a route with optional auth and rate limiting.
        
        Args:
            path: Route path (e.g., "/api/messages")
            methods: HTTP methods (e.g., ["POST"]). Defaults to ["GET"]
            auth: Auth requirement. True=any auth, str=specific permission, None=no auth
            limit: Rate limit string (e.g., "100 per hour")
        
        Returns:
            Decorator function
        
        Usage:
            @app_manager.route("/api/messages", ["POST"], "send", "100 per hour")
            def create_message():
                ...
        """
        def decorator(f: Callable) -> Callable:
            # Apply rate limiting if specified
            if limit:
                f = self.limiter.limit(limit)(f)
            
            # Apply auth if specified
            if auth is not None:
                if isinstance(auth, str):
                    f = self.require_auth(auth)(f)
                elif auth is True:
                    f = self.require_auth(True)(f)
            
            # Register route with Flask
            method_list = methods if methods else ["GET"]
            self.app.route(path, methods=method_list)(f)
            
            return f
        
        return decorator
    
    def page(self, template: str, permission: str | bool | None = None, auth: bool = False, root: bool = False) -> None:
        """
        Register a page route that renders a template.
        
        Args:
            template: Template filename (e.g., "send.html")
            permission: Permission required. If string, requires that permission.
                       If bool, requires any auth if True. If None, no auth required.
            auth: Alias for permission=True (deprecated, use permission=True)
            root: If True, register this page as the root route "/"
        
        Usage:
            app_manager.page("send.html", "send")
            app_manager.page("display.html", "view")
            app_manager.page("profile.html", auth=True)
            app_manager.page("home.html", root=True)  # Register as "/"
        """
        # Use root route if specified, otherwise infer from template name
        if root:
            if self._root_page is not None:
                raise ValueError(f"Root page already set to {self._root_page}. Only one page can be designated as root.")
            route = "/"
            self._root_page = template
        else:
            route = "/" + template.replace(".html", "").replace("_", "-")
        
        # Infer title from template name
        title = template.replace(".html", "").replace("_", " ").title()
        
        # Create unique handler endpoint name (use route without leading slash)
        if route == "/":
            endpoint_name = "page_root"
        else:
            endpoint_name = f"page_{route[1:].replace('-', '_')}"
        
        # Create handler
        def handler() -> str:
            return render_template(template)
        
        # Update handler name for unique endpoint
        handler.__name__ = endpoint_name
        
        # Register with auth if specified
        if auth:
            permission = True
        
        if permission is not None:
            if isinstance(permission, str):
                handler = self.require_auth(permission)(handler)
            else:
                handler = self.require_auth(True)(handler)
        
        # Exempt page routes from rate limiting (they're just HTML templates)
        handler = self.limiter.exempt(handler)
        
        # Register route
        self.app.route(route)(handler)
        
        # Store for navigation (only if requires auth)
        if permission is not None:
            self._pages.append({
                "route": route,
                "title": title,
                "permission": permission if isinstance(permission, str) else None
            })
    
    def _register_permissions_route(self) -> None:
        """Register /api/permissions route."""
        @self.limiter.limit("100 per minute")
        @self.app.route("/api/permissions")
        def get_permissions() -> Any:
            """Get current user's info if authenticated."""
            if session.get("authenticated") and session.get("user_id"):
                return jsonify({
                    "user_id": session["user_id"],
                    "permissions": session.get("permissions", []),
                    "authenticated": True
                })
            return jsonify({"user_id": None, "permissions": [], "authenticated": False})

    def start(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = True) -> None:
        """
        Start the Flask server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
        """
        print("\n" + "=" * 60)
        print("STARTING FLASK SERVER!")
        print("=" * 60 + "\n")
        
        # Setup logging configuration
        # 1. Configure werkzeug (for request logs)
        werkzeug_logger = logging.getLogger("werkzeug")
        werkzeug_logger.setLevel(logging.INFO)
        
        # 2. Log startup message
        self.app.logger.info("Server started and ready for requests")
        
        base_url = f"http://127.0.0.1:{port}"
        # Print admin link if available
        admin_key = os.environ.get("ADMIN_KEY")
        if admin_key:
            print(f"Admin: {base_url}/admin?key={admin_key}")
        # Print user links (local address with key)
        for key, (username, _) in sorted(self.auth_service.key_map.items(), key=lambda x: x[1][0]):
            print(f"{username}: {base_url}/?key={key}")
        print(f"\nServer running on {base_url}/")
        self.app.run(host=host, port=port, debug=debug)

