import asyncio
import logging
import uuid
import aiohttp
from typing import List

logger = logging.getLogger(__name__)

class LinkGenerator:
    """Generates and validates ChatGPT share links using UUID only"""
    
    def generate_links(self, count: int = 5) -> List[str]:
        """Generate ChatGPT share URLs using UUID4
        
        Args:
            count: Number of links to generate
            
        Returns:
            List of generated ChatGPT share URLs
        """
        logger.info(f"Generating {count} new links using UUID4...")
        
        links = []
        for _ in range(count):
            # Generate UUID4 which follows the format: 8-4-4-4-12 hexadecimal characters
            uuid_str = str(uuid.uuid4())
            link = f"https://chatgpt.com/share/{uuid_str}"
            links.append(link)
        
        logger.info(f"Generated {len(links)} URLs successfully")
        #logger.info(f"Generated {links[:3]}...{links[-3:]} URLs successfully")
        return links
    
    async def validate_link(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Validate if a link returns 200 OK status
        
        Args:
            session: aiohttp ClientSession for making requests
            url: URL to validate
            
        Returns:
            True if link is valid (returns 200), False otherwise
        """
        try:
            async with session.get(url, timeout=10) as response:
                is_valid = response.status == 200
                logger.debug(f"Link {url} validation: {response.status} ({'valid' if is_valid else 'invalid'})")
                return is_valid
                
        except asyncio.TimeoutError:
            logger.debug(f"Link {url} validation timeout")
            return False
        except Exception as e:
            logger.debug(f"Link {url} validation error: {e}")
            return False
    
    async def validate_links(self, urls: List[str]) -> List[str]:
        """Validate multiple links concurrently
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            List of valid URLs
        """
        if not urls:
            return []
        
        logger.info(f"Validating {len(urls)} links...")
        
        async with aiohttp.ClientSession() as session:
            # Create validation tasks for concurrent execution
            tasks = [self.validate_link(session, url) for url in urls]
            
            # Wait for all validation tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter valid URLs
            valid_urls = []
            for url, result in zip(urls, results):
                if isinstance(result, bool) and result:
                    valid_urls.append(url)
                elif isinstance(result, Exception):
                    logger.debug(f"Validation failed for {url}: {result}")
            
            logger.info(f"Found {len(valid_urls)} valid links out of {len(urls)}")
            return valid_urls
    
    def generate_and_get_links(self, count: int = 5) -> List[str]:
        """Synchronous method to generate links
        
        Args:
            count: Number of links to generate
            
        Returns:
            List of generated ChatGPT share URLs
        """
        return self.generate_links(count)
    
    async def generate_and_validate_links(self, count: int = 5, validate: bool = True) -> List[str]:
        """Generate links and optionally validate them
        
        Args:
            count: Number of links to generate
            validate: Whether to validate the generated links
            
        Returns:
            List of generated (and optionally validated) ChatGPT share URLs
        """
        # Generate links
        links = self.generate_links(count)
        
        # Optionally validate links
        if validate:
            valid_links = await self.validate_links(links)
            return valid_links
        
        return links