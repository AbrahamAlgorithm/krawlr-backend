"""
Website crawling and sitemap discovery service.

Complete sitemap discovery implementation with async HTTP, proper error handling,
and hierarchical URL tree building.
"""

from __future__ import annotations

from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from collections import deque
import logging
import asyncio

from app.services.utils.http_client import http_client

logger = logging.getLogger(__name__)

# Common sitemap locations to check
COMMON_SITEMAP_PATHS = [
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap/sitemap.xml',
    '/sitemap1.xml',
    '/wp-sitemap.xml'
]

# Concurrency limit for sitemap fetching
SITEMAP_CONCURRENCY = asyncio.Semaphore(5)


async def fetch_sitemap(url: str, timeout: float = 10.0) -> List[str]:
    """
    Fetch and parse an XML sitemap, returning list of URLs.
    
    Handles both:
    - Standard sitemaps with <url><loc>...</loc></url>
    - Sitemap index files with <sitemap><loc>...</loc></sitemap>
    
    Args:
        url: Sitemap URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        List of discovered URLs
        
    Implementation Details:
        - Fetches raw XML via async HTTP GET
        - Parses with xml.etree.ElementTree
        - Extracts <loc> tags (URL locations)
        - Handles XML namespaces (xmlns)
        - Recursively follows sitemap index references
    """
    async with SITEMAP_CONCURRENCY:
        try:
            logger.info(f"Fetching sitemap: {url}")
            
            # Async HTTP GET with timeout
            response = await http_client.get(url, timeout=timeout)
            if not response or response.status_code != 200:
                logger.warning(f"Failed to fetch sitemap {url}: status {response.status_code if response else 'None'}")
                return []
            
            content = response.content
            
            # Parse XML
            root = ET.fromstring(content)
            
            # Handle XML namespaces (sitemap xmlns)
            # Namespace format: {http://www.sitemaps.org/schemas/sitemap/0.9}
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            urls = []
            
            # Check if this is a sitemap index (contains <sitemap> tags)
            sitemap_refs = root.findall('.//sm:sitemap/sm:loc', ns)
            if sitemap_refs:
                logger.info(f"Found sitemap index with {len(sitemap_refs)} sitemaps")
                # Recursively fetch each referenced sitemap
                tasks = []
                for loc in sitemap_refs:
                    sitemap_url = loc.text.strip() if loc.text else None
                    if sitemap_url:
                        logger.info(f"Following sitemap reference: {sitemap_url}")
                        tasks.append(fetch_sitemap(sitemap_url, timeout))
                
                # Fetch all sitemaps concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, list):
                        urls.extend(result)
            else:
                # Standard sitemap: extract <url><loc> tags
                url_locs = root.findall('.//sm:url/sm:loc', ns)
                urls = [loc.text.strip() for loc in url_locs if loc.text]
                logger.info(f"Extracted {len(urls)} URLs from sitemap")
            
            return urls
            
        except ET.ParseError as e:
            logger.warning(f"Failed to parse sitemap XML {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching sitemap {url}: {e}")
            return []


async def discover_sitemaps(base_url: str, timeout: float = 10.0) -> List[str]:
    """
    Discover sitemap URLs for a domain by checking common locations and robots.txt.
    
    Discovery order:
    1. Try /sitemap.xml
    2. Try /sitemap_index.xml
    3. Parse /robots.txt for Sitemap: directives
    
    Args:
        base_url: Base URL of website (e.g., https://example.com)
        timeout: Request timeout
        
    Returns:
        List of discovered sitemap URLs
        
    Example robots.txt parsing:
        User-agent: *
        Disallow: /admin
        Sitemap: https://example.com/sitemap.xml
        Sitemap: https://example.com/news-sitemap.xml
    """
    discovered = []
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    logger.info(f"Discovering sitemaps for: {base}")
    
    # 1. Check common sitemap paths concurrently
    async def check_sitemap(path: str) -> Optional[str]:
        sitemap_url = urljoin(base, path)
        try:
            response = await http_client.head(sitemap_url, timeout=timeout)
            if response and response.status_code == 200:
                logger.info(f"✓ Found sitemap: {sitemap_url}")
                return sitemap_url
        except Exception:
            pass  # Silently skip failed attempts
        return None
    
    # Check all common paths concurrently
    tasks = [check_sitemap(path) for path in COMMON_SITEMAP_PATHS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, str):
            discovered.append(result)
    
    # 2. Check robots.txt for Sitemap directives
    robots_url = urljoin(base, '/robots.txt')
    try:
        logger.info(f"Checking robots.txt: {robots_url}")
        response = await http_client.get(robots_url, timeout=timeout)
        if response and response.status_code == 200:
            robots_text = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
            # Parse each line
            for line in robots_text.splitlines():
                line = line.strip()
                # Look for: Sitemap: https://example.com/sitemap.xml
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    if sitemap_url not in discovered:
                        logger.info(f"✓ Found sitemap in robots.txt: {sitemap_url}")
                        discovered.append(sitemap_url)
    except Exception as e:
        logger.warning(f"Could not fetch robots.txt: {e}")
    
    logger.info(f"Discovered {len(discovered)} sitemap(s)")
    return discovered


