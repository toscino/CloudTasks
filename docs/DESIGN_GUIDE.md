# Design Guide

A comprehensive guide to architecture, code organization, and documentation philosophy. This guide is portable and applicable across projects.

## I. Architecture Philosophy

### Layered Architecture

```
Routes (app.py)
    ↓
Services (src/services/) - Business logic, validation, API contracts
    ↓
Core (src/core/) - Domain logic, orchestration, algorithms
    ↓
Database (Firestore)
```

**Principles:**
- Each layer has single responsibility
- Services handle business logic and API contracts
- Core handles domain logic, orchestration, and AI integration
- Models handle data structures and validation
- Routes are thin - delegate to services

**Dependency Injection:**
- Services receive database client and core classes via constructor
- Core classes receive database client via constructor
- No global state, all dependencies explicit

### Key Patterns

**Service Layer Pattern**
- Each service handles a domain (tasks, goals, rewards, etc.)
- Services coordinate between API requests and core logic
- Services handle validation, error handling, response formatting

**Core Layer Pattern**
- Master classes: Orchestration (TaskMaster, RewardMaster, ChallengeMaster)
  - Responsibilities: Ensure minimums, session management, state coordination
- Generator classes: AI/Creation logic (TaskGenerator, RewardGenerator)
  - Responsibilities: AI integration, generation algorithms

**Single Responsibility**
- One class per file
- Each class has one reason to change
- Keep files focused and cohesive

## II. Project Structure

```
src/
  core/           # Domain logic (orchestration, AI, algorithms)
    *_master.py   # Orchestration classes (TaskMaster, RewardMaster)
    *_generator.py # Generation classes (TaskGenerator, RewardGenerator)
  
  services/        # Business logic, API contracts
    *_service.py   # Service classes (task_service, goal_service)
  
  models/          # Data models
    *.py          # Singular nouns (task.py, goal.py, reward.py)
  
  utils/           # Shared utilities
    logger.py      # Logging system
    config.py      # Configuration
    error_handlers.py # Error handling
    firestore_helpers.py # Database helpers
  
  auth/            # Authentication
    auth_service.py # Auth logic

templates/         # HTML templates (Jinja2)
static/            # Static assets
  js/              # JavaScript modules

docs/              # Permanent reference docs (keep minimal!)
plans/             # Active work plans (delete when complete)
tests/             # Test suite
```

## III. Docstring Style

### Core Principles

1. **Brief one-liners focused on WHAT, not HOW**
   - Help readers understand the code, not write code with it
2. **Action-focused verbs**: Get, Create, Update, Delete, Generate, Calculate, etc.
3. **Drop redundancy**: "for user" only when contrasting multiple users
4. **Keep useful specifics**: "(4 tasks)", "max 10", "(one per goal)"
5. **Note side effects**: "and mark as used", "with locking", "and delete"
6. **Simple getters/setters**: Can skip docstring if trivial

### Format Patterns

```python
# Basic: """Action the noun"""
def get_tasks(username):
    """Get active task session"""
    
# With detail: """Action noun (specific detail)"""
def get_tasks(username):
    """Get active task session (4 tasks)"""
    
# With side effect: """Action noun and side effect"""
def get_available_reward_options(username, earned_reward_id):
    """Get 4 reward options and mark as used"""
    
# Side effects with detail: """Action noun (detail) and side effect"""
def ensure_minimum_tasks(username):
    """Ensure minimum tasks per category with locking"""
```

### Examples

**Good docstrings:**
```python
"""Get active task session (4 tasks)"""
"""Get goals by category"""
"""Complete task and refresh session"""
"""Generate reward task batch with per-goal difficulties"""
"""Select weighted random goal (3x high, 1x low) or None"""
"""Calculate adjustment (+1/0/-1) based on performance"""
```

**Bad docstrings:**
```python
"""Get all goals for current user organized by category"""  # Too wordy
"""Mark a task as completed and refresh the task session"""  # Redundant
"""This function gets the goals for the user"""  # Unnecessary words
"""Retrieves a collection of goal entities associated with the user"""  # Too formal
```

## IV. Documentation Philosophy

### The Problem

Too many status/progress docs become outdated and clutter the docs folder.

### The Solution

**Permanent Documentation** (`/docs/`)
- README.md - Quick start and setup
- DESIGN_GUIDE.md - This file
- ARCHITECTURE.md - System architecture
- API_CONTRACTS.md - API reference
- CONFIG_GUIDE.md - Configuration guide
- FRONTEND_COMPONENTS.md - UI component patterns
- AI_AGENT_GUIDE.md - Developer reference

