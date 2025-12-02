from app.services.utils.http_client import http_client
from app.services.utils.parser import HTMLParser
from app.services.utils.validators import normalize_url, extract_domain, make_absolute_url
from app.services.utils.sitemap_utils import get_all_sitemap_urls
from typing import Optional, Dict, List
import re

class WebsiteScraper:
    """
    Comprehensive website scraper for company identity extraction.
    Extracts: logo, company info, social links, contacts, products, and more.
    """
    
    async def scrape(self, url: str, max_pages: int = 200) -> Dict:
        """
        Main scraping function for complete identity extraction.
        
        Args:
            url: Target company website URL
            max_pages: Maximum number of pages to crawl (default 200)
        """
        print(f"🌐 Starting comprehensive website scrape for: {url}")
        
        url = normalize_url(url)
        domain = extract_domain(url)
        
        result = {
            "url": url,
            "domain": domain,
            "logo_url": None,
            "favicon_url": None,
            "company_name": None,
            "description": None,
            "social_links": {},
            "contact_info": {},
            "sitemap_urls": [],
            "internal_links": [],
            "key_pages": {},
            "products": [],
            "services": [],
            "pdf_documents": [],
            "json_ld_data": [],
            "opengraph_data": {}
        }
        
        # Step 1: Fetch and parse the homepage
        homepage_data = await self._scrape_homepage(url)
        if homepage_data:
            result.update(homepage_data)
        
        # Step 2: Get comprehensive sitemap
        print(f"  🗺️  Discovering sitemaps...")
        sitemap_urls = await get_all_sitemap_urls(url, max_urls=max_pages, max_sitemaps=500)
        result['sitemap_urls'] = sitemap_urls
        print(f"  ✅ Found {len(sitemap_urls)} URLs in sitemap(s)")
        
        # Step 3: Crawl internal links from homepage (up to limit)
        if len(sitemap_urls) < max_pages:
            print(f"  🕸️  Crawling internal links...")
            response = await http_client.get(url)
            if response:
                parser = HTMLParser(response.text, url)
                internal_links = parser.get_all_internal_links(max_links=max_pages - len(sitemap_urls))
                result['internal_links'] = internal_links
                print(f"  ✅ Found {len(internal_links)} additional internal links")
                
                # Merge with sitemap
                all_pages = list(set(sitemap_urls + internal_links))[:max_pages]
            else:
                all_pages = sitemap_urls
        else:
            all_pages = sitemap_urls[:max_pages]
        
        # Step 4: Find and scrape key pages
        key_pages = await self._find_key_pages(url, all_pages)
        result['key_pages'] = key_pages
        
        # Step 5: Scrape About page for more company info
        if key_pages.get('about'):
            about_data = await self._scrape_about_page(key_pages['about'])
            if about_data:
                if not result['company_name']:
                    result['company_name'] = about_data.get('company_name')
                if not result['description']:
                    result['description'] = about_data.get('description')
        
        # Step 6: Scrape Products/Services pages
        if key_pages.get('products'):
            products = await self._scrape_products_page(key_pages['products'])
            result['products'].extend(products)
        
        # Step 7: Scrape Contact page for additional info
        if key_pages.get('contact'):
            contact_data = await self._scrape_contact_page(key_pages['contact'])
            if contact_data:
                result['contact_info'] = self._merge_contact_info(
                    result['contact_info'],
                    contact_data
                )
        
        # Step 8: Extract products from all product-related pages
        print(f"  🔍 Scanning for product pages...")
        product_urls = [url for url in all_pages if self._is_product_url(url)]
        print(f"  📦 Found {len(product_urls)} potential product pages")
        
        if product_urls:
            # Scrape up to 20 product pages
            for product_url in product_urls[:20]:
                product_data = await self._scrape_single_product_page(product_url)
                if product_data:
                    result['products'].append(product_data)
        
        print(f"✅ Website scrape completed for: {domain}")
        print(f"  📊 Results: {len(result.get('products', []))} products, {len(result.get('social_links', {}))} social links, {len(result.get('contact_info', {}).get('emails', []))} emails")
        
        return result
    
    async def _scrape_homepage(self, url: str) -> Optional[Dict]:
        """Scrape the homepage for comprehensive company identity."""
        print(f"  📄 Scraping homepage...")
        
        response = await http_client.get(url)
        if not response:
            print(f"  ❌ Failed to fetch homepage")
            return None
        
        parser = HTMLParser(response.text, url)
        
        # Extract all structured data
        json_ld = parser.get_json_ld()
        opengraph = parser.get_opengraph_tags()
        
        return {
            "logo_url": parser.get_logo_url(),
            "favicon_url": parser.get_favicon_url(),
            "company_name": parser.get_company_name(),
            "description": parser.get_company_description(),
            "social_links": parser.get_social_links(),
            "contact_info": parser.get_contact_info(),
            "pdf_documents": parser.get_pdf_links(),
            "json_ld_data": json_ld,
            "opengraph_data": opengraph
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
        """Scrape Products page with JSON-LD support."""
        print(f"  📦 Scraping Products page...")
        
        response = await http_client.get(url)
        if not response:
            return []
        
        parser = HTMLParser(response.text, url)
        products = []
        
        # First, try to get products from JSON-LD
        json_ld_products = parser.get_products_from_json_ld()
        if json_ld_products:
            products.extend(json_ld_products)
            print(f"  ✅ Extracted {len(json_ld_products)} products from JSON-LD")
        
        # Then scrape products from HTML
        product_sections = parser.soup.find_all(['div', 'section', 'article'], 
                                                 class_=re.compile('product|service|solution', re.I))
        
        for section in product_sections[:10]:
            name_tag = section.find(['h2', 'h3', 'h4'])
            name = name_tag.get_text(strip=True) if name_tag else None
            
            desc_tag = section.find('p')
            description = desc_tag.get_text(strip=True) if desc_tag else None
            
            link_tag = section.find('a', href=True)
            url = make_absolute_url(self.base_url, link_tag['href']) if link_tag else None
            
            if name and name not in [p.get('name') for p in products]:
                products.append({
                    "name": name,
                    "description": description,
                    "url": url
                })
        
        print(f"  ✅ Found total {len(products)} products/services")
        return products
    
    def _is_product_url(self, url: str) -> bool:
        """Check if URL is likely a product page."""
        product_keywords = ['product', 'service', 'solution', 'offering', 'feature']
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in product_keywords)
    
    async def _scrape_single_product_page(self, url: str) -> Optional[Dict]:
        """Scrape a single product page for details."""
        try:
            response = await http_client.get(url)
            if not response:
                return None
            
            parser = HTMLParser(response.text, url)
            
            # Try JSON-LD first
            json_ld_products = parser.get_products_from_json_ld()
            if json_ld_products:
                return json_ld_products[0]
            
            # Extract manually
            title = parser.get_title()
            description = parser.get_company_description()
            pdfs = parser.get_pdf_links()
            
            # Look for product features
            features = []
            feature_sections = parser.soup.find_all(['ul', 'ol'], class_=re.compile('feature|benefit', re.I))
            for section in feature_sections[:3]:
                items = section.find_all('li')
                features.extend([item.get_text(strip=True) for item in items[:10]])
            
            return {
                'name': title,
                'description': description,
                'url': url,
                'features': features[:10] if features else None,
                'brochures': pdfs[:3] if pdfs else None
            }
        
        except Exception as e:
            return None
    
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
            "addresses": list(set(info1.get('addresses', []) + info2.get('addresses', []))),
            "google_maps_links": list(set(
                info1.get('google_maps_links', []) + info2.get('google_maps_links', [])
            ))
        }
        return merged


# Create a shared instance
website_scraper = WebsiteScraper()