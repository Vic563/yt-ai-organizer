import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config import get_settings
from models import ConversationMessage
from cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)

class GeminiService:
    """Service for interacting with Google's Gemini AI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.settings = get_settings()
        
        # Initialize cost tracking service
        self.cost_tracker = CostTrackingService()
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.settings.gemini_model,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
    async def test_connection(self):
        """Test Gemini API connection"""
        try:
            response = self.model.generate_content("Hello, this is a test.")
            logger.info("Gemini API connection test successful")
            return True
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {e}")
            raise Exception(f"Gemini API test failed: {e}")
    
    async def generate_response(
        self, 
        prompt: str, 
        conversation_history: List[ConversationMessage] = None,
        conversation_id: Optional[str] = None,
        query_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate AI response using Gemini with cost tracking"""
        try:
            # Build conversation context
            full_prompt = self._build_conversation_prompt(prompt, conversation_history)
            
            # Generate response
            response = self.model.generate_content(full_prompt)
            
            # Extract response text
            response_text = response.text if response.text else "I apologize, but I couldn't generate a response."
            
            # Get token usage from response metadata if available
            prompt_tokens = 0
            completion_tokens = 0
            
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
            
            # Fallback to estimation if metadata not available
            if prompt_tokens == 0 or completion_tokens == 0:
                prompt_tokens = int(len(full_prompt.split()) * 1.3)  # Rough estimate
                completion_tokens = int(len(response_text.split()) * 1.3)
                logger.warning("Using estimated token counts - actual usage may differ")
            
            total_tokens = prompt_tokens + completion_tokens
            
            # Track usage with cost tracking service
            usage_record = self.cost_tracker.track_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.settings.gemini_model,
                conversation_id=conversation_id,
                query_type=query_type
            )
            
            # Prepare token usage for response
            token_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": usage_record.cost_usd
            }
            
            logger.info(f"Generated response: {total_tokens} tokens, ${usage_record.cost_usd:.6f}")
            
            return {
                "response": response_text,
                "token_usage": token_usage,
                "model": self.settings.gemini_model
            }
            
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise Exception(f"Failed to generate AI response: {str(e)}")
    
    def _build_conversation_prompt(
        self, 
        current_message: str, 
        conversation_history: List[ConversationMessage] = None
    ) -> str:
        """Build complete prompt with system instructions and conversation history"""
        
        system_prompt = """You are Project Insight, an AI assistant specialized in helping users explore and understand their personal YouTube video library. Your role is to act as a conversational research partner.

CORE CAPABILITIES:
1. DISCOVERY MODE: When users ask about topics or want to find videos, recommend relevant videos from their library
2. SYNTHESIS MODE: When users ask specific questions, provide detailed answers using information from their video transcripts

RESPONSE GUIDELINES:
- Always be helpful, conversational, and encouraging
- For discovery queries ("What videos do I have about X?"), focus on finding and recommending relevant videos
- For synthesis queries ("How do you do X?"), provide detailed answers with specific citations
- Use a friendly, knowledgeable tone as if you're a research librarian who knows their collection intimately
- When citing videos, use format: [Video Title, @timestamp] where applicable
- If you can't find relevant content, suggest related topics or ask clarifying questions

RESPONSE FORMAT:
- For video recommendations, provide clear reasoning why each video is relevant
- For answers with citations, include specific timestamps when possible
- Always encourage follow-up questions and deeper exploration

Remember: You are working with the user's personal, curated video library. This is their knowledge base, and you're helping them unlock its value through conversation."""

        # Build conversation history
        conversation_context = ""
        if conversation_history:
            # Limit conversation history to prevent token overflow
            recent_history = conversation_history[-self.settings.max_conversation_history:]
            
            for msg in recent_history:
                role = "Human" if msg.role == "user" else "Assistant"
                conversation_context += f"\n{role}: {msg.content}\n"
        
        # Combine all parts
        full_prompt = f"{system_prompt}\n\nCONVERSATION HISTORY:{conversation_context}\n\nHuman: {current_message}\n\nAssistant:"
        
        return full_prompt
    
    async def analyze_query_intent(self, query: str, conversation_history: List[ConversationMessage] = None) -> Dict[str, Any]:
        """
        Analyze the user's query to determine intent and extract key information.
        
        Args:
            query: The user's query
            conversation_history: List of previous conversation messages for context
            
        Returns:
            Dict containing:
            - intent: 'discovery', 'synthesis', or 'conversational'
            - entities: List of key entities (topics, concepts, etc.)
            - requires_context: Whether this query requires conversation context
            - follow_up: Whether this is a follow-up question
            - query_rewrite: A clearer, more specific version of the query if needed
        """
        try:
            # Build context from conversation history
            context = ""
            if conversation_history and len(conversation_history) > 0:
                # Include last 3 messages for context
                context_messages = conversation_history[-3:]
                context = "\n".join([
                    f"{msg.role.upper()}: {msg.content}" 
                    for msg in context_messages
                ])
            
            # Create the intent analysis prompt
            prompt = f"""Analyze the following user query and conversation context to determine the intent and extract key information.
            
            Respond with a JSON object containing these fields:
            - intent: One of 'discovery', 'synthesis', or 'conversational'
            - entities: List of key topics, concepts, or entities mentioned
            - requires_context: Boolean indicating if this query needs conversation context
            - follow_up: Boolean indicating if this is a follow-up question
            - query_rewrite: A clearer, more specific version of the query if needed, otherwise empty string
            
            Intent definitions:
            - 'discovery': User is looking for specific videos in their library (e.g., "Do I have videos about X?", "What videos do I have on Y?", "Are there any videos about Z?")
            - 'synthesis': User wants analysis or synthesis of information from their video transcripts (e.g., "How do I do X?", "What is Y?", "Explain Z")
            - 'conversational': General conversation, greetings, or questions about capabilities (e.g., "Hello", "What can you do?", "How are you?")
            
            Conversation context (most recent first):
            {context}
            
            Query: "{query}"
            
            Respond with valid JSON only, no other text:"""
            
            # Get response from Gemini
            response = self.model.generate_content(prompt)
            
            # Track usage with cost tracking service
            prompt_tokens = len(prompt.split())
            completion_tokens = len(response.text.split()) if response.text else 0
            total_tokens = prompt_tokens + completion_tokens

            usage_record = self.cost_tracker.track_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self.settings.gemini_model,
                conversation_id="intent_analysis",
                query_type="intent_analysis"
            )
            
            # Parse the JSON response
            try:
                import json
                import re

                # Clean the response text - remove markdown code blocks if present
                response_text = response.text.strip()

                # Remove markdown code blocks
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.startswith('```'):
                    response_text = response_text[3:]   # Remove ```
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # Remove trailing ```

                response_text = response_text.strip()

                result = json.loads(response_text)
                
                # Validate required fields
                if not all(key in result for key in ['intent', 'entities', 'requires_context', 'follow_up', 'query_rewrite']):
                    raise ValueError("Missing required fields in response")
                
                # Validate intent
                if result['intent'] not in ['discovery', 'synthesis', 'conversational']:
                    logger.warning(f"Invalid intent detected: {result['intent']}, defaulting to 'conversational'")
                    result['intent'] = 'conversational'
                
                # Ensure entities is a list
                if not isinstance(result['entities'], list):
                    result['entities'] = [result['entities']] if result['entities'] else []
                
                # Log the analysis for debugging
                logger.debug(f"Query analysis result: {result}")
                
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error parsing intent analysis: {e}. Response: {response.text}")
                # Fallback to simple intent detection
                return {
                    'intent': 'conversational',
                    'entities': [],
                    'requires_context': True,
                    'follow_up': False,
                    'query_rewrite': ''
                }
            
        except Exception as e:
            logger.error(f"Error in analyze_query_intent: {e}")
            return {
                'intent': 'conversational',
                'entities': [],
                'requires_context': True,
                'follow_up': False,
                'query_rewrite': ''
            }
    
    async def generate_video_relevance_reason(self, query: str, video_title: str, video_description: str = "") -> str:
        """Generate explanation for why a video is relevant to the query"""
        try:
            relevance_prompt = f"""Explain in one concise sentence why this video is relevant to the user's query.

Query: "{query}"
Video Title: "{video_title}"
Video Description: "{video_description[:200]}..."

Provide a brief, helpful explanation of the relevance:"""

            response = self.model.generate_content(relevance_prompt)
            
            # Track cost for relevance generation
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
                total_tokens = input_tokens + output_tokens
            else:
                # Fallback estimation
                total_tokens = len(relevance_prompt.split()) + len(response.text.split()) if response.text else 0
            
            # Track usage for relevance generation
            await self.cost_tracker.track_usage(
                conversation_id="relevance_generation",
                query_type="relevance_generation",
                input_tokens=input_tokens if 'input_tokens' in locals() else total_tokens // 2,
                output_tokens=output_tokens if 'output_tokens' in locals() else total_tokens // 2,
                total_tokens=total_tokens
            )
            
            return response.text.strip() if response.text else "This video appears relevant to your query."
            
        except Exception as e:
            logger.warning(f"Error generating relevance reason: {e}")
            return "This video may contain relevant information."
    
    async def extract_citations_from_transcript(
        self, 
        query: str, 
        transcript: str, 
        video_title: str
    ) -> List[Dict[str, Any]]:
        """Extract relevant citations from video transcript"""
        try:
            citation_prompt = f"""Given this user query and video transcript, identify the most relevant sections that answer the query.

Query: "{query}"
Video: "{video_title}"
Transcript: "{transcript[:3000]}..."

Find 1-3 most relevant sections and provide them in this format:
CITATION: [Brief description of what this section covers]
RELEVANCE: [Why this is relevant to the query]

Focus on sections that directly answer or relate to the user's question."""

            response = self.model.generate_content(citation_prompt)
            
            # Parse response to extract citations
            # This is a simplified version - could be enhanced with more sophisticated parsing
            citations = []
            if response.text:
                sections = response.text.split("CITATION:")
                for section in sections[1:]:  # Skip first empty section
                    if "RELEVANCE:" in section:
                        parts = section.split("RELEVANCE:")
                        if len(parts) >= 2:
                            citations.append({
                                "description": parts[0].strip(),
                                "relevance": parts[1].strip(),
                                "video_title": video_title
                            })
            
            return citations[:3]  # Limit to 3 citations
            
        except Exception as e:
            logger.warning(f"Error extracting citations: {e}")
            return []
