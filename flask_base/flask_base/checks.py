"""Safety checks for running and deploying Flask apps."""

import os
import socket
import sys

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_port_available(host: str, port: int) -> bool:
    """
    Check if a port is available for binding.
    
    Args:
        host: Host to check
        port: Port to check
        
    Returns:
        True if port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def validate_environment() -> None:
    """
    Validate required environment variables exist.
    
    Raises:
        SystemExit: If required env vars are missing
    """
    required_vars = ["FLASK_SECRET"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Please set these in your .env file or environment")
        sys.exit(1)


def run_checks(host: str = "0.0.0.0", port: int = 8080) -> None:
    """
    Perform all safety checks for running the Flask app.
    
    Exits with error if any check fails.
    
    Args:
        host: Host to check
        port: Port to check
    """
    # Check if port is available
    if not check_port_available(host, port):
        print(f"ERROR: Port {port} is already in use!")
        print(f"Please stop the process using port {port} or use a different port.")
        sys.exit(1)
    
    # Validate environment variables
    validate_environment()
    
    print(f"✓ Port {port} is available")
    print("✓ Environment checks passed")


def deploy_checks() -> None:
    """
    Perform all safety checks for deploying to App Engine.
    
    Exits with error if any check fails.
    """
    # Check if gcloud CLI is available
    import shutil
    if not shutil.which("gcloud"):
        print("ERROR: gcloud CLI not found. Please install Google Cloud SDK.")
        sys.exit(1)
    
    # Validate environment variables
    validate_environment()
    
    print("✓ gcloud CLI found")
    print("✓ Environment checks passed")

