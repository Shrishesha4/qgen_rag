#!/usr/bin/env python3
"""
Demo script to test the initial admin setup workflow.

This script demonstrates:
1. Creating the first admin account via /auth/setup-initial-admin
2. Logging in with the admin account
3. Attempting to create another admin (should fail without auth)
4. Creating additional admins via /admin/users with auth
"""

import requests
import json
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
FIRST_ADMIN_EMAIL = "admin@example.com"
FIRST_ADMIN_PASSWORD = "SecurePassword123!"
FIRST_ADMIN_USERNAME = "admin"

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_response(response: requests.Response, title: str = "Response"):
    """Print a formatted response."""
    print(f"{title}:")
    print(f"  Status: {response.status_code}")
    try:
        data = response.json()
        print(f"  Body: {json.dumps(data, indent=2)}")
    except:
        print(f"  Body: {response.text}")
    print()

def create_first_admin():
    """Test the initial admin setup endpoint."""
    print_section("Step 1: Create Initial Admin")
    
    payload = {
        "email": FIRST_ADMIN_EMAIL,
        "username": FIRST_ADMIN_USERNAME,
        "password": FIRST_ADMIN_PASSWORD,
        "full_name": "System Administrator",
        "security_question": "What is your favorite color?",
        "security_answer": "blue"
    }
    
    print(f"POST {API_BASE_URL}/auth/setup-initial-admin")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/auth/setup-initial-admin",
        json=payload
    )
    
    print_response(response, "Initial Admin Creation Response")
    
    if response.status_code == 201:
        print("✅ First admin created successfully!\n")
        return response.json()
    else:
        print("❌ Failed to create first admin\n")
        return None

def login_with_admin():
    """Test login with the admin account."""
    print_section("Step 2: Login with Admin Account")
    
    payload = {
        "email": FIRST_ADMIN_EMAIL,
        "password": FIRST_ADMIN_PASSWORD
    }
    
    print(f"POST {API_BASE_URL}/auth/login")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json=payload
    )
    
    print_response(response, "Login Response")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful!\n")
        return data.get("access_token")
    else:
        print("❌ Login failed\n")
        return None

def test_duplicate_admin_check():
    """Test that creating another admin via setup endpoint fails."""
    print_section("Step 3: Test Duplicate Admin Check (Should Fail)")
    
    payload = {
        "email": "admin2@example.com",
        "username": "admin2",
        "password": "AnotherSecurePassword123!",
        "full_name": "Second Admin",
        "security_question": "What is your favorite fruit?",
        "security_answer": "apple"
    }
    
    print(f"POST {API_BASE_URL}/auth/setup-initial-admin")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/auth/setup-initial-admin",
        json=payload
    )
    
    print_response(response, "Second Admin Creation Attempt")
    
    if response.status_code == 403:
        print("✅ Correctly rejected (as expected)!\n")
        return True
    else:
        print("❌ Should have been rejected\n")
        return False

def create_additional_admin(access_token: str):
    """Test creating additional admins via /admin/users."""
    print_section("Step 4: Create Additional Admin (Authenticated)")
    
    payload = {
        "email": "admin2@example.com",
        "username": "admin2",
        "password": "AnotherSecurePassword123!",
        "full_name": "Second Admin",
        "security_question": "What is your favorite fruit?",
        "security_answer": "apple",
        "role": "admin",
        "is_active": True,
        "can_manage_groups": True,
        "can_generate": True,
        "can_vet": True
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"POST {API_BASE_URL}/admin/users")
    print(f"Headers: {{'Authorization': 'Bearer <token>', ...}}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{API_BASE_URL}/admin/users",
        json=payload,
        headers=headers
    )
    
    print_response(response, "Additional Admin Creation Response")
    
    if response.status_code == 201:
        print("✅ Second admin created successfully!\n")
        return response.json()
    else:
        print("❌ Failed to create second admin\n")
        return None

def main():
    """Run the complete demo workflow."""
    print("\n" + "="*60)
    print("  INITIAL ADMIN SETUP WORKFLOW DEMO")
    print("="*60)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Expected endpoint: {API_BASE_URL}/auth/setup-initial-admin")
    
    try:
        # Step 1: Create first admin
        admin_data = create_first_admin()
        if not admin_data:
            print("\n❌ Demo failed at step 1\n")
            return
        
        # Step 2: Login
        access_token = login_with_admin()
        if not access_token:
            print("\n❌ Demo failed at step 2\n")
            return
        
        # Step 3: Test duplicate check
        test_duplicate_admin_check()
        
        # Step 4: Create additional admin
        create_additional_admin(access_token)
        
        print_section("✅ DEMO COMPLETED SUCCESSFULLY!")
        print("The initial admin setup workflow is working correctly.\n")
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Cannot connect to {API_BASE_URL}")
        print("Make sure the FastAPI backend is running:\n")
        print("  cd backend")
        print("  source .venv/bin/activate")
        print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000\n")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")

if __name__ == "__main__":
    main()
