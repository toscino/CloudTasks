"""
RewardGenerator - Handles AI-powered reward generation logic
"""
from openai import OpenAI
from .AITaskPrompt import AITaskPrompt
import random
import json
from datetime import datetime
from google.cloud import firestore
from src.utils.logger import logger


class RewardGenerator(AITaskPrompt):
    def __init__(self, db, cheapmode=False):
        super().__init__()
        
        self.db = db
        self.user = None  # Will be set when generating rewards
       
        if cheapmode:
            self.model = "gpt-5-nano"
        else:
            self.model = "gpt-5-mini"

        logger.debug(f"Initializing AI Reward Generator with model: {self.model}")
        
        # Initialize OpenAI client - API key should be in environment
        self.client = OpenAI()
    
    def format_prompt_theme(self, context, user, num_rewards=4):
        """Format prompt for reward generation"""
        prompt = f"You are generating special reward options for {user}.\n"
        prompt += f"These are intimate/playful activities that {user}'s spouse will do for {user} as a treat {user} earned.\n"

        prompt += self.REWARD_PROMPT
  
        if context:
            prompt += f"Context about {user}'s current life:\n{context.strip()}\n\n"

        prompt += "\nRequested Rewards:\n"

        for i in range(num_rewards):
            themes = random.sample(self.REWARD_THEMES[user.lower()], 2)
            if random.random() < 0.2:
                themes[0] = "Make up a theme"
            prompt += f"Theme for Reward {i+1}: [{themes[0]}] and [{themes[1]}]\n"

        prompt += f"\n\nGenerate the {num_rewards} options for {user} to select as a JSON array with 'themes' and 'reward'. Do not return Theme Examples, Do not return Duration or Difficulty."
        return prompt

    def generate_rewards(self, context, user, num_rewards=4):
        """Generate rewards via AI"""
        logger.debug(f"Generating {num_rewards} reward options for {user}")
        user_prompt = self.format_prompt_theme(context, user, num_rewards)
        response = self.get_response(user_prompt)
        
        # Parse the JSON response into a Python array
        if response:
            try:
                # Clean the response - remove any markdown formatting
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                logger.debug(f"Cleaned response: {cleaned_response[:200]}...")
                parsed_rewards = json.loads(cleaned_response)
                logger.debug(f"Successfully parsed {len(parsed_rewards)} reward options")
                
                # Debug: Check for nested arrays in themes
                for i, reward in enumerate(parsed_rewards):
                    if isinstance(reward.get("themes"), list):
                        for j, theme in enumerate(reward["themes"]):
                            if isinstance(theme, list):
                                logger.debug(f"Found nested array in reward {i}, theme {j}: {theme}")
                
                # Process each reward
                for reward in parsed_rewards:
                    reward["type"] = "Reward"
                    # Handle themes that might be nested lists
                    if isinstance(reward["themes"], list):
                        # Recursively flatten the themes list
                        def flatten_themes(themes):
                            flat_list = []
                            for theme in themes:
                                if isinstance(theme, list):
                                    flat_list.extend(flatten_themes(theme))
                                elif theme and str(theme).strip():  # Only add non-empty themes
                                    flat_list.append(str(theme).strip())
                            return flat_list
                        
                        flat_themes = flatten_themes(reward["themes"])
                        # Update the themes field to be a flat list for Firestore
                        reward["themes"] = flat_themes
                        themes_str = ", ".join(flat_themes)
                        logger.debug(f"Flattened themes for reward: {flat_themes}")
                    else:
                        themes_str = str(reward["themes"])
                    reward["display"] = f"[{themes_str}] - {reward['reward']}"
                
                return parsed_rewards
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response was: {response}")
                return []
        else:
            logger.error("No response received from AI")
        return []
    
    def get_response(self, prompt):
        """Get OpenAI API response"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=1
            )
            
            # Log AI call with token usage
            tokens_used = response.usage.total_tokens
            logger.ai_call(
                username=self.user or "unknown",
                purpose="reward_generation",
                model=self.model,
                tokens_used=tokens_used,
                success=True,
                summary=f"Generated rewards using {tokens_used} tokens"
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.ai_call(
                username=self.user or "unknown",
                purpose="reward_generation",
                model=self.model,
                tokens_used=0,
                success=False,
                summary=f"Failed: {str(e)}"
            )
            logger.error(f"Error getting response: {e}")
            return None
    
    def generate_reward_options_for_user(self, username, context=None, count=4, upload_to_firestore=True):
        """Generate AI reward options for user"""
        if count is None:
            return []
            
        # Set user for this generation
        self.user = username
        
        # Generate reward options using AI
        ai_rewards = self.generate_rewards(context, username, count)
        
        # Convert AI rewards to Firestore format and store them (if requested)
        generated_rewards = []
        for i, ai_reward in enumerate(ai_rewards):
            try:
                reward_data = {
                    'username': username,
                    'description': ai_reward['reward'],
                    'themes': ai_reward['themes'],
                    'display': ai_reward['display'],
                    'type': 'Reward',
                    'selected': False,
                    'used': False,  # Add the 'used' field for querying
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }
                
                if upload_to_firestore and self.db is not None:
                    doc_ref = self.db.collection('reward_options').add(reward_data)
                    reward_data['id'] = doc_ref[1].id
                    reward_data['created_at'] = datetime.now()  # For immediate use
                    reward_data['updated_at'] = datetime.now()  # For immediate use
                    logger.debug(f"Generated reward option for {username}: {ai_reward['reward']}")
                else:
                    # Simulation mode - just add a placeholder ID
                    reward_data['id'] = f"sim_reward_{i}_{datetime.now().timestamp()}"
                    reward_data['created_at'] = datetime.now()
                    reward_data['updated_at'] = datetime.now()
                    logger.debug(f"Generated reward option for {username} (simulation): {ai_reward['reward']}")
                
                generated_rewards.append(reward_data)
                
            except Exception as e:
                logger.error(f"Error generating reward option for {username}: {e}")
        
        return generated_rewards
