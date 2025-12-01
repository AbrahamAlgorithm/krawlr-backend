from bs4 import BeautifulSoup
from typing import Optional, List, Dict
import re
from urllib.parse import urljoin

class HTMLParser:
    """A helper class for parsing HTML content."""
    
    def __init__(self, html: str, base_url: str):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.base_url = base_url
    
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
        """Find the company logo URL."""
        # Strategy 1: Favicon
        icon_link = self.soup.find('link', rel=re.compile('icon|apple-touch-icon', re.I))
        if icon_link and icon_link.get('href'):
            return urljoin(self.base_url, icon_link.get('href'))
        
        # Strategy 2: Open Graph image
        og_image = self.soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(self.base_url, og_image.get('content'))
        
        # Strategy 3: Look for <img> with 'logo' in class or alt
        logo_img = self.soup.find('img', class_=re.compile('logo', re.I))
        if logo_img and logo_img.get('src'):
            return urljoin(self.base_url, logo_img.get('src'))
        
        logo_img = self.soup.find('img', alt=re.compile('logo', re.I))
        if logo_img and logo_img.get('src'):
            return urljoin(self.base_url, logo_img.get('src'))
        
        return None
    
    def get_company_name(self) -> Optional[str]:
        """
        Extract the company name.
        
        IMPROVED: Now includes fallback to domain name.
        """
        # Strategy 1: Open Graph site_name
        og_name = self.soup.find('meta', property='og:site_name')
        if og_name and og_name.get('content'):
            return og_name.get('content').strip()
        
        # Strategy 2: Schema.org structured data
        schema_script = self.soup.find('script', type='application/ld+json')
        if schema_script:
            try:
                import json
                data = json.loads(schema_script.string)
                if isinstance(data, dict) and data.get('@type') == 'Organization':
                    return data.get('name')
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Organization':
                            return item.get('name')
            except:
                pass
        
        # Strategy 3: Extract from title
        title = self.get_title()
        if title:
            # Common patterns: "Page - Company", "Company | Page", "Company - Page"
            for separator in [' - ', ' | ', ' — ']:
                if separator in title:
                    parts = title.split(separator)
                    # Usually company name is last or first
                    return parts[-1].strip() if len(parts[-1]) < len(parts[0]) else parts[0].strip()
            
            # NEW: If title is short and simple, it's probably the company name
            # Example: "Google", "Stripe", "Facebook"
            if len(title.split()) <= 3 and len(title) <= 50:
                return title.strip()
        
        # Strategy 4: NEW - Extract from domain as last resort
        from urllib.parse import urlparse
        from app.services.utils.validators import get_company_name_from_domain
        
        parsed = urlparse(self.base_url)
        domain = parsed.netloc
        
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
        """Extract contact information."""
        contact_info = {
            "emails": [],
            "phones": [],
            "addresses": []
        }
        
        page_text = self.soup.get_text()
        
        # Email regex
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        contact_info['emails'] = list(set(emails))
        
        # Phone regex
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, page_text)
            contact_info['phones'].extend(phones)
        
        contact_info['phones'] = list(set(contact_info['phones']))
        
        # Look for address in schema.org
        schema_script = self.soup.find('script', type='application/ld+json')
        if schema_script:
            try:
                import json
                data = json.loads(schema_script.string)
                
                items = [data] if isinstance(data, dict) else data
                
                for item in items:
                    if isinstance(item, dict) and 'address' in item:
                        address = item['address']
                        if isinstance(address, dict):
                            address_str = ', '.join(filter(None, [
                                address.get('streetAddress'),
                                address.get('addressLocality'),
                                address.get('addressRegion'),
                                address.get('postalCode')
                            ]))
                            if address_str:
                                contact_info['addresses'].append(address_str)
            except:
                pass
        
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