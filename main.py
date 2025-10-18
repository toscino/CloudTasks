"""
Entry point for the Firestore Test App - App Engine compatible
"""
import os
from app import create_app

# Create the app instance for App Engine
app = create_app()

if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
