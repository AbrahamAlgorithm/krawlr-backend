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
from app.services.scraping.orchestrator import scraping_orchestrator
from app.services.utils.validators import normalize_url, extract_domain
from pydantic import BaseModel

router = APIRouter()

# ============================================================================
# SCRAPING ENDPOINTS
# ============================================================================

class ScrapeRequest(BaseModel):
    url: str

class ScrapeResponse(BaseModel):
    job_id: str
    url: str
    domain: str
    status: str
    message: str

@router.post("/scrape", response_model=ScrapeResponse)
async def start_scraping(request: ScrapeRequest, current_user: dict = Depends(get_current_user)):
    """
    Start a comprehensive scraping job for a company URL.
    
    This endpoint initiates a background task that:
    - Scrapes company identity from the website
    - Searches for founders and executives on LinkedIn
    - Extracts financial data from SEC EDGAR (if public)
    - Searches for funding information
    - Finds competitors
    - Gathers recent news mentions
    
    Returns a job_id that can be used to check progress.
    """
    try:
        # Validate and normalize URL
        url = normalize_url(request.url)
        domain = extract_domain(url)
        
        # Check if recently scraped (cache)
        from app.services.scraping.firestore_service import firestore_service
        is_cached = await firestore_service.is_recently_scraped(domain, hours=24)
        
        if is_cached:
            # Return cached data immediately
            cached_data = await firestore_service.get_company_data(domain)
            return {
                "job_id": "cached",
                "url": url,
                "domain": domain,
                "status": "completed",
                "message": "Returning cached data from recent scrape",
                "data": cached_data
            }
        
        # Start new scraping job
        job_id = await scraping_orchestrator.start_scraping_job(url, current_user['uid'])
        
        return {
            "job_id": job_id,
            "url": url,
            "domain": domain,
            "status": "pending",
            "message": f"Scraping job started. Use job_id to check progress at GET /scrape/{job_id}"
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Scraping error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start scraping job")

@router.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get the status and results of a scraping job.
    
    Status values:
    - pending: Job is queued
    - in_progress: Currently scraping (check progress field)
    - completed: Scraping finished (result field contains data)
    - failed: Scraping failed (error field contains error message)
    """
    job_data = await scraping_orchestrator.get_job_status(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Only return job if user owns it (or is admin in future)
    if job_data.get('user_id') != current_user['uid']:
        raise HTTPException(status_code=403, detail="Unauthorized to view this job")
    
    return job_data

@router.get("/company/{domain}")
async def get_company_data(domain: str, current_user: dict = Depends(get_current_user)):
    """
    Get cached company data by domain.
    Returns None if not previously scraped.
    """
    company_data = await scraping_orchestrator.get_cached_company_data(domain)
    
    if not company_data:
        raise HTTPException(status_code=404, detail="Company data not found. Please initiate a scrape first.")
    
    return company_data

# ============================================================================
# AUTHENTICATION ENDPOINTS
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