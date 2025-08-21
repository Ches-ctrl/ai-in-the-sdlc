#!/usr/bin/env python3
"""
Test script to debug Supabase authentication issues
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

def test_supabase_connection():
    """Test basic Supabase connection and authentication"""
    
    # Load environment variables
    load_dotenv()
    
    # Get environment variables
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    print("🔍 Testing Supabase Authentication")
    print("=" * 50)
    
    # Check environment variables
    print(f"SUPABASE_URL: {'✅ Set' if SUPABASE_URL else '❌ Missing'}")
    print(f"SUPABASE_ANON_KEY: {'✅ Set' if SUPABASE_ANON_KEY else '❌ Missing'}")
    
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("\n❌ Missing required environment variables!")
        return False
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("\n✅ Supabase client created successfully")
        
        # Test connection by getting the current session
        try:
            session = supabase.auth.get_session()
            print(f"✅ Connection test successful - Session: {session}")
        except Exception as e:
            print(f"⚠️  No active session (this is normal): {e}")
        
        # Test sign-up with a test user (this might fail if user exists)
        test_email = "testuser.hackathon@gmail.com"  # Use a more realistic email
        test_password = "SecurePassword123!"
        
        print(f"\n🧪 Testing sign-up with {test_email}...")
        try:
            result = supabase.auth.sign_up({
                "email": test_email,
                "password": test_password
            })
            print(f"✅ Sign-up test successful: {result}")
        except Exception as e:
            print(f"❌ Sign-up test failed: {e}")
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response'):
                print(f"Response status: {getattr(e.response, 'status_code', 'N/A')}")
                print(f"Response text: {getattr(e.response, 'text', 'N/A')}")
            print("This might indicate the issue with authentication")
        
        # Test sign-in 
        print(f"\n🧪 Testing sign-in with {test_email}...")
        try:
            result = supabase.auth.sign_in_with_password({
                "email": test_email,
                "password": test_password
            })
            print(f"✅ Sign-in test successful: {result}")
        except Exception as e:
            print(f"❌ Sign-in test failed: {e}")
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response'):
                print(f"Response status: {getattr(e.response, 'status_code', 'N/A')}")
                print(f"Response text: {getattr(e.response, 'text', 'N/A')}")
            print("This is likely the source of your 400 error")
            
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create Supabase client: {e}")
        return False

if __name__ == "__main__":
    success = test_supabase_connection()
    sys.exit(0 if success else 1)
