import logging
import nest_asyncio
from playwright.async_api import async_playwright
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)
nest_asyncio.apply()

class ContentExtractor:
    """Extracts conversation content from ChatGPT share links"""
    
    async def extract_conversation(self, url: str) -> Optional[Dict]:
        """Extract complete conversation data from ChatGPT share URL"""
        try:
            logger.info(f"Extracting conversation from: {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    messages = await self._extract_with_multiple_strategies(page)

                    # Filter out error messages
                    error_patterns = [
                        "can't load shared conversation",
                        "return to chatgpt",
                        "unable to load",
                        "not found",
                        "something went wrong"
                    ]
                    
                    def is_error_message(msg):
                        content = msg.get("content", "").lower()
                        return any(pat in content for pat in error_patterns)

                    filtered_messages = [
                        msg for msg in messages if not is_error_message(msg)
                    ]

                    if not filtered_messages:
                        logger.warning(f"All extracted messages are error banners for {url}")
                        return None

                    # Validate conversation structure
                    user_count = sum(1 for msg in filtered_messages if msg.get("role") == "user")
                    assistant_count = sum(1 for msg in filtered_messages if msg.get("role") == "assistant")
                    
                    logger.info(f"✅ Extracted {len(filtered_messages)} messages: {user_count} user, {assistant_count} assistant")
                    
                    # Warn if imbalanced
                    if user_count == 0:
                        logger.warning("⚠️  No user messages detected - check role detection logic")
                    elif assistant_count == 0:
                        logger.warning("⚠️  No assistant messages detected - check role detection logic")
                    
                    return {
                        'url': url,
                        'messages': filtered_messages,
                        'metadata': {
                            'total_messages': len(filtered_messages),
                            'user_messages': user_count,
                            'assistant_messages': assistant_count,
                            'extraction_method': 'playwright_multi_strategy'
                        }
                    }

                except Exception as e:
                    logger.error(f"Error during page processing: {e}")
                    return None
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Error extracting conversation from {url}: {e}")
            return None
    
    async def _extract_with_multiple_strategies(self, page) -> List[Dict]:
        """Try multiple extraction strategies with improved role detection"""
        strategies = [
            self._strategy_modern_selectors,
            self._strategy_alternative_selectors,
            self._strategy_generic_selectors,
            self._strategy_structured_extraction,
            self._strategy_fallback
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                logger.debug(f"Trying extraction strategy {i + 1}")
                conversation = await strategy(page)
                if conversation and self._validate_conversation_structure(conversation):
                    logger.debug(f"Strategy {i + 1} succeeded with {len(conversation)} messages")
                    return conversation
            except Exception as e:
                logger.debug(f"Strategy {i + 1} failed: {e}")
                continue
        
        return []
    
    def _validate_conversation_structure(self, messages: List[Dict]) -> bool:
        """Validate that we have a reasonable conversation structure"""
        if not messages:
            return False
        
        # Check if we have both user and assistant messages
        roles = {msg.get("role") for msg in messages}
        has_user = "user" in roles
        has_assistant = "assistant" in roles
        
        # At least one of each type for a complete conversation
        return has_user and has_assistant
    
    async def _strategy_modern_selectors(self, page) -> List[Dict]:
        """Modern ChatGPT selectors strategy with improved role detection"""
        conversation = []
        
        # Try multiple container selectors
        container_selectors = [
            '[data-testid*="conversation-turn"]',
            '[data-testid*="message"]',
            'div[class*="ConversationItem"]'
        ]
        
        containers = []
        for selector in container_selectors:
            found = await page.query_selector_all(selector)
            if found:
                containers = found
                break
        
        for container in containers:
            role = await self._determine_role_improved(container)
            content = await self._extract_content(container, [
                '.prose', '.markdown', '[class*="markdown"]', '[class*="prose"]'
            ])
            
            if content and len(content.strip()) > 10:
                conversation.append({
                    "role": role, 
                    "content": content.strip(),
                    "extraction_method": "modern_selectors"
                })
        
        return conversation
    
    async def _strategy_alternative_selectors(self, page) -> List[Dict]:
        """Alternative modern selectors strategy"""
        conversation = []
        containers = await page.query_selector_all('div[class*="group"][class*="w-full"]')
        
        for container in containers:
            role = await self._determine_role_improved(container)
            content = await self._extract_content(container, [
                'div[class*="markdown"]', '.prose', 'div[class*="prose"]', '.message-content'
            ])
            
            if content and len(content.strip()) > 10:
                conversation.append({
                    "role": role, 
                    "content": content.strip(),
                    "extraction_method": "alternative_selectors"
                })
        
        return conversation
    
    async def _strategy_generic_selectors(self, page) -> List[Dict]:
        """Generic selectors strategy"""
        conversation = []
        containers = await page.query_selector_all('div.group, div[class*="message"]')
        
        for container in containers:
            role = await self._determine_role_improved(container)
            content = await self._extract_content(container, [
                'div[class*="markdown"]', 'div[class*="prose"]', '.message-content', 'p'
            ])
            
            if content and len(content.strip()) > 10:
                conversation.append({
                    "role": role, 
                    "content": content.strip(),
                    "extraction_method": "generic_selectors"
                })
        
        return conversation
    
    async def _strategy_structured_extraction(self, page) -> List[Dict]:
        """Try to extract messages in order from the page structure"""
        conversation = []
        
        # Look for alternating pattern in page structure
        all_elements = await page.query_selector_all('div, article, section')
        potential_messages = []
        
        for elem in all_elements:
            try:
                text = await elem.inner_text()
                if text and len(text.strip()) > 20 and len(text.strip()) < 10000:
                    # Check if this looks like a message
                    if self._looks_like_message(text.strip()):
                        role = await self._determine_role_improved(elem)
                        potential_messages.append({
                            "role": role,
                            "content": text.strip(),
                            "extraction_method": "structured_extraction"
                        })
            except:
                continue
        
        # Remove duplicates and filter
        seen_content = set()
        for msg in potential_messages:
            content_hash = hash(msg["content"][:100])  # Use first 100 chars as hash
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                conversation.append(msg)
        
        return conversation[:50]  # Limit to reasonable number
    
    async def _strategy_fallback(self, page) -> List[Dict]:
        """Enhanced fallback strategy with pattern recognition"""
        conversation = []
        
        # Get page text and try to identify conversation patterns
        page_text = await page.inner_text('body')
        
        # Split by potential message boundaries
        potential_splits = [
            '\n\n\n',
            '\n\nUser\n',
            '\n\nAssistant\n',
            '\n\nChatGPT\n'
        ]
        
        segments = [page_text]
        for split_pattern in potential_splits:
            new_segments = []
            for segment in segments:
                new_segments.extend(segment.split(split_pattern))
            segments = new_segments
        
        # Filter and classify segments
        for i, segment in enumerate(segments):
            cleaned = segment.strip()
            if len(cleaned) > 50 and len(cleaned) < 5000:
                # Use position and content to guess role
                role = self._guess_role_from_content(cleaned, i)
                conversation.append({
                    "role": role,
                    "content": cleaned,
                    "extraction_method": "fallback_pattern"
                })
        
        return conversation[:20]  # Limit results
    
    def _looks_like_message(self, text: str) -> bool:
        """Check if text looks like a conversation message"""
        # Skip very short or very long texts
        if len(text) < 20 or len(text) > 10000:
            return False
        
        # Skip navigation/UI elements
        ui_patterns = [
            'sign up', 'log in', 'menu', 'navigation', 'footer',
            'cookie', 'privacy', 'terms', 'subscribe'
        ]
        
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in ui_patterns):
            return False
        
        return True
    
    def _guess_role_from_content(self, content: str, position: int) -> str:
        """Guess role based on content patterns and position"""
        content_lower = content.lower()
        
        # Look for user indicators in content
        user_patterns = [
            'please', 'can you', 'how do i', 'what is', 'help me',
            'i want', 'i need', 'could you', 'would you'
        ]
        
        # Look for assistant indicators
        assistant_patterns = [
            'i can help', 'here is', 'here are', 'to answer',
            'certainly', 'of course', 'i understand', 'let me'
        ]
        
        user_score = sum(1 for pattern in user_patterns if pattern in content_lower)
        assistant_score = sum(1 for pattern in assistant_patterns if pattern in content_lower)
        
        if user_score > assistant_score:
            return "user"
        elif assistant_score > user_score:
            return "assistant"
        
        # Fallback to alternating pattern
        return "user" if position % 2 == 0 else "assistant"
    
    async def _determine_role_improved(self, container) -> str:
        """Improved role determination with multiple strategies"""
        try:
            # Strategy 1: Look for avatar/icon indicators
            user_avatar_selectors = [
                'img[alt*="User"]', 'img[alt*="user"]', 'img[src*="user"]',
                '[aria-label*="User"]', '[aria-label*="user"]',
                '[data-testid*="user"]', '.user-avatar'
            ]
            
            assistant_avatar_selectors = [
                'img[alt*="ChatGPT"]', 'img[alt*="Assistant"]', 'img[alt*="assistant"]',
                'img[src*="chatgpt"]', 'img[src*="openai"]',
                '[aria-label*="ChatGPT"]', '[aria-label*="Assistant"]',
                '[data-testid*="assistant"]', '.assistant-avatar'
            ]
            
            # Check for user indicators
            for selector in user_avatar_selectors:
                elements = await container.query_selector_all(selector)
                if elements:
                    return "user"
            
            # Check for assistant indicators
            for selector in assistant_avatar_selectors:
                elements = await container.query_selector_all(selector)
                if elements:
                    return "assistant"
            
            # Strategy 2: Check container classes
            container_html = await container.get_attribute('class') or ''
            container_html += await container.get_attribute('data-testid') or ''
            
            if any(indicator in container_html.lower() for indicator in ['user', 'human']):
                return "user"
            elif any(indicator in container_html.lower() for indicator in ['assistant', 'ai', 'chatgpt', 'bot']):
                return "assistant"
            
            # Strategy 3: Analyze content patterns
            content = await container.inner_text()
            if content:
                return self._guess_role_from_content(content, 0)
            
        except Exception as e:
            logger.debug(f"Error in role determination: {e}")
        
        # Default: return None to indicate uncertainty
        return "unknown"
    
    async def _extract_content(self, container, selectors: List[str]) -> str:
        """Extract content using multiple selectors"""
        for selector in selectors:
            try:
                elements = await container.query_selector_all(selector)
                if elements:
                    texts = []
                    for elem in elements:
                        text = await elem.inner_text()
                        if text and text.strip():
                            texts.append(text.strip())
                    
                    if texts:
                        return '\n'.join(texts)
            except:
                continue
        
        # Fallback: get all text from container
        try:
            full_text = await container.inner_text()
            return full_text.strip() if full_text else ""
        except:
            return ""