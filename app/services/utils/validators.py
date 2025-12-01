from urllib.parse import urlparse, urljoin
import re
from typing import Optional

def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except:
        return False


def extract_domain(url: str) -> Optional[str]:
    """
    Extract just the domain from a URL.
    
    Example:
        extract_domain("https://www.stripe.com/about") → "stripe.com"
        extract_domain("https://blog.example.com/post") → "example.com"
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove 'www.' if present
        # "www.stripe.com" → "stripe.com"
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    except:
        return None


def normalize_url(url: str) -> str:
    """
    Clean up a URL (remove fragments, normalize slashes, etc.).
    
    Example:
        normalize_url("https://stripe.com/about#team") → "https://stripe.com/about"
        normalize_url("https://stripe.com/about/") → "https://stripe.com/about"
    """
    try:
        # Parse the URL
        parsed = urlparse(url)
        
        # Rebuild without fragment (#section) and with normalized path
        clean_path = parsed.path.rstrip('/')  # Remove trailing slash
        
        normalized = f"{parsed.scheme}://{parsed.netloc}{clean_path}"
        
        # Add query string if present
        if parsed.query:
            normalized += f"?{parsed.query}"
        
        return normalized
    except:
        return url


def get_company_name_from_domain(domain: str) -> str:
    """
    Extract a company name from a domain.
    
    Example:
        get_company_name_from_domain("stripe.com") → "Stripe"
        get_company_name_from_domain("openai.com") → "OpenAI"
    """
    # Remove TLD (.com, .org, etc.)
    name = domain.split('.')[0]
    
    # Capitalize first letter
    return name.capitalize()


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs belong to the same domain.
    
    Example:
        is_same_domain("https://stripe.com/about", "https://stripe.com/products") → True
        is_same_domain("https://stripe.com", "https://google.com") → False
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    
    return domain1 == domain2 if domain1 and domain2 else False


def make_absolute_url(base_url: str, relative_url: str) -> str:
    """
    Convert a relative URL to an absolute URL.
    
    Example:
        make_absolute_url("https://stripe.com", "/about") → "https://stripe.com/about"
        make_absolute_url("https://stripe.com/products", "../about") → "https://stripe.com/about"
    """
    return urljoin(base_url, relative_url)