from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth as firebase_auth
import os

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours

security = HTTPBearer()

def create_access_token(data: dict):
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(authorization: str = Header(...)):
    """
    Dependency to extract and verify current user from Firebase ID token.
    Expects: Authorization: Bearer <id_token>
    """
    from app.core.database import db
    
    # Validate Authorization header format
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    
    try:
        # Verify the Firebase ID token using Admin SDK
        # This checks signature and expiration locally (very fast)
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        if not email:
            raise credentials_exception
        
        # Fetch additional user data from Firestore
        user_ref = db.collection("users").document(email)
        doc = user_ref.get()
        
        if doc.exists:
            user_data = doc.to_dict()
            return {
                "uid": uid,
                "id": email,
                "name": user_data.get("name"),
                "email": email
            }
        else:
            # Return basic Firebase Auth data if no Firestore doc
            return {
                "uid": uid,
                "id": email,
                "name": decoded_token.get("name", ""),
                "email": email
            }
        
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your token."
        )
    except Exception as e:
        raise credentials_exception