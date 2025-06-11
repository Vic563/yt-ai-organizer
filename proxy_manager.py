"""
Proxy manager for rotating requests to avoid IP-based blocking
"""
import logging
import random
import requests
from typing import List, Optional, Dict
import time

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manages proxy rotation for HTTP requests"""
    
    def __init__(self):
        # Free proxy list - these are examples, users would need to provide their own
        self.free_proxies = [
            # These are example proxy formats - actual proxies would need to be provided
            # {"http": "http://proxy1:port", "https": "https://proxy1:port"},
            # {"http": "http://proxy2:port", "https": "https://proxy2:port"},
        ]
        
        self.working_proxies = []
        self.failed_proxies = set()
        self.last_test_time = 0
        self.test_interval = 300  # Test proxies every 5 minutes
        
    def add_proxy(self, proxy_dict: Dict[str, str]):
        """Add a proxy to the rotation list"""
        if proxy_dict not in self.free_proxies:
            self.free_proxies.append(proxy_dict)
            logger.info(f"Added proxy to rotation: {proxy_dict}")
    
    def add_proxies_from_list(self, proxy_strings: List[str]):
        """Add proxies from a list of strings like 'host:port'"""
        for proxy_str in proxy_strings:
            try:
                if ':' in proxy_str:
                    host, port = proxy_str.strip().split(':')
                    proxy_dict = {
                        "http": f"http://{host}:{port}",
                        "https": f"http://{host}:{port}"
                    }
                    self.add_proxy(proxy_dict)
            except Exception as e:
                logger.warning(f"Invalid proxy format '{proxy_str}': {e}")
    
    async def test_proxy(self, proxy_dict: Dict[str, str], timeout: int = 10) -> bool:
        """Test if a proxy is working"""
        try:
            test_url = "https://httpbin.org/ip"
            response = requests.get(
                test_url, 
                proxies=proxy_dict, 
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            if response.status_code == 200:
                logger.debug(f"Proxy test successful: {proxy_dict}")
                return True
            else:
                logger.debug(f"Proxy test failed with status {response.status_code}: {proxy_dict}")
                return False
                
        except Exception as e:
            logger.debug(f"Proxy test failed with error: {proxy_dict} - {e}")
            return False
    
    async def refresh_working_proxies(self):
        """Test all proxies and update working list"""
        current_time = time.time()
        if current_time - self.last_test_time < self.test_interval:
            return  # Don't test too frequently
        
        self.last_test_time = current_time
        logger.info("Testing proxy connections...")
        
        new_working = []
        for proxy in self.free_proxies:
            proxy_key = str(proxy)
            if proxy_key in self.failed_proxies:
                continue  # Skip previously failed proxies
                
            if await self.test_proxy(proxy):
                new_working.append(proxy)
            else:
                self.failed_proxies.add(proxy_key)
        
        self.working_proxies = new_working
        logger.info(f"Found {len(self.working_proxies)} working proxies out of {len(self.free_proxies)} total")
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random working proxy"""
        if not self.working_proxies:
            return None
        return random.choice(self.working_proxies)
    
    def get_proxy_session(self) -> requests.Session:
        """Get a requests session with a random proxy"""
        session = requests.Session()
        
        proxy = self.get_random_proxy()
        if proxy:
            session.proxies.update(proxy)
            logger.debug(f"Using proxy: {proxy}")
        else:
            logger.debug("No working proxies available, using direct connection")
        
        # Add realistic headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def report_proxy_failure(self, proxy_dict: Dict[str, str]):
        """Report that a proxy failed and remove it from working list"""
        if proxy_dict in self.working_proxies:
            self.working_proxies.remove(proxy_dict)
            self.failed_proxies.add(str(proxy_dict))
            logger.debug(f"Marked proxy as failed: {proxy_dict}")
    
    def get_status(self) -> Dict:
        """Get proxy manager status"""
        return {
            "total_proxies": len(self.free_proxies),
            "working_proxies": len(self.working_proxies),
            "failed_proxies": len(self.failed_proxies),
            "last_test": self.last_test_time
        }

# Global instance for easy access
proxy_manager = ProxyManager()

# Example of how to add proxies (users would add their own)
# proxy_manager.add_proxies_from_list([
#     "proxy1.example.com:8080",
#     "proxy2.example.com:3128",
#     "proxy3.example.com:8000"
# ])