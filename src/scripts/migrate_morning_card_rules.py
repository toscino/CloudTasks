"""
Migrate morning card templates and selections from ian_rules/karleigh_rules to user_rules format.

This script migrates existing morning card data to the new dynamic user_rules structure.
After running this script, update the frontend to use the new format.
"""

import os
import sys
from google.cloud import firestore
from google.cloud.firestore import FieldFilter

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def load_env_file():
    """Load environment variables from .env file"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def migrate_morning_cards():
    """Migrate morning card templates from ian_rules/karleigh_rules to user_rules format and add username field."""
    # Load environment variables
    load_env_file()
    
    # Initialize Firestore
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable not set")
        return
    
    db = firestore.Client(project=project_id)
    
    print("Starting migration of morning card templates...")
    
    # Get all templates
    templates = db.collection('morning_card_templates').stream()
    
    migrated_count = 0
    skipped_count = 0
    
    for template in templates:
        template_data = template.to_dict()
        
        # Determine username - if username field exists, use it; otherwise assign to 'Ian' by default
        username = template_data.get('username', 'Ian')
        
        # Check if already migrated to new format ('mine'/'spouse' keys)
        existing_user_rules = template_data.get('user_rules', {})
        if isinstance(existing_user_rules, dict) and ('mine' in existing_user_rules or 'spouse' in existing_user_rules):
            skipped_count += 1
            continue
        
        # Migrate old format to new format
        user_rules = {}
        
        # Handle old ian_rules/karleigh_rules format
        if 'ian_rules' in template_data:
            if username == 'Ian':
                user_rules['mine'] = template_data['ian_rules']
            else:
                user_rules['spouse'] = template_data['ian_rules']
        
        if 'karleigh_rules' in template_data:
            if username == 'Karleigh':
                user_rules['mine'] = template_data['karleigh_rules']
            else:
                user_rules['spouse'] = template_data['karleigh_rules']
        
        # Handle existing username-based user_rules (convert to generic keys)
        if 'user_rules' in template_data and isinstance(existing_user_rules, dict):
            for key, rules in existing_user_rules.items():
                if key == username:
                    user_rules['mine'] = rules
                elif key in ['Ian', 'Karleigh'] and key != username:
                    # This is the spouse's rules
                    user_rules['spouse'] = rules
                else:
                    # Keep other keys as-is
                    user_rules[key] = rules
        
        # Update document
        updates = {}
        if user_rules:
            updates['user_rules'] = user_rules
        if 'username' not in template_data:
            updates['username'] = username
        
        if updates:
            db.collection('morning_card_templates').document(template.id).update(updates)
            migrated_count += 1
            print(f"Migrated template {template.id} (username: {username})")
        else:
            skipped_count += 1
    
    print(f"\nMigration complete: {migrated_count} migrated, {skipped_count} skipped")
    print("\nYou can now use the new user_rules format.")

if __name__ == '__main__':
    migrate_morning_cards()

