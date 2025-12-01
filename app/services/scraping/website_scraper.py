from app.services.utils.http_client import http_client
from app.services.utils.parser import HTMLParser
from app.services.utils.validators import normalize_url, extract_domain, make_absolute_url
from app.services.utils.sitemap_utils import get_all_sitemap_urls  # NEW
from typing import Optional, Dict, List
import re

class WebsiteScraper:
    """
    Scrapes information directly from a company's website.
    """
    
    async def scrape(self, url: str) -> Dict:
        """Main scraping function."""
        print(f"🌐 Starting website scrape for: {url}")
        
        url = normalize_url(url)
        domain = extract_domain(url)
        
        result = {
            "url": url,
            "domain": domain,
            "logo_url": None,
            "company_name": None,
            "description": None,
            "social_links": {},
            "contact_info": {},
            "sitemap_urls": [],
            "key_pages": {},
            "products": [],
            "services": []
        }
        
        # Step 1: Fetch the homepage
        homepage_data = await self._scrape_homepage(url)
        if homepage_data:
            result.update(homepage_data)
        
        # Step 2: Get sitemap (IMPROVED)
        sitemap_urls = await get_all_sitemap_urls(url, max_urls=1000, max_sitemaps=500)
        result['sitemap_urls'] = sitemap_urls
        
        # Step 3: Find and scrape key pages
        key_pages = await self._find_key_pages(url, sitemap_urls)
        result['key_pages'] = key_pages
        
        # Step 4: Scrape About page
        if key_pages.get('about'):
            about_data = await self._scrape_about_page(key_pages['about'])
            if about_data:
                if not result['company_name']:
                    result['company_name'] = about_data.get('company_name')
                if not result['description']:
                    result['description'] = about_data.get('description')
        
        # Step 5: Scrape Products page
        if key_pages.get('products'):
            products = await self._scrape_products_page(key_pages['products'])
            result['products'] = products
        
        # Step 6: Scrape Contact page
        if key_pages.get('contact'):
            contact_data = await self._scrape_contact_page(key_pages['contact'])
            if contact_data:
                result['contact_info'] = self._merge_contact_info(
                    result['contact_info'],
                    contact_data
                )
        
        print(f"✅ Website scrape completed for: {domain}")
        return result
    
    async def _scrape_homepage(self, url: str) -> Optional[Dict]:
        """Scrape the homepage for basic company info."""
        print(f"  📄 Scraping homepage...")
        
        response = await http_client.get(url)
        if not response:
            print(f"  ❌ Failed to fetch homepage")
            return None
        
        parser = HTMLParser(response.text, url)
        
        return {
            "logo_url": parser.get_logo_url(),
            "company_name": parser.get_company_name(),
            "description": parser.get_meta_description(),
            "social_links": parser.get_social_links(),
            "contact_info": parser.get_contact_info()
        }
    
    async def _find_key_pages(self, base_url: str, sitemap_urls: List[str]) -> Dict[str, str]:
        """Find important pages."""
        print(f"  🔍 Finding key pages...")
        
        key_pages = {}
        
        page_keywords = {
            'about': ['about', 'company', 'who-we-are', 'our-story'],
            'products': ['products', 'solutions', 'services', 'what-we-do'],
            'contact': ['contact', 'contact-us', 'get-in-touch'],
            'team': ['team', 'leadership', 'management', 'people'],
            'careers': ['careers', 'jobs', 'hiring', 'join-us']
        }
        
        # Search sitemap
        for page_type, keywords in page_keywords.items():
            for url in sitemap_urls:
                url_lower = url.lower()
                if any(keyword in url_lower for keyword in keywords):
                    key_pages[page_type] = url
                    break
        
        # Fallback: try homepage links
        if len(key_pages) < len(page_keywords):
            response = await http_client.get(base_url)
            if response:
                parser = HTMLParser(response.text, base_url)
                
                for page_type, keywords in page_keywords.items():
                    if page_type not in key_pages:
                        found_url = parser.find_page_by_keywords(keywords)
                        if found_url:
                            key_pages[page_type] = found_url
        
        print(f"  ✅ Found {len(key_pages)} key pages: {list(key_pages.keys())}")
        return key_pages
    
    async def _scrape_about_page(self, url: str) -> Optional[Dict]:
        """Scrape the About page."""
        print(f"  📖 Scraping About page...")
        
        response = await http_client.get(url)
        if not response:
            return None
        
        parser = HTMLParser(response.text, url)
        
        description = parser.get_meta_description()
        
        if not description:
            main_content = parser.soup.find(['main', 'article', 'div'], class_=re.compile('content|main|about', re.I))
            if main_content:
                first_p = main_content.find('p')
                if first_p:
                    description = first_p.get_text(strip=True)
        
        return {
            "company_name": parser.get_company_name(),
            "description": description
        }
    
    async def _scrape_products_page(self, url: str) -> List[Dict]:
        """Scrape Products page."""
        print(f"  📦 Scraping Products page...")
        
        response = await http_client.get(url)
        if not response:
            return []
        
        parser = HTMLParser(response.text, url)
        products = []
        
        product_sections = parser.soup.find_all(['div', 'section', 'article'], 
                                                 class_=re.compile('product|service|solution', re.I))
        
        for section in product_sections[:10]:
            name_tag = section.find(['h2', 'h3', 'h4'])
            name = name_tag.get_text(strip=True) if name_tag else None
            
            desc_tag = section.find('p')
            description = desc_tag.get_text(strip=True) if desc_tag else None
            
            if name:
                products.append({
                    "name": name,
                    "description": description
                })
        
        print(f"  ✅ Found {len(products)} products/services")
        return products
    
    async def _scrape_contact_page(self, url: str) -> Optional[Dict]:
        """Scrape Contact page."""
        print(f"  📞 Scraping Contact page...")
        
        response = await http_client.get(url)
        if not response:
            return None
        
        parser = HTMLParser(response.text, url)
        return parser.get_contact_info()
    
    def _merge_contact_info(self, info1: Dict, info2: Dict) -> Dict:
        """Merge contact info dictionaries."""
        merged = {
            "emails": list(set(info1.get('emails', []) + info2.get('emails', []))),
            "phones": list(set(info1.get('phones', []) + info2.get('phones', []))),
            "addresses": list(set(info1.get('addresses', []) + info2.get('addresses', [])))
        }
        return merged


# Create a shared instance
website_scraper = WebsiteScraper()