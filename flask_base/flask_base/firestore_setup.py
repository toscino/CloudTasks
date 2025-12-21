"""Firestore client initialization."""

from typing import Any, Optional

try:
    from google.cloud import firestore
except ImportError:
    firestore = None  # type: ignore


def get_db(project_id: Optional[str] = None) -> Any:
    """
    Get Firestore client (lazy initialization).
    
    Args:
        project_id: Optional GCP project ID
    
    Returns:
        Firestore Client instance
    """
    if firestore is None:
        raise ImportError(
            "google-cloud-firestore is not installed. "
            "Install with: pip install google-cloud-firestore"
        )
    
    return firestore.Client(project=project_id)

