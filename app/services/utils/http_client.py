import httpx
from typing import Optional, Dict
import asyncio
from aiolimiter import AsyncLimiter

class HTTPClient:
    """
    A reusable HTTP client for making web requests.
    
    Think of this as a web browser that:
    - Fetches web pages
    - Handles errors gracefully
    - Prevents getting blocked by websites
    - Pretends to be a real browser (user agent)
    """
    
    def __init__(self):
        # Rate limiter: Only allow 10 requests per second
        self.limiter = AsyncLimiter(max_rate=10, time_period=1)
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    
    async def get(self, url: str, headers: Optional[Dict] = None, retries: int = 3) -> Optional[httpx.Response]:
        """
        Fetch a web page (like clicking a link in your browser).
        """
        merged_headers = {**self.headers, **(headers or {})}
        
        for attempt in range(retries):
            try:
                async with self.limiter:
                    async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                        response = await client.get(url, headers=merged_headers)
                        response.raise_for_status()
                        return response
            
            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP error fetching {url}: {e.response.status_code}")
                if e.response.status_code < 500:
                    return None
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
            
            except httpx.TimeoutException:
                print(f"⏱️ Timeout fetching {url} (attempt {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
            
            except Exception as e:
                print(f"❌ Error fetching {url}: {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    async def get_text(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch text content from a URL (for XML, robots.txt, etc.).
        
        This is simpler than get() - just returns the text content.
        
        Args:
            url: The URL to fetch
            retries: Number of retry attempts
        
        Returns:
            Text content or None if failed
        """
        response = await self.get(url, retries=retries)
        return response.text if response else None
    
    async def post(self, url: str, data: Dict, headers: Optional[Dict] = None) -> Optional[httpx.Response]:
        """Send data to a website (like submitting a form)."""
        merged_headers = {**self.headers, **(headers or {})}
        
        try:
            async with self.limiter:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=data, headers=merged_headers)
                    response.raise_for_status()
                    return response
        
        except Exception as e:
            print(f"❌ Error posting to {url}: {str(e)}")
            return None


# Create a shared instance
http_client = HTTPClient()