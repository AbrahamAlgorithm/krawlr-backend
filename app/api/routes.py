from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.schemas.user import (
    UserCreate, UserLogin, UserUpdate, 
    PasswordChange, PasswordResetRequest, PasswordResetConfirm,
    TokenRefresh, DeleteAccount
)
from app.services.user_service import (
    create_user, 
    authenticate_user,
    refresh_user_token,
    get_user_profile,
    update_user_profile,
    change_password,
    delete_user_account,
    create_password_reset_token,
    reset_password_with_token
)
from app.services.email_service import send_password_reset_email

router = APIRouter()

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================
# Note: Scraping endpoints have been moved to app/api/scraping_routes.py
# and are now available at /api/v1/scrape/*
# ============================================================================

@router.post("/register")
async def register_user(data: UserCreate):
    """
    Register a new user.
    Firebase is completely masked - client doesn't know it exists.
    """
    try:
        user = create_user(data.name, data.email, data.password)
        return {
            "message": "User created successfully. Please login to continue.",
            "user": user
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login")
async def login_user(data: UserLogin):
    """
    Login user via Firebase Auth REST API (masked from client).
    Returns Firebase ID token and refresh token.
    
    Client should store both tokens:
    - idToken: Send in Authorization header for API requests
    - refreshToken: Use to get new idToken when it expires (every hour)
    """
    result = await authenticate_user(data.email, data.password)
    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    return {
        "message": "Login successful",
        "token": result['idToken'],
        "refreshToken": result['refreshToken'],
        "expiresIn": result['expiresIn'],
        "user": result['user']
    }


@router.post("/refresh-token")
async def refresh_token(data: TokenRefresh):
    """
    Refresh an expired ID token.
    
    Firebase ID tokens expire every hour. When client gets 401 with 
    "Token has expired" message, they should call this endpoint with 
    their refresh token to get a new ID token.
    """
    try:
        result = await refresh_user_token(data.refreshToken)
        return {
            "message": "Token refreshed successfully",
            "token": result['idToken'],
            "refreshToken": result['refreshToken'],
            "expiresIn": result['expiresIn']
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/user-profile")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current logged-in user info from Firebase Auth token.
    Send token in header: Authorization: Bearer <idToken>
    """
    return {"user": current_user}


@router.get("/get-profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get full user profile from Firestore"""
    profile = get_user_profile(current_user["email"])
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"user": profile}


@router.put("/update-profile")
async def update_profile(
    data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile in Firebase Auth and Firestore"""
    try:
        updated_user = update_user_profile(
            current_user["email"],
            name=data.name,
            new_email=data.email
        )
        return {
            "message": "Profile updated successfully",
            "user": updated_user
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Profile update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-password")
async def change_user_password(
    data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """
    Change user password.
    Verifies old password first for security.
    """
    try:
        # Verify old password
        auth_result = await authenticate_user(current_user["email"], data.old_password)
        if not auth_result:
            raise ValueError("Incorrect current password")
        
        # Update to new password
        change_password(current_user["uid"], data.new_password)
        
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Password change error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest):
    """
    Request password reset - sends email with reset token.
    Completely masks Firebase from client.
    """
    try:
        # Generate reset token
        token = create_password_reset_token(data.email)
        
        # Send email with reset link
        email_sent = await send_password_reset_email(data.email, token)
        
        if not email_sent:
            raise HTTPException(status_code=500, detail="Failed to send reset email")
        
        return {
            "message": "Password reset email sent. Please check your inbox.",
            "email": data.email
        }
    except ValueError:
        # For security, return success even if user doesn't exist
        # This prevents email enumeration attacks
        return {
            "message": "If an account exists with that email, a reset link has been sent.",
            "email": data.email
        }
    except Exception as e:
        print(f"Forgot password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reset-password")
async def reset_password_page(token: str):
    """Verify reset token is valid (for rendering password reset form)"""
    try:
        from app.core.database import db
        from datetime import datetime, timezone
        
        reset_ref = db.collection('password_resets').document(token)
        doc = reset_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        reset_data = doc.to_dict()
        
        # Check if already used
        if reset_data.get("used"):
            raise HTTPException(status_code=400, detail="Reset token has already been used")
        
        # Check if expired
        expires_at = reset_data["expires_at"]
        now = datetime.now(timezone.utc)
        if now > expires_at:
            raise HTTPException(status_code=400, detail="Reset token has expired")
        
        return {
            "message": "Token is valid",
            "email": reset_data["email"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm):
    """Reset password using token from email"""
    try:
        reset_password_with_token(data.token, data.new_password)
        return {
            "message": "Password has been reset successfully. You can now login with your new password."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/delete-account")
async def delete_account(
    data: DeleteAccount,
    current_user: dict = Depends(get_current_user)
):
    """Delete user account (requires password confirmation)"""
    try:
        await delete_user_account(current_user["email"], data.password)
        return {"message": "Account deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Account deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")