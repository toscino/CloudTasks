#!/usr/bin/env python3
"""
Test script for secret key authentication
"""
import requests
import os

# Set your test secret key (should match run.bat)
SECRET_KEY = "my-local-secret-123"
USERNAME = "testuser"
BASE_URL = "http://localhost:8080"

def test_auth_scenarios():
    print("🔓 Testing Permissive Authentication (test_user fallback)\n")
    
    # Test 1: No authentication (should work as test_user)
    print("1. Testing without authentication (should work as test_user):")
    try:
        response = requests.get(f"{BASE_URL}/api/tasks")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('status', 'N/A')}")
            print(f"   Username: {data.get('tasks', [{}])[0].get('username', 'N/A') if data.get('tasks') else 'No tasks'}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 2: With correct secret key via headers (should work as authenticated user)
    print("2. Testing with correct secret key via headers:")
    try:
        headers = {
            'X-Secret-Key': SECRET_KEY,
            'X-Username': USERNAME
        }
        response = requests.get(f"{BASE_URL}/api/tasks", headers=headers)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('status', 'N/A')}")
            print(f"   Username: {data.get('tasks', [{}])[0].get('username', 'N/A') if data.get('tasks') else 'No tasks'}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 3: With correct secret key via URL parameters (should work as authenticated user)
    print("3. Testing with correct secret key via URL parameters:")
    try:
        params = {
            'secret_key': SECRET_KEY,
            'username': USERNAME
        }
        response = requests.get(f"{BASE_URL}/api/tasks", params=params)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('status', 'N/A')}")
            print(f"   Username: {data.get('tasks', [{}])[0].get('username', 'N/A') if data.get('tasks') else 'No tasks'}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 4: Wrong secret key (should work as test_user)
    print("4. Testing with wrong secret key (should work as test_user):")
    try:
        headers = {
            'X-Secret-Key': 'wrong-secret',
            'X-Username': USERNAME
        }
        response = requests.get(f"{BASE_URL}/api/tasks", headers=headers)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('status', 'N/A')}")
            print(f"   Username: {data.get('tasks', [{}])[0].get('username', 'N/A') if data.get('tasks') else 'No tasks'}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 5: Username without secret key (should work as test_user)
    print("5. Testing with username but no secret key (should work as test_user):")
    try:
        params = {'username': USERNAME}
        response = requests.get(f"{BASE_URL}/api/tasks", params=params)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('status', 'N/A')}")
            print(f"   Username: {data.get('tasks', [{}])[0].get('username', 'N/A') if data.get('tasks') else 'No tasks'}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 6: Test task creation with authentication
    print("6. Testing task creation with correct authentication:")
    try:
        headers = {
            'X-Secret-Key': SECRET_KEY,
            'X-Username': USERNAME,
            'Content-Type': 'application/json'
        }
        task_data = {'description': 'Test task with enforced auth'}
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_data, headers=headers)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('message', 'N/A')}")
            if 'task_id' in data:
                print(f"   Task ID: {data['task_id']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 7: Test task creation without authentication (should work as test_user)
    print("7. Testing task creation without authentication (should work as test_user):")
    try:
        task_data = {'description': 'Test task without auth'}
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_data)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data.get('message', 'N/A')}")
            if 'task_id' in data:
                print(f"   Task ID: {data['task_id']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 8: Test /api/user endpoint to see authentication status
    print("8. Testing /api/user endpoint:")
    try:
        response = requests.get(f"{BASE_URL}/api/user")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Username={data.get('username')}, Authenticated={data.get('authenticated')}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 11: Test wrong secret key shows test_user with test icon
    print("11. Testing wrong secret key behavior:")
    try:
        headers = {
            'X-Secret-Key': 'wrong-secret',
            'X-Username': USERNAME
        }
        response = requests.get(f"{BASE_URL}/api/user", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"   Username: {data.get('username')}")
            print(f"   Authenticated: {data.get('authenticated')}")
            if data.get('username') == 'test_user' and not data.get('authenticated'):
                print(f"   ✅ Correctly shows test_user with unauthenticated status")
            else:
                print(f"   ❌ Should show test_user with unauthenticated status")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 12: Test user isolation - create task as one user, try to access as another
    print("12. Testing user isolation:")
    try:
        # Create task as authenticated user
        headers_auth = {
            'X-Secret-Key': SECRET_KEY,
            'X-Username': USERNAME,
            'Content-Type': 'application/json'
        }
        task_data = {'description': 'Isolation test task'}
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_data, headers=headers_auth)
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            print(f"   ✅ Created task as {USERNAME}: {task_id}")
            
            # Try to complete task as test_user (should fail)
            response2 = requests.put(f"{BASE_URL}/api/tasks/{task_id}/complete")
            if response2.status_code == 403:
                print(f"   ✅ Correctly blocked test_user from modifying {USERNAME}'s task")
            else:
                print(f"   ❌ Security issue: test_user could modify {USERNAME}'s task")
                
        else:
            print(f"   ❌ Failed to create task: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    print("Make sure your Flask app is running on localhost:8080")
    print("Set APP_SECRET_KEY=my-local-secret-123 in your environment")
    print("=" * 60)
    test_auth_scenarios()