**Active Work** (`/plans/`)
- Current work plans
- Delete when complete
- Temporary during development

**Not Documentation**
- ❌ Status updates ("COMPLETE", "PROGRESS", "SUMMARY")
- ❌ Completed work summaries
- ❌ Refactoring notes
- ❌ "What changed" logs

### Rules

1. **Six Month Rule**: If a future developer won't need it in 6+ months, don't create a separate doc
2. **Inline > Separate**: Prefer docstrings and code comments over separate documentation
3. **Delete When Done**: `/plans/` files should be deleted when work is complete
4. **Keep It Minimal**: Only document what's essential for understanding the system

### When to Create a Doc

✅ **Create a separate doc for:**
- Architecture decisions affecting multiple systems
- Complex API contracts (API_CONTRACTS.md)
- Setup/deployment procedures (README.md)
- Persistent configuration needs (CONFIG_GUIDE.md)
- Design patterns developers need to follow (DESIGN_GUIDE.md)

❌ **Don't create a separate doc for:**
- "Progress on X feature" (use TODO.md or issues)
- "Refactoring complete" (commit messages are sufficient)
- "Status updates" (temporary information)
- Implementation details (use inline comments)

## V. Naming Conventions

### Files
- Services: `{domain}_service.py` (task_service.py, goal_service.py)
- Core orchestrators: `{domain}_master.py` (task_master.py, reward_master.py)
- Core generators: `{domain}_generator.py` (task_generator.py, reward_generator.py)
- Models: Singular nouns (task.py, goal.py, reward.py)
- Utils: Purpose-based (logger.py, config.py, error_handlers.py)

### Classes
- Service classes: `{Domain}Service` (TaskService, GoalService)
- Core classes: `{Domain}Master` or `{Domain}Generator` (TaskMaster, TaskGenerator)
- Model classes: `{Domain}Model` (TaskModel, GoalModel)

### Functions
- Clear, descriptive names: `get_active_session_tasks`, `ensure_minimum_tasks`
- Action verbs at start: get, create, update, delete, complete, generate
- Avoid abbreviations unless standard (id, config, db)

## VI. Code Organization

### Class Responsibilities

**Master Classes** (`*_master.py`)
- Orchestration and state management
- Ensuring minimums (tasks, rewards, challenges)
- Session management
- Lock acquisition/release

Example: `TaskMaster`
- Ensures minimum tasks per category
- Manages task sessions
- Handles task completion and refresh

**Generator Classes** (`*_generator.py`)
- AI integration
- Generation algorithms
- Content creation logic

Example: `TaskGenerator`
- Generates tasks via AI
- Formats prompts
- Parses AI responses

**Service Classes** (`*_service.py`)
- Business logic
- Request validation
- Error handling
- Response formatting

Example: `TaskService`
- Validates task creation requests
- Calls TaskMaster for domain logic
- Formats responses for API

### File Organization

**One class per file**
- Each class in its own file
- File name matches class name (lowercase with underscores)

**Grouped by responsibility**
- Core: Domain logic grouped by feature
- Services: API logic grouped by domain
- Models: Data structures grouped by type

## VII. Example Code Structure

```python
# task_service.py
class TaskService:
    """Service for task-related operations"""
    
    def __init__(self, db, task_master):
        self.db = db
        self.task_master = task_master
    
    def get_tasks(self, username: str) -> Dict[str, Any]:
        """Get active task session (4 tasks)"""
        # Business logic: validation, calling core, formatting response
        pass
```

```python
# task_master.py
class TaskMaster:
    """Manages task creation and ensures minimum task counts per category"""
    
    def __init__(self, db):
        self.db = db
        self.task_generator = TaskGenerator(db)
    
    def ensure_minimum_tasks(self, username):
        """Ensure minimum tasks per category with locking"""
        # Core logic: orchestration, state management
        pass
```

```python
# task_generator.py
class TaskGenerator:
    """Handles AI-powered task generation logic"""
    
    def __init__(self, db, cheapmode=False):
        self.db = db
        self.client = OpenAI()
    
    def generate_tasks_for_category(self, username, category, count=None):
        """Generate AI tasks for category"""
        # Generation logic: AI integration, prompt formatting
        pass
```

## Summary

This design guide captures proven patterns for building maintainable, scalable applications with clear separation of concerns, concise documentation, and effective code organization.

