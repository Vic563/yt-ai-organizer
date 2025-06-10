#!/usr/bin/env python3
"""Script to create an admin user for the YouTube AI Organizer"""

import sqlite3
import os
import sys
from getpass import getpass
from auth import UserCreate, create_user
from security import get_password_hash
from database import init_database
from database_migrations import run_migrations

def create_admin_user():
    """Create an admin user interactively"""
    print("YouTube AI Organizer - Create Admin User")
    print("=" * 40)
    
    # Initialize database
    print("Initializing database...")
    init_database()
    run_migrations()
    
    # Get user input
    while True:
        username = input("Enter admin username: ").strip()
        if len(username) >= 3 and username.isalnum():
            break
        print("Username must be at least 3 characters and alphanumeric only")
    
    while True:
        email = input("Enter admin email: ").strip()
        if "@" in email and "." in email:
            break
        print("Please enter a valid email address")
    
    while True:
        password = getpass("Enter admin password: ")
        if len(password) >= 8:
            confirm = getpass("Confirm password: ")
            if password == confirm:
                break
            else:
                print("Passwords do not match")
        else:
            print("Password must be at least 8 characters")
    
    # Create the user
    try:
        # First create as regular user
        user_data = UserCreate(
            username=username,
            email=email,
            password=password
        )
        user = create_user(user_data)
        
        # Then update to admin
        db_path = os.path.join(os.path.dirname(__file__), "data", "project_insight.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_admin = TRUE WHERE username = ?",
            (username,)
        )
        conn.commit()
        conn.close()
        
        print(f"\n✓ Admin user '{username}' created successfully!")
        print("\nYou can now login with these credentials at http://localhost:3000/login")
        
    except Exception as e:
        print(f"\n✗ Error creating admin user: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_admin_user()