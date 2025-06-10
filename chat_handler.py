import logging
import uuid
import random
from typing import List, Dict, Any
from models import ConversationMessage, ChatResponse, VideoCitation, VideoRecommendation
from gemini_service import GeminiService
from youtube_service import YouTubeService
from database import get_videos_by_query, get_all_videos

logger = logging.getLogger(__name__)

class ChatHandler:
    """Main chat handler that orchestrates AI responses"""
    
    def __init__(self, gemini_service: GeminiService, youtube_service: YouTubeService):
        self.gemini = gemini_service
        self.youtube = youtube_service
    
    async def process_message(
        self, 
        message: str, 
        conversation_history: List[ConversationMessage] = None
    ) -> ChatResponse:
        """
        Process user message and generate appropriate response
        
        Args:
            message: The user's message
            conversation_history: List of previous conversation messages for context
            
        Returns:
            ChatResponse object with the generated response
        """
        try:
            logger.info(f"Processing message: {message[:100]}...")
            
            # Generate conversation ID for cost tracking if not provided
            conversation_id = str(uuid.uuid4())
            
            # Analyze query intent and extract context
            intent_analysis = await self.gemini.analyze_query_intent(
                message, 
                conversation_history=conversation_history
            )
            
            logger.info(f"Query analysis: {intent_analysis}")
            
            # Use the rewritten query if available, otherwise use original message
            effective_query = intent_analysis.get('query_rewrite', message).strip()
            if not effective_query:  # If rewrite is empty, fall back to original
                effective_query = message
                
            # Prepare context for the handler
            context = {
                'conversation_id': conversation_id,
                'intent': intent_analysis['intent'],
                'entities': intent_analysis.get('entities', []),
                'requires_context': intent_analysis.get('requires_context', True),
                'follow_up': intent_analysis.get('follow_up', False),
                'original_query': message,
                'effective_query': effective_query
            }
            
            # Route to appropriate handler based on intent
            intent = intent_analysis['intent']
            if intent == "discovery":
                return await self._handle_discovery_query(
                    effective_query, 
                    conversation_history, 
                    conversation_id,
                    context
                )
            elif intent == "synthesis":
                return await self._handle_synthesis_query(
                    effective_query, 
                    conversation_history, 
                    conversation_id,
                    context
                )
            else:  # conversational
                return await self._handle_conversational_query(
                    effective_query, 
                    conversation_history, 
                    conversation_id,
                    context
                )
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return ChatResponse(
                message="I apologize, but I encountered an error processing your request. Please try again.",
                type="error"
            )
    
    async def _handle_discovery_query(
        self, 
        query: str, 
        conversation_history: List[ConversationMessage] = None,
        conversation_id: str = None,
        context: Dict[str, Any] = None
    ) -> ChatResponse:
        """
        Handle discovery-focused queries (finding videos)
        
        Args:
            query: The user's search query
            conversation_history: List of previous conversation messages
            conversation_id: Unique ID for the conversation
            context: Additional context from intent analysis
            
        Returns:
            ChatResponse with video recommendations
        """
        logger.info(f"Handling discovery query: {query}")
        
        # Extract entities from context if available for better search
        search_terms = [query]
        if context and 'entities' in context and context['entities']:
            search_terms.extend(context['entities'])
        
        # Use the most specific search term (longest) for better relevance
        search_query = max(search_terms, key=len) if search_terms else query
        
        # Search for relevant videos
        relevant_videos = get_videos_by_query(search_query, limit=10)
        
        # If no results and this is a follow-up, try with the original query
        if not relevant_videos and context and context.get('follow_up') and query != context.get('original_query', query):
            logger.info("No results with rewritten query, trying with original query")
            relevant_videos = get_videos_by_query(context['original_query'], limit=10)
        
        # Convert to video recommendations with AI-generated relevance reasons
        video_recommendations = []
        for video in relevant_videos[:5]:  # Limit to 5 recommendations
            try:
                # Only generate relevance reason if we have a non-empty query
                relevance_reason = ""
                if query.strip():
                    relevance_reason = await self.gemini.generate_video_relevance_reason(
                        query, 
                        video['title'], 
                        video.get('description', '')
                    )
                
                recommendation = VideoRecommendation(
                    id=video['video_id'],
                    title=video['title'],
                    thumbnail=video.get('thumbnail_url'),
                    duration=video.get('duration'),
                    published_at=video.get('published_at'),
                    channel_title=video.get('channel_title'),
                    description=video.get('description', '')[:200] + "..." if video.get('description') else None,
                    relevance_reason=relevance_reason,
                    url=f"https://www.youtube.com/watch?v={video['video_id']}",
                    score=video.get('score', 0)  # Include relevance score if available
                )
                video_recommendations.append(recommendation)
                
            except Exception as e:
                logger.warning(f"Error processing video {video.get('video_id', 'unknown')}: {e}", exc_info=True)
                continue
        
        # Sort by relevance score if available
        video_recommendations.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)
        
        # Generate conversational response
        if video_recommendations:
            if context and context.get('follow_up'):
                response_text = f"Here are some videos that might be relevant to what we were discussing about '{context.get('original_query', query)}':"
            else:
                response_text = f"I found {len(video_recommendations)} videos that might be relevant to your query about '{query}':"
            
            # Previously the assistant appended follow-up suggestions asking the
            # user if they wanted comparisons or summaries. These suggestions
            # were removed to keep responses concise and avoid interrupting the
            # user's flow.
                
        else:
            response_text = f"I couldn't find any videos related to '{query}' in your library. "
            
            # Previously additional suggestions were appended when no videos
            # were found. These prompts encouraged rephrasing the query or
            # adding new videos. They have been removed to allow the user to
            # decide the next step without unsolicited guidance.
        
        return ChatResponse(
            message=response_text,
            type="discovery",
            videos=video_recommendations,
            context=context  # Include context in the response for UI/UX purposes
        )
    
    async def _handle_synthesis_query(
        self, 
        query: str, 
        conversation_history: List[ConversationMessage] = None,
        conversation_id: str = None,
        context: Dict[str, Any] = None
    ) -> ChatResponse:
        """
        Handle synthesis-focused queries (answering questions)
        
        Args:
            query: The user's question or query
            conversation_history: List of previous conversation messages
            conversation_id: Unique ID for the conversation
            context: Additional context from intent analysis
            
        Returns:
            ChatResponse with synthesized answer and relevant citations
        """
        logger.info(f"Handling synthesis query: {query}")
        
        # Use the effective query from context if available, otherwise use the original query
        effective_query = context.get('effective_query', query) if context else query
        
        # If this is a follow-up, include previous context in the search
        search_query = effective_query
        if context and context.get('follow_up') and context.get('original_query'):
            search_query = f"{context['original_query']} {effective_query}"
        
        # Find potentially relevant videos
        relevant_videos = get_videos_by_query(search_query, limit=5)
        
        # If no videos found, try with just the original query
        if not relevant_videos and search_query != effective_query:
            relevant_videos = get_videos_by_query(effective_query, limit=5)
        
        # If still no videos, try with just the original query from context
        if not relevant_videos and context and context.get('original_query'):
            relevant_videos = get_videos_by_query(context['original_query'], limit=5)
        
        # Collect transcripts from relevant videos with relevance scoring
        transcript_context = ""
        citations = []
        processed_videos = set()  # Avoid duplicate videos
        
        for video in relevant_videos:
            if video['video_id'] in processed_videos:
                continue
                
            processed_videos.add(video['video_id'])
            
            # Get transcript with error handling
            try:
                transcript = self.youtube.get_transcript_from_file(video['video_id'])
                if not transcript:
                    logger.debug(f"No transcript found for video: {video['video_id']}")
                    continue
                    
                # Add transcript context (truncated to manage token usage)
                video_context = f"\n\n--- Video: {video['title']} (Relevance: {video.get('score', 0):.1f}) ---\n{transcript[:1500]}...\n"
                transcript_context += video_context
                
                # Generate citations for this video
                citations.append(VideoCitation(
                    video_id=video['video_id'],
                    title=video['title'],
                    timestamp="00:00",  # Default timestamp
                    relevance_score=video.get('score', 0)
                ))
                
            except Exception as e:
                logger.warning(f"Error processing video {video.get('video_id', 'unknown')}: {e}", exc_info=True)
                continue
                
        # If we have no transcript context, handle the no-results case
        if not transcript_context:
            logger.warning(f"No relevant transcripts found for query: {query}")
            
            # Try to be helpful based on the context
            if context and context.get('entities'):
                entities_str = ", ".join(f"'{e}'" for e in context['entities'])
                message = f"I couldn't find any information about {entities_str} in your video library. "
            else:
                message = f"I couldn't find any information about '{query}' in your video library. "
            
            message += "This could be because:\n"
            message += "• The topic isn't covered in your videos\n"
            message += "• The videos might use different terminology\n"
            message += "• The videos might not have transcripts available\n\n"
            # The previous version prompted the user to try a different search.
            # This suggestion has been removed to keep the response focused on
            # the current query.
            
            return ChatResponse(
                message=message,
                type="synthesis",
                context=context
            )
        
        # Build enhanced prompt with transcript context
        enhanced_prompt = f"""Based on the user's question and the following video transcripts from their library, provide a comprehensive answer.

User Question: "{effective_query}"

Video Transcripts:
{transcript_context}

Please provide a detailed answer using the information from these videos. If you reference specific information, mention which video it came from. If the transcripts don't contain enough information to fully answer the question, say so and suggest what additional information might be helpful."""
        
        # Generate AI response with context
        try:
            # Get the response from Gemini
            response = await self.gemini.generate_response(
                prompt=enhanced_prompt,
                conversation_history=conversation_history,
                conversation_id=conversation_id,
                query_type="synthesis"
            )
            
            # Format the response with citations
            response_text = response.text.strip()
            
            # If we have citations, add them to the response
            if citations:
                response_text += "\n\nSources:"
                for i, citation in enumerate(citations, 1):
                    response_text += f"\n{i}. {citation.title} - {self._format_video_url(citation.video_id, citation.timestamp)}"
            
            # Previous versions appended follow-up prompts offering additional
            # searches or details. These have been removed to avoid cluttering
            # the assistant's response with unsolicited suggestions.
            
            return ChatResponse(
                message=response_text,
                type="synthesis",
                citations=citations,
                context=context
            )
            
        except Exception as e:
            logger.error(f"Error generating synthesis response: {e}", exc_info=True)
            
            # Fallback response with the videos we found
            if relevant_videos:
                return ChatResponse(
                    message=f"I found some videos that might contain information about '{effective_query}', but I'm having trouble processing the content right now. You might want to check these videos directly, or try rephrasing your question.",
                    type="synthesis",
                    videos=[
                        VideoRecommendation(
                            id=video['video_id'],
                            title=video['title'],
                            url=f"https://www.youtube.com/watch?v={video['video_id']}",
                            relevance_reason=f"Relevance score: {video.get('score', 0):.1f}"
                        ) for video in relevant_videos[:3]
                    ],
                    context=context
                )
            else:
                return ChatResponse(
                    message=f"I'm sorry, but I couldn't find any videos related to '{effective_query}' in your library.",
                    type="synthesis",
                    context=context
                )

    async def _handle_conversational_query(
        self, 
        query: str, 
        conversation_history: List[ConversationMessage] = None,
        conversation_id: str = None,
        context: Dict[str, Any] = None
    ) -> ChatResponse:
        """
        Handle conversational queries (greetings, general chat, non-video questions)
        
        Args:
            query: The user's message
            conversation_history: List of previous conversation messages
            conversation_id: Unique ID for the conversation
            context: Additional context from intent analysis
            
        Returns:
            ChatResponse with a conversational response
        """
        logger.info(f"Handling conversational query: {query}")
        
        # Use the effective query from context if available (e.g., for follow-ups)
        effective_query = context.get('effective_query', query) if context else query
        
        # Check if this is a follow-up to a previous query
        is_follow_up = context and context.get('follow_up', False)
        
        # Build conversational prompt with context
        prompt_parts = [
            "You are Project Insight, an AI assistant that helps users explore and understand "
            "their personal YouTube video library.",
            "",
            "The user has sent you a message:",
            f'"{effective_query}"',
            ""
        ]
        
        # Add context if this is a follow-up
        if is_follow_up and context.get('original_query'):
            prompt_parts.extend([
                f"This is a follow-up to your previous query about: {context['original_query']}",
                ""
            ])
        
        # Add conversation history for context
        if conversation_history and len(conversation_history) > 0:
            prompt_parts.append("Previous conversation context:")
            for msg in conversation_history[-3:]:  # Only use last 3 messages for context
                role = "User" if msg.role == "user" else "Assistant"
                prompt_parts.append(f"{role}: {msg.content}")
            prompt_parts.append("")
        
        # Add instructions with strict constraints
        prompt_parts.extend([
            "IMPORTANT: You are an AI assistant that helps users explore their PERSONAL YouTube video library.",
            "You must ONLY reference videos that exist in the user's personal collection.",
            "NEVER suggest, recommend, or mention videos that are not in their library.",
            "NEVER hallucinate or make up video titles, content, or recommendations.",
            "",
            "Please respond in a friendly, helpful manner. Here's what you can help with:",
            "- Answering general questions about the user's video library",
            "- Helping find specific videos or topics IN THEIR LIBRARY",
            "- Explaining concepts from the user's videos",
            "- Suggesting ways to organize or explore their library",
            "",
            "If the user asks about videos on a topic, you should:",
            "1. Acknowledge their question",
            "2. Offer to search their personal library for relevant videos",
            "3. NEVER suggest external videos or content not in their library",
            "",
            "Keep your response concise and focused.",
            "",
            "Your response:"
        ])
        
        conversational_prompt = "\n".join(prompt_parts)
        
        try:
            # Get the response from Gemini
            response = await self.gemini.generate_response(
                prompt=conversational_prompt,
                conversation_history=conversation_history,
                conversation_id=conversation_id,
                query_type="conversational"
            )
            
            # Format the response - handle both dict and object response formats
            if isinstance(response, dict):
                # Extract just the response text from the dictionary
                if 'response' in response:
                    response_text = response['response'].strip()
                else:
                    # Fallback to using the first string value we can find
                    for key, value in response.items():
                        if isinstance(value, str) and key != 'model':
                            response_text = value.strip()
                            break
                    else:
                        # If no string value found, use a default response
                        response_text = "I'm here to help you explore your YouTube library. What would you like to know?"                
            else:
                response_text = response.text.strip()
            
            # Add a helpful follow-up if this was a follow-up
            if is_follow_up:
                if "?" in effective_query:  # If it was a question
                    response_text += "\n\nDoes this help answer your question, or would you like me to look for more specific information in your video library?"
                else:
                    response_text += "\n\nIs there anything else you'd like to know about this topic or would you like to explore something else in your video library?"
            
            return ChatResponse(
                message=response_text,
                type="conversational",
                context=context
            )
            
        except Exception as e:
            logger.error(f"Error generating conversational response: {e}", exc_info=True)
            
            # Fallback response
            fallback_responses = [
                "I'm having trouble understanding that right now. Could you rephrase your question or ask me something else?",
                "I'm not quite sure how to respond to that. I can help you find videos or answer questions about your library. What would you like to know?",
                "I'm still learning! Could you try asking me in a different way? I'm best at helping you find and understand videos in your library."
            ]
            
            # Add context-aware fallback if available
            if context and context.get('intent') == 'greeting':
                fallback_responses.append("Hello! I'm here to help you explore your YouTube video library. What would you like to do?")
            elif context and context.get('intent') == 'capabilities':
                fallback_responses.append("I can help you search through your YouTube video library, answer questions about your videos, and provide insights about your content. Just let me know what you're looking for!")
            
            return ChatResponse(
                message=random.choice(fallback_responses),
                type="conversational",
                context=context
            )

    def _format_video_url(self, video_id: str, timestamp: str = None) -> str:
        """Format YouTube URL with optional timestamp"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        if timestamp:
            # Convert timestamp to seconds if needed
            if ':' in timestamp:  # Format: HH:MM:SS or MM:SS
                parts = timestamp.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    h, m, s = parts
                    seconds = int(h) * 3600 + int(m) * 60 + int(s)
                else:  # MM:SS
                    m, s = parts
                    seconds = int(m) * 60 + int(s)
                timestamp = str(seconds)
            url += f"&t={timestamp}"
        return url
