import openai
import os
from typing import List, Dict

class AIService:
    def __init__(self):
        # Set up OpenAI API key
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            print("Warning: OPENAI_API_KEY not found in environment variables")
    
    def get_chat_response(self, message: str, conversation_history: List[Dict] = None) -> str:
        """
        Get a response from the AI chatbot
        
        Args:
            message: The user's message
            conversation_history: Previous conversation messages
            
        Returns:
            AI response string
        """
        try:
            # If no OpenAI API key, return a mock response
            if not openai.api_key:
                return self._get_mock_response(message)
            
            # Build conversation context
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant. Be friendly, informative, and concise in your responses."}
            ]
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Get AI response using OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return response['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"Error getting AI response: {e}")
            return self._get_mock_response(message)
    
    def _get_mock_response(self, message: str) -> str:
        """
        Generate a mock response when OpenAI API is not available
        """
        message_lower = message.lower()
        
        if "hello" in message_lower or "hi" in message_lower:
            return "Hello! I'm your AI assistant. How can I help you today?"
        elif "how are you" in message_lower:
            return "I'm doing great, thank you for asking! I'm here to help you with any questions or tasks you might have."
        elif "what can you do" in message_lower:
            return "I can help you with various tasks like answering questions, providing information, and assisting with your social media content management. What would you like to know more about?"
        elif "social media" in message_lower:
            return "I can help you manage your social media content! You can upload videos and images, and I'll help generate engaging captions and hashtags for platforms like YouTube, Instagram, Facebook, and TikTok."
        elif "upload" in message_lower:
            return "To upload media, use the media management panel on the right side of the interface. I can help generate captions and hashtags based on your content!"
        elif "thank" in message_lower:
            return "You're welcome! I'm always here to help. Is there anything else you'd like to know?"
        else:
            return f"I understand you're asking about: '{message}'. I'm here to help! Could you provide more details about what you'd like to know?"
    
    def generate_social_media_content(self, media_info: Dict, platform: str = "general", custom_prompt: str = "") -> Dict:
        """
        Generate hashtags and captions for social media content
        
        Args:
            media_info: Information about the media file
            platform: Target social media platform
            custom_prompt: Additional context from user
            
        Returns:
            Dictionary with caption, hashtags, and suggested_time
        """
        try:
            if not openai.api_key:
                return self._get_mock_social_content(media_info, platform)
            
            # Create prompt based on file type and platform
            base_prompt = f"""
            Generate engaging social media content for a {media_info.get('file_type', 'media')} file named "{media_info.get('filename', 'content')}" 
            that will be posted on {platform}. 
            
            Please provide:
            1. A compelling caption/description (appropriate length for {platform})
            2. Relevant hashtags (trending and niche-specific)
            3. Suggested posting time for maximum engagement
            
            {f"Additional context: {custom_prompt}" if custom_prompt else ""}
            
            Format the response as JSON with keys: caption, hashtags (array), suggested_time
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a social media expert who creates viral content. Always respond with valid JSON."},
                    {"role": "user", "content": base_prompt}
                ],
                max_tokens=800,
                temperature=0.8
            )
            
            ai_response = response['choices'][0]['message']['content']
            
            # Try to parse JSON response
            import json
            try:
                content_data = json.loads(ai_response)
            except json.JSONDecodeError:
                # Fallback if AI doesn't return valid JSON
                content_data = {
                    "caption": ai_response[:500],
                    "hashtags": ["#viral", "#trending", "#content"],
                    "suggested_time": "Peak hours: 7-9 PM"
                }
            
            return content_data
            
        except Exception as e:
            print(f"Error generating social media content: {e}")
            return self._get_mock_social_content(media_info, platform)
    
    def _get_mock_social_content(self, media_info: Dict, platform: str) -> Dict:
        """
        Generate mock social media content when OpenAI API is not available
        """
        file_type = media_info.get('file_type', 'media')
        filename = media_info.get('filename', 'content')
        
        # Platform-specific content
        platform_data = {
            'youtube': {
                'caption': f"Check out this amazing {file_type}! Don't forget to like and subscribe for more content like this. What do you think? Let me know in the comments below!",
                'hashtags': ['#YouTube', '#Content', '#Subscribe', '#Like', '#Share'],
                'suggested_time': 'Best times: 2-4 PM or 8-10 PM on weekdays'
            },
            'instagram': {
                'caption': f"✨ New {file_type} alert! ✨ Swipe to see more and don't forget to double-tap if you love it! 💖",
                'hashtags': ['#Instagram', '#InstaGood', '#PhotoOfTheDay', '#Content', '#Viral'],
                'suggested_time': 'Peak engagement: 11 AM-1 PM or 7-9 PM'
            },
            'facebook': {
                'caption': f"Sharing this incredible {file_type} with all my friends! What are your thoughts? Tag someone who would love this!",
                'hashtags': ['#Facebook', '#Share', '#Friends', '#Content', '#Viral'],
                'suggested_time': 'Best times: 1-3 PM or 7-9 PM'
            },
            'tiktok': {
                'caption': f"🔥 This {file_type} is everything! Follow for more content like this! #fyp",
                'hashtags': ['#TikTok', '#FYP', '#Viral', '#Trending', '#ForYou'],
                'suggested_time': 'Peak hours: 6-10 AM or 7-9 PM'
            }
        }
        
        default_content = {
            'caption': f"Check out this amazing {file_type}! Hope you enjoy it as much as I do. Let me know what you think!",
            'hashtags': ['#content', '#viral', '#trending', '#social', '#media'],
            'suggested_time': 'Peak engagement hours: 7-9 PM'
        }
        
        return platform_data.get(platform.lower(), default_content)

