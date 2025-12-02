from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
import re
import json
from urllib.parse import urljoin

class HTMLParser:
    """A helper class for parsing HTML content."""
    
    def __init__(self, html: str, base_url: str):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.base_url = base_url
        self._json_ld_cache = None
        self._opengraph_cache = None
    
    def get_json_ld(self) -> List[Dict[str, Any]]:
        """Extract all JSON-LD structured data from the page."""
        if self._json_ld_cache is not None:
            return self._json_ld_cache
        
        json_ld_data = []
        scripts = self.soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        json_ld_data.extend(data)
                    else:
                        json_ld_data.append(data)
                except json.JSONDecodeError:
                    continue
        
        self._json_ld_cache = json_ld_data
        return json_ld_data
    
    def get_opengraph_tags(self) -> Dict[str, str]:
        """Extract all OpenGraph meta tags."""
        if self._opengraph_cache is not None:
            return self._opengraph_cache
        
        og_data = {}
        og_tags = self.soup.find_all('meta', property=re.compile(r'^og:'))
        
        for tag in og_tags:
            property_name = tag.get('property', '').replace('og:', '')
            content = tag.get('content', '').strip()
            if property_name and content:
                og_data[property_name] = content
        
        self._opengraph_cache = og_data
        return og_data
        self._json_ld_cache = None
        self._opengraph_cache = None
    
    def get_title(self) -> Optional[str]:
        """Get the page title."""
        title_tag = self.soup.find('title')
        return title_tag.get_text(strip=True) if title_tag else None
    
    def get_meta_description(self) -> Optional[str]:
        """Get the meta description."""
        meta_tag = self.soup.find('meta', attrs={'name': 'description'})
        
        if meta_tag and meta_tag.get('content'):
            return meta_tag.get('content').strip()
        
        og_tag = self.soup.find('meta', attrs={'property': 'og:description'})
        if og_tag and og_tag.get('content'):
            return og_tag.get('content').strip()
        
        return None
    
    def get_logo_url(self) -> Optional[str]:
        """Find the company logo URL from multiple sources."""
        # Strategy 1: JSON-LD structured data
        json_ld = self.get_json_ld()
        for item in json_ld:
            if isinstance(item, dict):
                # Check for Organization schema
                if item.get('@type') in ['Organization', 'Corporation', 'LocalBusiness']:
                    logo = item.get('logo')
                    if logo:
                        if isinstance(logo, str):
                            return urljoin(self.base_url, logo)
                        elif isinstance(logo, dict) and logo.get('url'):
                            return urljoin(self.base_url, logo['url'])
                
                # Check for image property
                if item.get('image'):
                    image = item['image']
                    if isinstance(image, str):
                        return urljoin(self.base_url, image)
                    elif isinstance(image, dict) and image.get('url'):
                        return urljoin(self.base_url, image['url'])
        
        # Strategy 2: Open Graph image
        og_tags = self.get_opengraph_tags()
        if og_tags.get('image'):
            return urljoin(self.base_url, og_tags['image'])
        
        # Strategy 3: Look for <img> with 'logo' in class or alt
        logo_img = self.soup.find('img', class_=re.compile('logo', re.I))
        if logo_img and logo_img.get('src'):
            return urljoin(self.base_url, logo_img.get('src'))
        
        logo_img = self.soup.find('img', alt=re.compile('logo', re.I))
        if logo_img and logo_img.get('src'):
            return urljoin(self.base_url, logo_img.get('src'))
        
        # Strategy 4: Favicon
        icon_link = self.soup.find('link', rel=re.compile('icon|apple-touch-icon', re.I))
        if icon_link and icon_link.get('href'):
            return urljoin(self.base_url, icon_link.get('href'))
        
        return None
    
    def get_favicon_url(self) -> Optional[str]:
        """Get the favicon URL."""
        icon_link = self.soup.find('link', rel=re.compile('icon|shortcut icon', re.I))
        if icon_link and icon_link.get('href'):
            return urljoin(self.base_url, icon_link.get('href'))
        
        # Default favicon location
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    
    def get_company_name(self) -> Optional[str]:
        """
        Extract the company name from multiple sources.
        """
        # Strategy 1: JSON-LD structured data
        json_ld = self.get_json_ld()
        for item in json_ld:
            if isinstance(item, dict):
                if item.get('@type') in ['Organization', 'Corporation', 'LocalBusiness', 'WebSite']:
                    name = item.get('name')
                    if name:
                        return name.strip()
        
        # Strategy 2: Open Graph site_name
        og_tags = self.get_opengraph_tags()
        if og_tags.get('site_name'):
            return og_tags['site_name'].strip()
        
        # Strategy 3: Extract from title
        title = self.get_title()
        if title:
            # Common patterns: "Page - Company", "Company | Page", "Company - Page"
            for separator in [' - ', ' | ', ' — ']:
                if separator in title:
                    parts = title.split(separator)
                    # Usually company name is last or first
                    return parts[-1].strip() if len(parts[-1]) < len(parts[0]) else parts[0].strip()
            
            # If title is short and simple, it's probably the company name
            if len(title.split()) <= 3 and len(title) <= 50:
                return title.strip()
        
        # Strategy 4: Extract from domain as last resort
        from urllib.parse import urlparse
        from app.services.utils.validators import get_company_name_from_domain
        
        parsed = urlparse(self.base_url)
        domain = parsed.netloc
        
        # Remove 'www.' if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Convert domain to company name
        return get_company_name_from_domain(domain)
        
        # Remove 'www.' if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Convert domain to company name
        # "google.com" → "Google"
        # "stripe.com" → "Stripe"
        return get_company_name_from_domain(domain)
    
    def get_social_links(self) -> Dict[str, str]:
        """Find social media profile links."""
        social_links = {}
        
        social_patterns = {
            'twitter.com': 'twitter',
            'x.com': 'twitter',
            'linkedin.com': 'linkedin',
            'facebook.com': 'facebook',
            'instagram.com': 'instagram',
            'youtube.com': 'youtube',
            'github.com': 'github',
            'tiktok.com': 'tiktok'
        }
        
        all_links = self.soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            
            for domain, platform in social_patterns.items():
                if domain in href.lower():
                    full_url = urljoin(self.base_url, href)
                    if platform not in social_links:
                        social_links[platform] = full_url
        
        return social_links
    
    def get_contact_info(self) -> Dict[str, any]:
        """Extract comprehensive contact information."""
        contact_info = {
            "emails": [],
            "phones": [],
            "addresses": [],
            "google_maps_links": []
        }
        
        page_text = self.soup.get_text()
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        # Filter out common non-contact emails
        excluded_domains = ['example.com', 'yourdomain.com', 'domain.com']
        emails = [e for e in emails if not any(ex in e.lower() for ex in excluded_domains)]
        contact_info['emails'] = list(set(emails))[:10]  # Limit to 10
        
        # Extract phones
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, page_text))
        contact_info['phones'] = list(set(phones))[:10]  # Limit to 10
        
        # Extract Google Maps links
        all_links = self.soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if 'google.com/maps' in href or 'maps.google.com' in href or 'goo.gl/maps' in href:
                full_url = urljoin(self.base_url, href)
                if full_url not in contact_info['google_maps_links']:
                    contact_info['google_maps_links'].append(full_url)
        
        # Extract addresses from JSON-LD
        json_ld = self.get_json_ld()
        for item in json_ld:
            if isinstance(item, dict):
                address = item.get('address')
                if address:
                    if isinstance(address, str):
                        contact_info['addresses'].append(address)
                    elif isinstance(address, dict):
                        address_str = ', '.join(filter(None, [
                            address.get('streetAddress'),
                            address.get('addressLocality'),
                            address.get('addressRegion'),
                            address.get('postalCode'),
                            address.get('addressCountry')
                        ]))
                        if address_str:
                            contact_info['addresses'].append(address_str)
        
        return contact_info
    
    def find_page_by_keywords(self, keywords: List[str]) -> Optional[str]:
        """Find a link that contains any of the given keywords."""
        all_links = self.soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '').lower()
            link_text = link.get_text(strip=True).lower()
            
            for keyword in keywords:
                if keyword.lower() in href or keyword.lower() in link_text:
                    return urljoin(self.base_url, link.get('href'))
        
        return None
    
    def get_all_internal_links(self, max_links: int = 100) -> List[str]:
        """Get all internal links."""
        from app.services.utils.validators import is_same_domain, make_absolute_url
        
        internal_links = set()
        all_links = self.soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            absolute_url = make_absolute_url(self.base_url, href)
            
            if is_same_domain(self.base_url, absolute_url):
                internal_links.add(absolute_url)
            
            if len(internal_links) >= max_links:
                break
        
        return list(internal_links)
    
    def get_products_from_json_ld(self) -> List[Dict[str, Any]]:
        """Extract product information from JSON-LD structured data."""
        products = []
        json_ld = self.get_json_ld()
        
        for item in json_ld:
            if isinstance(item, dict):
                if item.get('@type') == 'Product':
                    product = {
                        'name': item.get('name'),
                        'description': item.get('description'),
                        'image': item.get('image'),
                        'url': item.get('url'),
                        'brand': item.get('brand', {}).get('name') if isinstance(item.get('brand'), dict) else item.get('brand'),
                        'category': item.get('category'),
                        'offers': None
                    }
                    
                    # Extract pricing if available
                    if 'offers' in item:
                        offers = item['offers']
                        if isinstance(offers, dict):
                            product['offers'] = {
                                'price': offers.get('price'),
                                'currency': offers.get('priceCurrency'),
                                'availability': offers.get('availability')
                            }
                    
                    products.append(product)
        
        return products
    
    def get_pdf_links(self) -> List[Dict[str, str]]:
        """Extract all PDF links from the page."""
        pdf_links = []
        all_links = self.soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            if href.lower().endswith('.pdf'):
                full_url = urljoin(self.base_url, href)
                link_text = link.get_text(strip=True)
                pdf_links.append({
                    'url': full_url,
                    'title': link_text or 'PDF Document'
                })
        
        return pdf_links
    
    def get_company_description(self) -> Optional[str]:
        """Get comprehensive company description from multiple sources."""
        # Try OpenGraph description first
        og_tags = self.get_opengraph_tags()
        if og_tags.get('description'):
            return og_tags['description']
        
        # Try meta description
        meta_desc = self.get_meta_description()
        if meta_desc:
            return meta_desc
        
        # Try JSON-LD
        json_ld = self.get_json_ld()
        for item in json_ld:
            if isinstance(item, dict):
                if item.get('@type') in ['Organization', 'Corporation', 'LocalBusiness']:
                    desc = item.get('description')
                    if desc:
                        return desc
        
        return None