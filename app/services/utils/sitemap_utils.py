"""
Sitemap discovery and parsing utilities.
"""

from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from collections import deque
import logging

from app.services.utils.http_client import http_client

logger = logging.getLogger(__name__)

SITEMAP_CANDIDATES = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/sitemap1.xml",
    "/wp-sitemap.xml",
)


async def discover_sitemaps(base_url: str, max_sitemaps: int = 5) -> List[str]:
    """Discover sitemap URLs from common locations and robots.txt."""
    print(f"  🔍 Discovering sitemaps for {base_url}...")
    
    discovered: List[str] = []
    seen: Set[str] = set()
    
    async def _try_add(url: str) -> bool:
        """Try to add a URL as a valid sitemap."""
        if url in seen:
            return False
        
        seen.add(url)
        
        text = await http_client.get_text(url)
        if not text:
            logger.debug(f"Sitemap candidate unavailable: {url}")
            return False
        
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            logger.debug(f"Candidate is not valid XML: {url}")
            return False
        
        tag = root.tag.lower()
        if tag.endswith("urlset") or tag.endswith("sitemapindex"):
            discovered.append(url)
            print(f"    ✅ Found sitemap: {url}")
            return True
        else:
            logger.debug(f"XML file but not a sitemap: {url} (tag: {tag})")
            return False
    
    # Step 1: Try common sitemap locations
    for path in SITEMAP_CANDIDATES:
        if len(discovered) >= max_sitemaps:
            break
        sitemap_url = urljoin(base_url, path)
        await _try_add(sitemap_url)
    
    # Step 2: Check robots.txt
    robots_url = urljoin(base_url, "/robots.txt")
    robots_text = await http_client.get_text(robots_url)
    
    if robots_text:
        print(f"    📄 Checking robots.txt for sitemap directives...")
        for line in robots_text.splitlines():
            if len(discovered) >= max_sitemaps:
                break
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                await _try_add(sitemap_url)
    
    print(f"  ✅ Discovered {len(discovered)} sitemap(s)")
    return discovered


def _extract_text(element: ET.Element, tag_name: str) -> Optional[str]:
    """Extract text from an XML element's child by tag name."""
    for child in element:
        if child.tag.lower().endswith(tag_name.lower()):
            return (child.text or "").strip()
    return None


async def parse_sitemap_urls(
    sitemap_url: str,
    base_netloc: str,
    visited: Set[str],
    max_urls: int = 500,
    max_sitemaps: int = 10
) -> Set[str]:
    """Parse a sitemap and extract all URLs, recursively handling sitemap indexes."""
    urls: Set[str] = set()
    sitemap_queue: deque[str] = deque([sitemap_url])
    
    while sitemap_queue and len(urls) < max_urls and len(visited) < max_sitemaps:
        current_sitemap = sitemap_queue.popleft()
        
        if current_sitemap in visited:
            continue
        
        visited.add(current_sitemap)
        print(f"    📖 Parsing sitemap: {current_sitemap}")
        
        xml_text = await http_client.get_text(current_sitemap)
        if not xml_text:
            logger.warning(f"Unable to fetch sitemap: {current_sitemap}")
            continue
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Invalid sitemap XML at {current_sitemap}: {e}")
            continue
        
        tag = root.tag.lower()
        
        if tag.endswith("sitemapindex"):
            print(f"      ℹ️  This is a sitemap index (contains other sitemaps)")
            for sitemap_element in root:
                loc = _extract_text(sitemap_element, "loc")
                if not loc:
                    continue
                parsed = urlparse(loc)
                if not parsed.netloc:
                    loc = urljoin(current_sitemap, loc)
                    parsed = urlparse(loc)
                if parsed.netloc and parsed.netloc == base_netloc:
                    sitemap_queue.append(loc)
        
        elif tag.endswith("urlset"):
            print(f"      ℹ️  This is a URL set (contains page URLs)")
            for url_element in root:
                loc = _extract_text(url_element, "loc")
                if not loc:
                    continue
                parsed = urlparse(loc)
                if not parsed.netloc:
                    loc = urljoin(current_sitemap, loc)
                    parsed = urlparse(loc)
                if parsed.netloc != base_netloc:
                    continue
                urls.add(loc.rstrip("/"))
                if len(urls) >= max_urls:
                    print(f"      ⚠️  Reached URL cap of {max_urls}")
                    break
        else:
            logger.debug(f"Unexpected sitemap root tag: {tag}")
    
    return urls


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
    High-level function: Discover and parse all sitemaps for a website.
    
    NEW: Falls back to building sitemap from navigation if no official sitemap exists.
    """
    parsed_base = urlparse(base_url)
    if not parsed_base.scheme or not parsed_base.netloc:
        raise ValueError("Base URL must include scheme and host (e.g., https://example.com)")
    
    base_netloc = parsed_base.netloc
    
    # Step 1: Try to discover official sitemaps
    sitemap_urls = await discover_sitemaps(base_url, max_sitemaps=max_sitemaps)
    
    # Step 2: If sitemaps found, parse them
    if sitemap_urls:
        print(f"  📊 Parsing {len(sitemap_urls)} sitemap(s)...")
        
        visited_sitemaps: Set[str] = set()
        all_urls: Set[str] = set()
        
        for sitemap_url in sitemap_urls:
            if len(all_urls) >= max_urls:
                break
            
            urls = await parse_sitemap_urls(
                sitemap_url,
                base_netloc,
                visited_sitemaps,
                max_urls=max_urls - len(all_urls),
                max_sitemaps=max_sitemaps
            )
            
            all_urls.update(urls)
        
        print(f"  ✅ Collected {len(all_urls)} URLs from sitemaps")
        
        if all_urls:
            return list(all_urls)
    
    # Step 3: Fallback - build sitemap from navigation
    print(f"  ⚠️  No official sitemap found or empty sitemap")
    return await build_sitemap_from_navigation(base_url, max_urls=max_urls)