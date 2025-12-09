import os
from app.core.database import db
from firebase_admin import auth as firebase_auth
from datetime import datetime, timezone
import httpx
import secrets

USER_COLLECTION = "users"
PASSWORD_RESET_COLLECTION = "password_resets"

# Firebase Web API Key (from Firebase Console -> Project Settings -> Web API Key)
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_API_KEY")


def create_user(name: str, email: str, password: str):
    """
    Register a new user using Firebase Admin SDK.
    """
    try:
        # Create user in Firebase Auth via Admin SDK
        firebase_user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Store additional user data in Firestore
        user_ref = db.collection(USER_COLLECTION).document(email)
        user_ref.set({
            "uid": firebase_user.uid,
            "name": name,
            "email": email,
            "created_at": datetime.utcnow()
        })
        
        return {
            "uid": firebase_user.uid,
            "id": email,
            "name": name,
            "email": email
        }
        
    except firebase_auth.EmailAlreadyExistsError:
        raise ValueError("User already exists")
    except Exception as e:
        raise Exception(f"Failed to create user: {str(e)}")


async def authenticate_user(email: str, password: str):
    """
    Authenticate user via Firebase Auth REST API.
    Returns Firebase ID token and refresh token.
    
    This masks Firebase from the client - they don't use Firebase SDK.
    """
    if not FIREBASE_WEB_API_KEY:
        raise Exception("FIREBASE_API_KEY not configured in environment")
    
    # Firebase Auth REST API endpoint
    request_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(request_url, json=payload)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Get user data from Firestore
            user_ref = db.collection(USER_COLLECTION).document(email)
            doc = user_ref.get()
            
            user_data = None
            if doc.exists:
                user_data = doc.to_dict()
            
            # Return tokens and user info
            return {
                "idToken": data['idToken'],
                "refreshToken": data['refreshToken'],
                "expiresIn": data['expiresIn'],
                "user": {
                    "uid": data['localId'],
                    "id": email,
                    "name": user_data.get("name") if user_data else "",
                    "email": email
                }
            }
            
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return None


async def refresh_user_token(refresh_token: str):
    """
    Refresh an expired ID token using the refresh token.
    This is crucial since Firebase ID tokens expire every hour.
    """
    if not FIREBASE_WEB_API_KEY:
        raise Exception("FIREBASE_API_KEY not configured in environment")
    
    request_url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_WEB_API_KEY}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(request_url, json=payload)
            
            if response.status_code != 200:
                raise ValueError("Invalid refresh token")
            
            data = response.json()
            
            return {
                "idToken": data['id_token'],
                "refreshToken": data['refresh_token'],
                "expiresIn": data['expires_in']
            }
            
        except Exception as e:
            raise ValueError(f"Failed to refresh token: {str(e)}")


def get_user_profile(email: str):
    """Get full user profile from Firestore"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        return None
    
    user = doc.to_dict()
    return {
        "uid": user.get("uid"),
        "id": email,
        "name": user["name"],
        "email": user["email"]
    }


def update_user_profile(email: str, name: str = None, new_email: str = None):
    """Update user profile in Firebase Auth and Firestore"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    user_data = doc.to_dict()
    uid = user_data.get("uid")
    
    # Update Firebase Auth user
    update_params = {}
    if name:
        update_params['display_name'] = name
    if new_email and new_email != email:
        update_params['email'] = new_email
    
    if update_params:
        try:
            firebase_auth.update_user(uid, **update_params)
        except Exception as e:
            raise ValueError(f"Failed to update user: {str(e)}")
    
    # Update Firestore
    if new_email and new_email != email:
        # Check if new email already exists
        new_user_ref = db.collection(USER_COLLECTION).document(new_email)
        if new_user_ref.get().exists:
            raise ValueError("Email already in use")
        
        # Move document to new email key
        user_data["email"] = new_email
        if name:
            user_data["name"] = name
        
        new_user_ref.set(user_data)
        user_ref.delete()
        
        return {
            "uid": uid,
            "id": new_email,
            "name": user_data["name"],
            "email": new_email
        }
    
    if name:
        user_ref.update({"name": name})
    
    updated_doc = user_ref.get()
    updated_data = updated_doc.to_dict()
    
    return {
        "uid": uid,
        "id": email,
        "name": updated_data["name"],
        "email": updated_data["email"]
    }


def change_password(uid: str, new_password: str):
    """
    Change user password via Firebase Admin SDK.
    Note: For security, you should verify the old password first via authenticate_user.
    """
    try:
        firebase_auth.update_user(uid, password=new_password)
        return True
    except Exception as e:
        raise ValueError(f"Failed to update password: {str(e)}")


def create_password_reset_token(email: str):
    """Create a password reset token and store in Firestore"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    # Generate secure random token
    token = secrets.token_urlsafe(32)
    
    # Store token with expiration (1 hour)
    from datetime import timedelta
    reset_ref = db.collection(PASSWORD_RESET_COLLECTION).document(token)
    reset_ref.set({
        "email": email,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=1),
        "used": False
    })
    
    return token


def reset_password_with_token(token: str, new_password: str):
    """Reset password using token"""
    reset_ref = db.collection(PASSWORD_RESET_COLLECTION).document(token)
    doc = reset_ref.get()
    
    if not doc.exists:
        raise ValueError("Invalid or expired reset token")
    
    reset_data = doc.to_dict()
    
    # Check if token is already used
    if reset_data.get("used"):
        raise ValueError("Reset token has already been used")
    
    # Check if token is expired (both must be timezone-aware for comparison)
    expires_at = reset_data["expires_at"]
    now = datetime.now(timezone.utc)
    if now > expires_at:
        raise ValueError("Reset token has expired")
    
    # Get user
    email = reset_data["email"]
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    user_data = doc.to_dict()
    uid = user_data.get("uid")
    
    # If uid not in Firestore (legacy users), get it from Firebase Auth
    if not uid:
        try:
            user = firebase_auth.get_user_by_email(email)
            uid = user.uid
            # Update Firestore with uid for future use
            user_ref.update({"uid": uid})
        except Exception as e:
            raise ValueError(f"Failed to get user from Firebase: {str(e)}")
    
    # Update password in Firebase Auth
    try:
        firebase_auth.update_user(uid, password=new_password)
        
        # Mark token as used
        reset_ref.update({"used": True})
        
        return True
    except Exception as e:
        raise ValueError(f"Failed to reset password: {str(e)}")


async def delete_user_account(email: str, password: str):
    """Delete user account from Firebase Auth and Firestore"""
    # First verify password
    auth_result = await authenticate_user(email, password)
    if not auth_result:
        raise ValueError("Incorrect password")
    
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    user_data = doc.to_dict()
    uid = user_data.get("uid")
    
    try:
        # Delete from Firebase Auth
        firebase_auth.delete_user(uid)
        
        # Delete from Firestore
        user_ref.delete()
        
        return True
    except Exception as e:
        raise ValueError(f"Failed to delete user: {str(e)}")