"""
Unit tests for the Firestore Test App
"""
import unittest
from unittest.mock import patch, MagicMock
from src.app import create_app

class TestApp(unittest.TestCase):
    """Test cases for the Flask application"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_index_route(self):
        """Test the main index route"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    @patch('src.app.firestore.Client')
    def test_firestore_connection_success(self, mock_firestore):
        """Test successful Firestore connection"""
        # Mock Firestore client and document
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'message': 'Test data'}
        
        mock_collection = MagicMock()
        mock_document = MagicMock()
        mock_document.get.return_value = mock_doc
        mock_collection.document.return_value = mock_document
        mock_firestore.return_value.collection.return_value = mock_collection
        
        response = self.client.get('/api/test')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
    
    def test_add_data_missing_data(self):
        """Test adding data with missing request data"""
        response = self.client.post('/api/data')
        self.assertEqual(response.status_code, 400)
    
    def test_add_data_valid_data(self):
        """Test adding valid data"""
        test_data = {
            'name': 'Test User',
            'email': 'test@example.com',  # This is the fallback for testing
            'message': 'Test message'
        }
        
        with patch('src.app.firestore.Client') as mock_firestore:
            mock_collection = MagicMock()
            mock_doc_ref = MagicMock()
            mock_doc_ref.id = 'test-doc-id'
            mock_collection.add.return_value = (None, mock_doc_ref)
            mock_firestore.return_value.collection.return_value = mock_collection
            
            response = self.client.post('/api/data', 
                                      json=test_data,
                                      content_type='application/json')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'success')

if __name__ == '__main__':
    unittest.main()
