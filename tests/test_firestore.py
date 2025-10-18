"""
Integration tests for Firestore operations
"""
import unittest
import os
from google.cloud import firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TestFirestoreIntegration(unittest.TestCase):
    """Integration tests for Firestore operations"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        # Only run integration tests if Firestore is configured
        if not os.getenv('GOOGLE_CLOUD_PROJECT'):
            raise unittest.SkipTest("Firestore not configured for integration tests")
        
        cls.db = firestore.Client()
        cls.test_collection = 'test_integration'
    
    def setUp(self):
        """Set up test fixtures"""
        # Clean up any existing test documents
        docs = self.db.collection(self.test_collection).stream()
        for doc in docs:
            doc.reference.delete()
    
    def test_firestore_connection(self):
        """Test basic Firestore connection"""
        # Try to create and read a document
        doc_ref = self.db.collection(self.test_collection).document('test_connection')
        doc_ref.set({
            'message': 'Integration test',
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # Verify the document was created
        doc = doc_ref.get()
        self.assertTrue(doc.exists)
        self.assertEqual(doc.to_dict()['message'], 'Integration test')
    
    def test_add_and_retrieve_data(self):
        """Test adding and retrieving data"""
        # Add test data
        test_data = {
            'name': 'Integration Test User',
            'email': 'integration@test.com',
            'message': 'This is an integration test'
        }
        
        doc_ref = self.db.collection(self.test_collection).add(test_data)
        doc_id = doc_ref[1].id
        
        # Retrieve the data
        doc = self.db.collection(self.test_collection).document(doc_id).get()
        self.assertTrue(doc.exists)
        self.assertEqual(doc.to_dict()['name'], 'Integration Test User')
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up test documents
        docs = self.db.collection(self.test_collection).stream()
        for doc in docs:
            doc.reference.delete()

if __name__ == '__main__':
    unittest.main()
