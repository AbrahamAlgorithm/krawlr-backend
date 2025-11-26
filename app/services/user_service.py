from app.core.database import db
from app.utils.security import hash_password, verify_password
from app.core.auth import create_access_token
from datetime import datetime, timedelta
import secrets

USER_COLLECTION = "users"
PASSWORD_RESET_COLLECTION = "password_resets"

def create_user(name: str, email: str, password: str):
    """Create a new user in Firestore"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if doc.exists:
        raise ValueError("User already exists")
    
    hashed = hash_password(password)
    
    user_ref.set({
        "name": name,
        "email": email,
        "password": hashed
    })
    
    return {"id": email, "name": name, "email": email}


def authenticate_user(email: str, password: str):
    """Authenticate user and return JWT token"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        return None
    
    user = doc.to_dict()
    
    if not verify_password(password, user["password"]):
        return None
    
    token = create_access_token(data={"sub": email})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": email,
            "name": user["name"],
            "email": user["email"]  
        }
    }


def get_user_profile(email: str):
    """Get full user profile from Firestore"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        return None
    
    user = doc.to_dict()
    return {
        "id": email,
        "name": user["name"],
        "email": user["email"]
    }


def update_user_profile(email: str, name: str = None, new_email: str = None):
    """Update user profile"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    updates = {}
    if name:
        updates["name"] = name
    if new_email and new_email != email:
        # Check if new email already exists
        new_user_ref = db.collection(USER_COLLECTION).document(new_email)
        if new_user_ref.get().exists:
            raise ValueError("Email already in use")
        
        # Move user data to new email document
        user_data = doc.to_dict()
        user_data["email"] = new_email
        if name:
            user_data["name"] = name
        
        new_user_ref.set(user_data)
        user_ref.delete()
        
        return {"id": new_email, "name": user_data["name"], "email": new_email}
    
    if updates:
        user_ref.update(updates)
    
    updated_doc = user_ref.get()
    user_data = updated_doc.to_dict()
    
    return {"id": email, "name": user_data["name"], "email": user_data["email"]}


def change_password(email: str, old_password: str, new_password: str):
    """Change user password"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    user = doc.to_dict()
    
    # Verify old password
    if not verify_password(old_password, user["password"]):
        raise ValueError("Incorrect current password")
    
    # Hash and update new password
    hashed = hash_password(new_password)
    user_ref.update({"password": hashed})
    
    return True


def create_password_reset_token(email: str):
    """Create a password reset token"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    # Generate secure random token
    token = secrets.token_urlsafe(32)
    
    # Store token with expiration (1 hour)
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
    
    # Check if token is expired
    if datetime.utcnow() > reset_data["expires_at"]:
        raise ValueError("Reset token has expired")
    
    # Update password
    email = reset_data["email"]
    user_ref = db.collection(USER_COLLECTION).document(email)
    hashed = hash_password(new_password)
    user_ref.update({"password": hashed})
    
    # Mark token as used
    reset_ref.update({"used": True})
    
    return True


def delete_user_account(email: str, password: str):
    """Delete user account"""
    user_ref = db.collection(USER_COLLECTION).document(email)
    doc = user_ref.get()
    
    if not doc.exists:
        raise ValueError("User not found")
    
    user = doc.to_dict()
    
    # Verify password before deletion
    if not verify_password(password, user["password"]):
        raise ValueError("Incorrect password")
    
    user_ref.delete()
    return True