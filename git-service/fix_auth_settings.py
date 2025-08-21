#!/usr/bin/env python3
"""
Script to test authentication with admin privileges and potentially fix auth settings
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

def test_admin_auth():
    """Test authentication with admin/service role key"""
    
    load_dotenv()
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    print("🔧 Testing Admin Authentication")
    print("=" * 50)
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Missing admin credentials")
        return False
    
    try:
        # Create admin client with service role key
        admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("✅ Admin client created successfully")
        
        # Test getting user info with admin privileges
        try:
            # List users (this requires service role)
            result = admin_client.auth.admin.list_users()
            print(f"✅ Admin access confirmed - Found {len(result.users)} users")
            
            # Find our test user
            test_email = "testuser.hackathon@gmail.com"
            test_user = None
            for user in result.users:
                if user.email == test_email:
                    test_user = user
                    break
            
            if test_user:
                print(f"✅ Found test user: {test_user.email}")
                print(f"   Email confirmed: {test_user.email_confirmed_at is not None}")
                print(f"   User ID: {test_user.id}")
                
                # If email not confirmed, we can confirm it with admin privileges
                if not test_user.email_confirmed_at:
                    print("🔧 Attempting to confirm email with admin privileges...")
                    try:
                        admin_client.auth.admin.update_user_by_id(
                            test_user.id,
                            {"email_confirm": True}
                        )
                        print("✅ Email confirmed successfully!")
                        return True
                    except Exception as e:
                        print(f"❌ Failed to confirm email: {e}")
                        return False
                else:
                    print("✅ Email already confirmed!")
                    return True
            else:
                print(f"⚠️  Test user {test_email} not found")
                return False
                
        except Exception as e:
            print(f"❌ Admin operations failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to create admin client: {e}")
        return False

if __name__ == "__main__":
    success = test_admin_auth()
    
    if success:
        print("\n🎉 Authentication should now work!")
        print("Try running your application again.")
    else:
        print("\n⚠️  Consider disabling email confirmation in Supabase Dashboard")
        print("Authentication → Settings → Disable 'Enable email confirmations'")

