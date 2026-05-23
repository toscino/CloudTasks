"""
Goal service - handles goal-related business logic
"""
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from src.models.goal import GoalModel, create_goal_from_request_data
from src.utils.firestore_helpers import prepare_firestore_document
from src.utils.exceptions import NotFoundError, UnauthorizedError, ValidationError, FirestoreError
from src.utils.error_handlers import handle_exception
from typing import List, Dict, Any


class GoalService:
    """Service for goal-related operations"""
    
    def __init__(self, app_manager):
        """Initialize GoalService"""
        self.logger = app_manager.logger
        self.db = app_manager.db
    
    def get_goals(self, username: str) -> Dict[str, Any]:
        """Get goals by category"""
        try:
            # Query goals for this user
            goals_query = self.db.collection('goals').where('username', '==', username)
            goals_docs = goals_query.stream()
            
            goals_by_category = {}
            for doc in goals_docs:
                goal_data = prepare_firestore_document(doc)
                
                category = goal_data.get('category', 'General')
                if category not in goals_by_category:
                    goals_by_category[category] = []
                goals_by_category[category].append(goal_data)
            
            return {
                'status': 'success',
                'goals': goals_by_category
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get goals: {str(e)}'
            }
    
    def create_goal(self, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Create goal"""
        try:
            if not data or not data.get('description'):
                raise ValidationError(
                    "Goal description is required",
                    user_message="Goal description is required"
                )
            
            # Create goal model
            goal_model = create_goal_from_request_data(data, username)
            
            if not goal_model.validate():
                raise ValidationError(
                    "Invalid goal data",
                    user_message="Invalid goal data"
                )
            
            # Create new goal in Firestore
            doc_ref = self.db.collection('goals').add(goal_model.to_firestore_dict())
            
            return {
                'status': 'success',
                'message': 'Goal created successfully',
                'goal_id': doc_ref[1].id
            }
        except ValidationError as e:
            return handle_exception(e, "Failed to create goal")
        except Exception as e:
            return handle_exception(e, "Unexpected error creating goal")
    
    def update_goal(self, goal_id: str, data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Update goal"""
        try:
            doc_ref = self.db.collection('goals').document(goal_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise NotFoundError(
                    f"Goal {goal_id} not found",
                    user_message="Goal not found"
                )
            
            goal_data = doc.to_dict()
            if goal_data.get('username') != username:
                raise UnauthorizedError(
                    f"Goal {goal_id} belongs to {goal_data.get('username')}, not {username}",
                    user_message="Unauthorized: Goal belongs to another user"
                )
            
            # Update fields
            update_data = {'updated_at': firestore.SERVER_TIMESTAMP}
            if 'description' in data:
                update_data['description'] = data['description']
            if 'category' in data:
                update_data['category'] = data['category']
            if 'priority' in data:
                update_data['priority'] = data['priority']
            if 'status' in data:
                update_data['status'] = data['status']
            if 'delete_on_complete' in data:
                update_data['delete_on_complete'] = data['delete_on_complete']
            
            doc_ref.update(update_data)
            
            return {
                'status': 'success',
                'message': 'Goal updated successfully'
            }
        except (NotFoundError, UnauthorizedError) as e:
            return handle_exception(e, "Failed to update goal")
        except Exception as e:
            return handle_exception(e, "Unexpected error updating goal")
    
    def delete_goal(self, goal_id: str, username: str) -> Dict[str, Any]:
        """Delete goal"""
        try:
            doc_ref = self.db.collection('goals').document(goal_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise NotFoundError(
                    f"Goal {goal_id} not found",
                    user_message="Goal not found"
                )
            
            goal_data = doc.to_dict()
            if goal_data.get('username') != username:
                raise UnauthorizedError(
                    f"Goal {goal_id} belongs to {goal_data.get('username')}, not {username}",
                    user_message="Unauthorized: Goal belongs to another user"
                )
            
            doc_ref.delete()
            
            return {
                'status': 'success',
                'message': 'Goal deleted successfully'
            }
        except (NotFoundError, UnauthorizedError) as e:
            return handle_exception(e, "Failed to delete goal")
        except Exception as e:
            return handle_exception(e, "Unexpected error deleting goal")
    
    def get_categories(self) -> Dict[str, Any]:
        """Get goal categories"""
        categories = [
            {'value': 'Work', 'label': 'Work', 'icon': '💼'},
            {'value': 'Kids', 'label': 'Kids', 'icon': '👶'},
            {'value': 'Spouse', 'label': 'Spouse', 'icon': '💕'},
            {'value': 'House', 'label': 'House', 'icon': '🏠'},
            {'value': 'Self', 'label': 'Self', 'icon': '🧘'}
        ]
        
        return {
            'status': 'success',
            'categories': categories
        }
