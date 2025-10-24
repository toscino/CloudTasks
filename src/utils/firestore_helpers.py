"""
Firestore helper utilities - common Firestore operations and conversions
"""
from datetime import datetime
from typing import Dict, Any, Optional


def convert_firestore_timestamp(timestamp: Any) -> Optional[datetime]:
    """
    Convert Firestore timestamp to Python datetime.
    
    Args:
        timestamp: Firestore timestamp object
        
    Returns:
        datetime object or None if timestamp is None
        
    Example:
        data = doc.to_dict()
        created_at = convert_firestore_timestamp(data.get('created_at'))
    """
    if not timestamp:
        return None
    
    if hasattr(timestamp, 'timestamp'):
        return datetime.fromtimestamp(timestamp.timestamp())
    
    return timestamp


def convert_firestore_timestamps(data: Dict[str, Any], fields: list = None) -> Dict[str, Any]:
    """
    Convert Firestore timestamps in a document to Python datetime objects.
    
    Args:
        data: Document data dictionary from Firestore
        fields: List of field names to convert. If None, converts common timestamp fields.
        
    Returns:
        Modified dictionary with timestamps converted to datetime objects
        
    Example:
        data = doc.to_dict()
        data = convert_firestore_timestamps(data)
        # Now created_at and updated_at are datetime objects
    """
    if fields is None:
        fields = ['created_at', 'updated_at', 'completed_at', 'presented_at']
    
    for field in fields:
        if field in data:
            data[field] = convert_firestore_timestamp(data[field])
    
    return data


def add_document_id(data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    """
    Add document ID to Firestore document data.
    
    Args:
        data: Document data dictionary from Firestore
        doc_id: Document ID
        
    Returns:
        Modified dictionary with 'id' field added
        
    Example:
        data = doc.to_dict()
        data = add_document_id(data, doc.id)
    """
    data['id'] = doc_id
    return data


def prepare_firestore_document(doc) -> Dict[str, Any]:
    """
    Prepare a Firestore document for use in the application.
    
    Converts document to dict, adds document ID, and converts timestamps.
    
    Args:
        doc: Firestore document object
        
    Returns:
        Dictionary ready for use in application
        
    Example:
        for doc in query.stream():
            data = prepare_firestore_document(doc)
            # data now has 'id' field and converted timestamps
    """
    data = doc.to_dict()
    data = add_document_id(data, doc.id)
    data = convert_firestore_timestamps(data)
    return data