async def build_sitemap_from_navigation(base_url: str, max_urls: int = 100) -> List[str]:
    """
    Build a sitemap by crawling header/footer navigation links.
    
    This is a fallback when no official sitemap exists.
    
    Strategy:
    1. Fetch homepage
    2. Find header and footer sections
    3. Extract all internal links
    4. Follow those links one level deep (optional)
    
    Args:
        base_url: The website base URL
        max_urls: Maximum URLs to collect
    
    Returns:
        List of discovered URLs
    """
    print(f"  🧭 Building sitemap from navigation (no official sitemap found)...")
    
    from bs4 import BeautifulSoup
    from app.services.utils.validators import is_same_domain, make_absolute_url
    
    # Fetch homepage
    html = await http_client.get_text(base_url)
    if not html:
        print(f"    ❌ Could not fetch homepage")
        return [base_url]
    
    soup = BeautifulSoup(html, 'html.parser')
    parsed_base = urlparse(base_url)
    urls: Set[str] = set()
    
    # Add homepage
    urls.add(base_url.rstrip("/"))
    
    # Strategy 1: Find header and footer
    # Common selectors: <header>, <footer>, <nav>, class="header", class="footer"
    navigation_sections = []
    
    # Find by tag
    navigation_sections.extend(soup.find_all(['header', 'footer', 'nav']))
    
    # Find by common class names
    navigation_sections.extend(soup.find_all(class_=lambda x: x and any(
        keyword in str(x).lower() 
        for keyword in ['header', 'footer', 'nav', 'menu', 'navigation']
    )))
    
    print(f"    📍 Found {len(navigation_sections)} navigation sections")
    
    # Extract links from navigation sections
    for section in navigation_sections:
        links = section.find_all('a', href=True)
        
        for link in links:
            if len(urls) >= max_urls:
                break
            
            href = link.get('href')
            
            # Skip non-HTTP links
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Make absolute URL
            absolute_url = make_absolute_url(base_url, href)
            
            # Only add if same domain
            if is_same_domain(base_url, absolute_url):
                urls.add(absolute_url.rstrip("/"))
    
    # Strategy 2: If we didn't find enough, crawl all links on homepage
    if len(urls) < 20:  # Arbitrary threshold
        print(f"    🔍 Not enough navigation links, checking all homepage links...")
        
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            if len(urls) >= max_urls:
                break
            
            href = link.get('href')
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            absolute_url = make_absolute_url(base_url, href)
            if is_same_domain(base_url, absolute_url):
                urls.add(absolute_url.rstrip("/"))
    
    print(f"  ✅ Built sitemap with {len(urls)} URLs from navigation")
    return list(urls)


async def get_all_sitemap_urls(
    base_url: str,
    max_urls: int = 500,
    max_sitemaps: int = 10
) -> List[str]:
    """
    Main entry point: Discover sitemaps, extract URLs, with fallback to navigation crawling.
    
    Full workflow:
    1. Normalize base_url
    2. Discover sitemap URLs (check /sitemap.xml, robots.txt, etc.)
    3. Fetch and parse each sitemap XML (with recursive sitemap index support)
    4. Deduplicate and limit URLs
    5. Fallback to navigation crawling if no sitemaps found
    
    Args:
        base_url: Target website URL
        max_urls: Maximum URLs to return (prevents memory issues)
        max_sitemaps: Maximum number of sitemaps to discover (default: 10)
        
    Returns:
        List of discovered URLs
    
    Example usage:
        urls = await get_all_sitemap_urls("https://stripe.com", max_urls=200)
        print(f"Found {len(urls)} URLs")
    """
    logger.info(f"Starting sitemap crawl for: {base_url}")
    
    # Normalize base URL (ensure scheme)
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = f"https://{base_url}"
        parsed = urlparse(base_url)
    
    if not parsed.netloc:
        raise ValueError("Base URL must include a domain (e.g., https://example.com)")
    
    # Step 1: Discover sitemap URLs
    sitemap_urls = await discover_sitemaps(base_url)
    
    if not sitemap_urls:
        logger.warning(f"No sitemaps found for {base_url}, falling back to navigation crawling")
        print(f"  ⚠️  No official sitemap found or empty sitemap")
        return await build_sitemap_from_navigation(base_url, max_urls=max_urls)
    
    # Step 2: Fetch and parse all sitemaps concurrently
    print(f"  📊 Parsing {len(sitemap_urls)} sitemap(s)...")
    
    # Limit to max_sitemaps
    sitemap_urls = sitemap_urls[:max_sitemaps]
    
    # Fetch all sitemaps concurrently
    tasks = [fetch_sitemap(url) for url in sitemap_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect all URLs
    all_urls = []
    for i, result in enumerate(results):
        if isinstance(result, list):
            all_urls.extend(result)
            logger.info(f"Sitemap {sitemap_urls[i]}: {len(result)} URLs")
        elif isinstance(result, Exception):
            logger.error(f"Failed to parse sitemap {sitemap_urls[i]}: {result}")
    
    # Step 3: Deduplicate
    unique_urls = list(set(all_urls))
    logger.info(f"Total unique URLs: {len(unique_urls)}")
    
    # Step 4: Limit to max_urls
    if len(unique_urls) > max_urls:
        logger.warning(f"Limiting to {max_urls} URLs (found {len(unique_urls)})")
        unique_urls = unique_urls[:max_urls]
    
    print(f"  ✅ Collected {len(unique_urls)} URLs from sitemaps")
    
    if not unique_urls:
        logger.warning("Sitemaps were empty, falling back to navigation crawling")
        print(f"  ⚠️  No official sitemap found or empty sitemap")
        return await build_sitemap_from_navigation(base_url, max_urls=max_urls)
    
    logger.info(f"✓ Crawl complete: {len(unique_urls)} URLs, {len(sitemap_urls)} sitemaps")
    
    return unique_urls