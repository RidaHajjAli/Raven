import logging
import re
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger(__name__)

class InsightExtractor:
    """Extracts insights and generates titles from conversation data"""
    
    async def generate_title(self, conversation_data: List[Dict]) -> str:
        """Generate a title from the first user message"""
        try:
            # Find first user message
            first_user_msg = None
            user_name = "user"
            
            for msg in conversation_data:
                if msg.get('role') == 'user':
                    first_user_msg = msg.get('content', '')
                    break
            
            if not first_user_msg:
                return f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Extract name if mentioned
            name_patterns = [
                r"my name is (\w+)",
                r"i'm (\w+)",
                r"i am (\w+)",
                r"call me (\w+)"
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, first_user_msg.lower())
                if match:
                    user_name = match.group(1)
                    break
            
            # Get first 3-5 words for summary
            words = first_user_msg.split()[:5]
            summary = "_".join(word.lower().strip('.,!?') for word in words if word.isalnum())
            
            # Clean and format title
            title = f"{user_name}_{summary}"
            title = re.sub(r'[^\w\-_]', '', title)[:50]  # Limit length and clean
            
            return title if title else f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            return f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    async def extract_insights(self, conversation_data: List[Dict]) -> Optional[Dict]:
        """Extract structured insights from conversation data using LLM"""
        try:
            logger.info("Extracting insights from conversation")
            
            # Prepare conversation text
            conversation_text = self._format_conversation_for_analysis(conversation_data)
            
            prompt = f"""
            Analyze the following conversation and extract structured insights in JSON format.
            
            Conversation:
            {conversation_text}
            
            Extract the following information and return as valid JSON:
            {{
                "user_name": "extracted name or null",
                "user_background": "brief description of user background/context",
                "main_topic": "primary topic discussed",
                "problem_described": "main problem or question raised",
                "solution_provided": "key solution or advice given",
                "tags": ["tag1", "tag2", "tag3"],
                "sentiment": "positive/neutral/negative",
                "created_at": "{datetime.now().isoformat()}"
            }}
            
            Return ONLY valid JSON, no other text.
            """
            
            payload = {
                "model": settings.LOCAL_LLM_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "You are a conversation analyst that returns only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.LOCAL_URL}",
                    json=payload,
                    timeout=120
                ) as response:
                    if response.status != 200:
                        logger.error(f"Insight extraction failed with status {response.status}")
                        return self._generate_fallback_insights(conversation_data)
                    
                    data = await response.json()
                    content = data.get('message', {}).get('content', '')
                    
                    # Try to parse JSON from response
                    insights = self._parse_json_response(content)
                    
                    if insights:
                        logger.info("✅Successfully extracted insights using LLM")
                        return insights
                    else:
                        logger.warning("Failed to parse LLM response, using fallback")
                        return self._generate_fallback_insights(conversation_data)
                        
        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return self._generate_fallback_insights(conversation_data)
    
    def _format_conversation_for_analysis(self, conversation_data: List[Dict]) -> str:
        """Format conversation for LLM analysis"""
        formatted = []
        for msg in conversation_data:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted.append(f"{role.upper()}: {content}")
        
        return '\n\n'.join(formatted)
    
    def _parse_json_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        import json
        
        try:
            # Try direct JSON parsing
            return json.loads(content)
        except:
            pass
        
        try:
            # Look for JSON block in response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return None
    
    def _generate_fallback_insights(self, conversation_data: List[Dict]) -> Dict:
        """Generate basic insights without LLM"""
        logger.info("Generating fallback insights")
        
        # Extract basic information
        user_messages = [msg['content'] for msg in conversation_data if msg.get('role') == 'user']
        assistant_messages = [msg['content'] for msg in conversation_data if msg.get('role') == 'assistant']
        
        # Simple name extraction
        user_name = None
        if user_messages:
            first_msg = user_messages[0].lower()
            name_patterns = [
                r"my name is (\w+)",
                r"i'm (\w+)",
                r"i am (\w+)",
                r"call me (\w+)"
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, first_msg)
                if match:
                    user_name = match.group(1)
                    break
        
        # Basic topic extraction (first few words of first user message)
        main_topic = "General conversation"
        if user_messages:
            words = user_messages[0].split()[:5]
            main_topic = " ".join(words)
        
        # Simple sentiment analysis
        sentiment = "neutral"
        all_text = " ".join(user_messages + assistant_messages).lower()
        positive_words = ["good", "great", "excellent", "thank", "helpful", "amazing"]
        negative_words = ["bad", "terrible", "awful", "problem", "issue", "error"]
        
        pos_count = sum(1 for word in positive_words if word in all_text)
        neg_count = sum(1 for word in negative_words if word in all_text)
        
        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        
        return {
            "user_name": user_name,
            "user_background": "Not specified",
            "main_topic": main_topic,
            "problem_described": user_messages[0] if user_messages else "No problem specified",
            "solution_provided": assistant_messages[0] if assistant_messages else "No solution provided",
            "tags": ["conversation", "chat"],
            "sentiment": sentiment,
            "created_at": datetime.now().isoformat()
        }