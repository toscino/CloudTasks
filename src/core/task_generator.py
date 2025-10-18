"""
TaskGenerator - Handles AI-powered task generation logic
"""
from openai import OpenAI
from .AITaskPrompt import AITaskPrompt
import random
import json
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from src.utils.logger import logger


difficulty_weights = {
    1: 5,   # 5% chance
    2: 20,  # 20% chance
    3: 25,  # 25% chance
    4: 25,  # 25% chance
    5: 15,  # 15% chance
    6: 10,  # 10% chance
    7: 3,   # 3% chance
    8: 2,   # 2% chance
    9: 2,   # 2% chance
    10: 3   # 3% chance
}

class TaskGenerator(AITaskPrompt):
    def __init__(self, db, cheapmode=False):
        super().__init__()
        
        self.db = db
        self.user = None  # Will be set when generating tasks
       
        if cheapmode:
            self.model = "gpt-5-nano"   # Cheaper model
        else:
            self.model = "gpt-5-mini"   # Better model

        logger.debug(f"Initializing AI Task Generator with model: {self.model}")
        
        # Initialize OpenAI client - API key should be in environment
        self.client = OpenAI()
    
    def format_prompt(self, context, taskList, user):
        prompt = ""

        if context:
            prompt += f"Context about {user}'s current life:\n{context.strip()}\n\n"

        targets = set()
        combos = set()
        for task in taskList:
            combo = (user, task["target"])
            if combo not in combos:
                combos.add(combo)
            if task["target"] not in targets:
                targets.add(task["target"])
                
        for combo in combos:
            prompt += f"Context about tasks where {combo[0]} is targeting {combo[1]}:\n {self.TARGETS[combo[0]][combo[1]].strip()}\n\n"

        for target in targets:
            all_examples = []
            # Map target to correct EXAMPLES key
            if target == "Self":
                examples_key = "self"
            elif target == "Spouse":
                if user == "Ian":
                    examples_key = "karleigh"  # Ian's spouse tasks
                elif user == "Karleigh":
                    examples_key = "ian"  # Karleigh's spouse tasks
                else:
                    examples_key = "spouse"  # Fallback for other users
            else:  # Kids, Work, House
                examples_key = target.lower()
            
            for difficulty, examples in self.EXAMPLES[examples_key].items():
                for example in examples:
                    all_examples.append((difficulty, example))

            prompt += f"\nExamples tasks and difficulties for {user} targeting {target}:\n"
            examples = random.sample(all_examples, 3)
            for example in examples:
                prompt += f"  Difficulty {example[0]}: {example[1]}\n"

        prompt += "\nRequested Tasks:\n"
        prompt += str(taskList)
        prompt += f"\n\nGenerate the {len(taskList)} tasks for {user} to accomplish as a JSON array with target, description, duration, and difficulty."
        return prompt

    def generate_tasks(self, context, tasks, user):
        logger.debug(f"Generating {len(tasks)} tasks for {user}")
        user_prompt = self.format_prompt(context, tasks, user)
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
                parsed_tasks = json.loads(cleaned_response)
                logger.debug(f"Successfully parsed {len(parsed_tasks)} tasks")
                return parsed_tasks
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response was: {response}")
                return []
        else:
            logger.error("No response received from AI")
        return []
    
    def generate_task(self, base_idea, task_type='reward', themes=None):
        """Generate a single task for reward goals"""
        logger.debug(f"Generating {task_type} task with base idea: {base_idea}")
        
        # Create a single task input
        task_input = [{
            "target": "Ian",  # Reward tasks are for Ian to fulfill
            "difficulty": 3,  # Medium difficulty for reward tasks
            "base_idea": base_idea,
            "themes": themes or []
        }]
        
        # Generate using AI
        ai_tasks = self.generate_tasks(f"Generate a {task_type} task", task_input, self.user or "default_user")
        
        if ai_tasks and len(ai_tasks) > 0:
            return ai_tasks[0]  # Return the first (and only) generated task
        else:
            logger.error(f"Failed to generate {task_type} task")
            return None
    
    
    def generate_reward_tasks_batch_with_weights(self, goals_data, count):
        """Generate a batch of reward tasks from reward goals with individual difficulties per goal"""
        logger.debug(f"Generating reward tasks from {len(goals_data)} goals (limited to {count} tasks) with individual difficulties")
        
        # Limit to the number of goals or requested count, whichever is smaller
        tasks_to_generate = min(len(goals_data), count)
        
        # Create task inputs for batch generation (one per goal with individual difficulty)
        task_inputs = []
        for i in range(tasks_to_generate):
            goal = goals_data[i]
            
            # Get the selected difficulty for this specific goal
            selected_difficulty = goal.get('selected_difficulty', 3)
            
            task_input = {
                "target": "Spouse",  # Reward tasks are for Ian to fulfill
                "difficulty": selected_difficulty,  # Individual difficulty per goal
                "base_idea": goal['description'],
                "themes": goal.get('reward_themes', []),
                "ID": goal['id']  # Use 'ID' to match system prompt expectations
            }
            task_inputs.append(task_input)
            logger.debug(f"Task input {i}: ID = {task_input['ID']}, difficulty = {selected_difficulty}")
        
        # Generate tasks using AI in batch
        ai_tasks = self.generate_tasks("Generate reward tasks", task_inputs, self.user or "default_user")
        
        # Debug: Check what came back from AI
        if ai_tasks:
            logger.debug(f"AI returned {len(ai_tasks)} tasks")
            for i, task in enumerate(ai_tasks):
                logger.debug(f"AI task {i}: ID = {task.get('ID')}")
        
        if ai_tasks:
            logger.debug(f"Successfully generated {len(ai_tasks)} reward tasks (one per goal) with individual difficulties")
            return ai_tasks
        else:
            logger.error("Failed to generate reward tasks batch with weights")
            return []
        
    def get_response(self, prompt):
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
                purpose="task_generation",
                model=self.model,
                tokens_used=tokens_used,
                success=True,
                summary=f"Generated tasks using {tokens_used} tokens"
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.ai_call(
                username=self.user or "unknown",
                purpose="task_generation",
                model=self.model,
                tokens_used=0,
                success=False,
                summary=f"Failed: {str(e)}"
            )
            logger.error(f"Error getting response: {e}")
            return None
    
    def get_goals_for_category(self, username, category):
        """Fetch goals for a specific category from Firestore"""
        try:
            # Query goals for this user and category
            goals_query = self.db.collection('goals').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('category', '==', category)
                ])
            )
            goals_docs = goals_query.stream()
            
            goals = []
            for doc in goals_docs:
                goal_data = doc.to_dict()
                goal_data['id'] = doc.id
                goals.append(goal_data)
            
            return goals
        except Exception as e:
            logger.error(f"Error fetching goals for {username} in {category}: {e}")
            return []
    
    def get_active_goals_for_category(self, username, category):
        """Get only active goals for a user and category with database filter"""
        try:
            # Query only active goals for this user and category
            goals_query = self.db.collection('goals').where(
                filter=firestore.And([
                    FieldFilter('username', '==', username),
                    FieldFilter('category', '==', category),
                    FieldFilter('status', '==', 'Active')
                ])
            )
            goals_docs = goals_query.stream()
            
            active_goals = []
            for doc in goals_docs:
                goal_data = doc.to_dict()
                goal_data['id'] = doc.id
                active_goals.append(goal_data)
            
            return active_goals
        except Exception as e:
            logger.error(f"Error fetching active goals for {username} in {category}: {e}")
            return []

    def select_base_idea_from_goals(self, username, category):
        """Select a random base idea from goals using priority weighting (3x high, 1x low), with significant chance to return None"""
        active_goals = self.get_active_goals_for_category(username, category)
        
        if not active_goals:
            logger.debug(f"No active goals found for {username} in {category}")
            return None
        
        # Create weighted pool based on priority (only from active goals)
        weighted_goals = []
        for goal in active_goals:
            if goal.get('priority') == 'High':
                # Add 3 times for high priority
                weighted_goals.extend([goal] * 3)
            elif goal.get('priority') == 'Low':
                # Add 1 time for low priority
                weighted_goals.append(goal)
            else:  # Medium priority
                # Add 2 times for medium priority (between high and low)
                weighted_goals.extend([goal] * 2)
        
        # Add None options to give significant chance of returning None
        # Assuming 10 medium goals = 20 points, we want at least 20 weighted goals
        # Add None options to reach at least 20 total, with significant None chance
        none_count = max(20 - len(weighted_goals), len(weighted_goals) // 2)  # At least half as many None options as goals
        weighted_goals.extend([None] * none_count)
        
        # Select random goal (or None) from weighted pool
        selected_item = random.choice(weighted_goals)
        
        if selected_item is None:
            logger.debug(f"No base idea selected for {username} {category} (returning None)")
            return None
        else:
            base_idea = selected_item.get('description', '')
            logger.debug(f"Selected base idea for {username} {category}: '{base_idea}' (priority: {selected_item.get('priority')}, status: {selected_item.get('status')})")
            return base_idea
    
    def generate_tasks_for_category(self, username, category, count=None, upload_to_firestore=True):
        """Generate tasks for a specific category using AI - main entry point"""
        if count is None:
            return []
            
        # Set user for this generation
        self.user = username
        
        # Create task configurations for the specified category
        tasks_input = []
        for i in range(count):
            # Weighted difficulty selection (heavily weighted toward 2-6)
            difficulties = list(difficulty_weights.keys())
            weights = list(difficulty_weights.values())
            difficulty = random.choices(difficulties, weights=weights, k=1)[0]
            
            # Get base idea from goals using priority weighting
            base_idea = self.select_base_idea_from_goals(username, category)
            
            tasks_input.append({
                "target": category,  # Use the specified category
                "difficulty": difficulty,
                "base_idea": base_idea
            })
        
        # Generate tasks using AI
        ai_tasks = self.generate_tasks(f"Focus on {category} tasks", tasks_input, username)
        
        # Convert AI tasks to Firestore format and store them (if requested)
        generated_tasks = []
        for ai_task in ai_tasks:
            try:
                task_data = {
                    'username': username,
                    'description': ai_task['description'],
                    'category': ai_task['target'],  # Map target to category
                    'difficulty': ai_task['difficulty'],
                    'duration': ai_task['duration'],
                    'completed': False,
                    'saved': False,
                    'presented_at': None,  # Standardized to null for unpresented tasks
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }
                
                if upload_to_firestore and self.db is not None:
                    doc_ref = self.db.collection('tasks').add(task_data)
                    task_data['id'] = doc_ref[1].id
                    task_data['created_at'] = datetime.now()  # For immediate use
                    task_data['updated_at'] = datetime.now()  # For immediate use
                    logger.debug(f"Generated {category} task for {username}: {ai_task['description']}")
                else:
                    # Simulation mode - just add a placeholder ID
                    task_data['id'] = f"sim_{i}_{datetime.now().timestamp()}"
                    task_data['created_at'] = datetime.now()
                    task_data['updated_at'] = datetime.now()
                    logger.debug(f"Generated {category} task for {username} (simulation): {ai_task['description']}")
                
                generated_tasks.append(task_data)
                
            except Exception as e:
                logger.error(f"Error generating {category} task for {username}: {e}")
        
        return generated_tasks
    