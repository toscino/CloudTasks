"""Authentication service with unified user-permission model."""

import logging
import os
from functools import wraps
from typing import Any, Callable

from flask import request, session, jsonify


class AuthService:
    """Authentication service with unified user-permission model."""

    def __init__(self, logger: logging.Logger) -> None:
        """
        Initialize auth service.
        
        Args:
            logger: Logger instance to use for logging
        """
        self.logger = logger
        self.admin_key = os.environ.get("ADMIN_KEY")
        if not self.admin_key:
            raise ValueError("ADMIN_KEY environment variable is required")
        
        # Get key prefix from environment (required, no default)
        # Each project must set FLASK_BASE_KEY_PREFIX to avoid conflicts
        key_prefix = os.environ.get("FLASK_BASE_KEY_PREFIX")
        if not key_prefix:
            raise ValueError(
                "FLASK_BASE_KEY_PREFIX environment variable is required. "
                "Set it to your project's prefix (e.g., FLASK_BASE_KEY_PREFIX=AID_KEY_)"
            )
        key_prefix = key_prefix.upper()
        
        # Parse user keys from environment
        # Format: <PREFIX><username>=user_key:permission1,permission2
        # Example with CT_KEY_ prefix: CT_KEY_IAN_B=dev-key:send,view
        # Username extracted from env var name (underscores become spaces): CT_KEY_IAN_B → "Ian B"
        # User provides the actual key value in ?key= parameter: ?key=dev-key
        self.key_map: dict[str, tuple[str, list[str]]] = {}
        
        # Scan environment for key definitions
        for env_var_name, env_var_value in os.environ.items():
            env_var_upper = env_var_name.upper()
            # Only process keys that start with the prefix
            if env_var_upper.startswith(key_prefix):
                try:
                    # Extract username from env var name (remove prefix, replace underscores with spaces)
                    # Get original case env var name (before uppercasing)
                    username_part = env_var_name.replace(key_prefix, "").replace("_", " ")
                    # Capitalize first letter of each word
                    username = " ".join(word.capitalize() for word in username_part.split())
                    
                    # Parse value: user_key:permission1,permission2 or just user_key (no colon = no permissions)
                    if ":" in env_var_value:
                        user_key, perms_str = env_var_value.split(":", 1)
                        user_key = user_key.strip()
                        permissions = [p.strip() for p in perms_str.split(",") if p.strip()]
                    else:
                        # No colon means entire value is the key, no permissions
                        user_key = env_var_value.strip()
                        permissions = []
                    
                    if not user_key:
                        self.logger.warning(f"Empty key value for {env_var_name}, skipping")
                        continue
                    
                    # Store mapping: user_key.lower() → (username, permissions)
                    # Use lowercase for case-insensitive matching
                    self.key_map[user_key.lower()] = (username, permissions)
                    self.logger.debug(f"Loaded key {user_key}: {username} with permissions {permissions}")
                except ValueError:
                    self.logger.warning(f"Invalid key format for {env_var_name}: {env_var_value}")
        
        self.logger.info(f"Loaded {len(self.key_map)} user keys")

    def _user_has_permissions(self, user_permissions: list[str], required_perms: tuple[str, ...]) -> bool:
        """Check if user has all required permissions."""
        user_perms_set = set(user_permissions)
        
        # Admin has all permissions
        if "admin" in user_perms_set:
            return True
        
        # User must have ALL required permissions
        required_set = set(required_perms)
        return required_set.issubset(user_perms_set)

    def _validate_key_and_get_user_info(self, key: str) -> tuple[str, list[str]] | None:
        """
        Validate key and return (username, permissions), or None if invalid.
        
        Args:
            key: The key to validate (user provides this in ?key= parameter)
            
        Returns:
            Tuple of (username, permissions_list) or None
        """
        # Check admin key first
        if key == self.admin_key:
            return ("admin", ["admin"])
        
        # Check against stored key values (case-insensitive comparison)
        key_lower = key.lower()
        self.logger.debug(f"Looking up key '{key_lower}' in key_map. Available keys: {list(self.key_map.keys())}")
        if key_lower in self.key_map:
            username, permissions = self.key_map[key_lower]
            self.logger.debug(f"Found key '{key_lower}' -> username: {username}, permissions: {permissions}")
            return (username, permissions)
        
        self.logger.debug(f"Key '{key_lower}' not found in key_map")
        return None

    def _authenticate_user(self) -> tuple[bool, str, list[str]]:
        """
        Get authenticated user's info.
        
        Returns:
            Tuple of (is_authenticated, user_id, permissions_list)
        """
        # Check session first
        if session.get("authenticated") and session.get("user_id"):
            user_id = session["user_id"]
            permissions = session.get("permissions", [])
            self.logger.debug(f"Using session user: {user_id}")
            return True, user_id, permissions
        
        # Fallback to key in URL or headers
        key = request.args.get("key", "")
        
        if key:
            self.logger.debug(f"Validating key from request: '{key}' (length: {len(key)})")
            user_info = self._validate_key_and_get_user_info(key)
            self.logger.debug(f"Key validation result: {user_info}")
            
            if user_info:
                user_id, permissions = user_info
                # Store in session for future requests
                session["user_id"] = user_id
                session["permissions"] = permissions
                session["authenticated"] = True
                self.logger.info(f"Authenticated user: {user_id} with permissions: {permissions}")
                return True, user_id, permissions
            else:
                self.logger.warning(f"Invalid key provided (length: {len(key)})")
        
        return False, "", []

    def require_auth(self, auth: str | bool | None = None) -> Callable:
        """
        Decorator that requires authentication with optional permissions.
        
        Args:
            auth: If True, requires any auth. If string, requires that permission.
                If None/omitted, requires any auth.
        
        Usage:
            @app.route('/send')
            @auth_service.require_auth("send")
            def send_page():
                ...
                
            @app.route('/profile')
            @auth_service.require_auth(True)
            def profile_page():
                ...
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated_function(*args, **kwargs) -> Any:
                is_authenticated, user_id, user_permissions = self._authenticate_user()
                
                # Check if this is an HTML request or API request
                wants_html = "text/html" in request.headers.get("Accept", "")
                
                # Check authentication
                if not is_authenticated:
                    if wants_html:
                        return "<h1>Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404
                    return jsonify({"error": "Not found"}), 404
                
                # Check if specific permission required
                if isinstance(auth, str):
                    required_perms = (auth,)
                    if not self._user_has_permissions(user_permissions, required_perms):
                        self.logger.warning(
                            f"User {user_id} attempted to access route requiring {required_perms}"
                        )
                        if wants_html:
                            return "<h1>Not Found</h1><p>The page you're looking for doesn't exist.</p>", 404
                        return jsonify({"error": "Not found"}), 404
                
                return f(*args, **kwargs)
            
            return decorated_function
        
        return decorator

