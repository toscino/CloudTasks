# CloudTasks - Task Management App

A comprehensive task management application built for Google App Engine with Firestore integration. Features a complete rewards system with spouse collaboration, AI-generated tasks, and real-time synchronization.

## Setup

1. **Install dependencies:**
   ```bash
   install.bat
   # or
   pip install -r requirements.txt
   ```

2. **Set up Google Cloud Project:**
   - Create a new project in [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Firestore API
   - Create a service account and download the key file
   - Update `GOOGLE_CLOUD_PROJECT` in `.env` file

3. **Local Development:**
   ```bash
   # Run locally
   run.bat
   # or
   python Main.py
   ```

4. **Deploy to App Engine:**
   ```bash
   # Deploy to development
   gcloud app deploy config/development.yaml
   
   # Deploy to production
   gcloud app deploy config/production.yaml
   ```

## Features

- **Task Management**: Create, complete, and save tasks with AI-generated content and swipe-to-complete interface
- **Rewards System**: Complete rewards system with spouse collaboration
  - **Rewards to Claim**: Earn rewards by completing difficult tasks
  - **Rewards Owed**: Complete challenges to fulfill rewards your spouse selected
  - **Challenges**: AI-generated tasks to complete reward goals
- **User Separation**: Multi-user support with session-based authentication
- **Firestore Integration**: Real-time task storage with Google Cloud Firestore
- **AI Integration**: OpenAI-powered task and reward generation
- **Background Processing**: Pregenerated tasks and rewards for instant loading
- **Mobile-Friendly**: Touch and swipe gestures for task completion
- **Weekly Tracking**: Difficulty points tracking with Friday-to-Friday weeks
- **Spouse Comparison**: Compare pending rewards with your spouse

## API Endpoints

### Task Management
- `GET /` - Main task display page (tasks.html) - includes challenges
- `GET /test` - Testing interface (test.html)
- `GET /api/tasks` - Get active tasks for current user (max 4)
- `POST /api/tasks` - Create new task
- `PUT /api/tasks/<task_id>/complete` - Mark task as completed
- `PUT /api/tasks/<task_id>/save` - Toggle save status

### Rewards System
- `GET /rewards` - Rewards to claim page (reward_claim.html)
- `GET /rewards-owed` - Rewards owed page (rewards_owed.html)
- `GET /api/rewards` - Get rewards to claim (earned rewards)
- `GET /api/rewards-owed` - Get rewards owed (spouse-selected rewards)
- `GET /api/challenges` - Get challenges (tasks to complete rewards owed)
- `POST /api/challenges/<task_id>/complete` - Complete a challenge
- `POST /api/rewards-owed/<goal_id>/complete` - Complete a reward owed

### Earned Rewards
- `GET /api/earned-rewards` - Get pending earned rewards
- `POST /api/earned-rewards/<reward_id>/generate-options` - Generate reward options
- `POST /api/earned-rewards/<reward_id>/select-option` - Select reward option

### Statistics & Comparison
- `GET /api/weekly-points` - Get weekly difficulty points (Friday 5pm to Friday 5pm)
- `GET /api/reward-comparison` - Compare pending rewards with spouse

### System Testing
- `GET /api/test` - Test Firestore connection
- `GET /api/user` - Get current user information

## Firestore Schema

### Tasks Collection
Each task document contains:
- `username` (string) - User identifier for separation
- `description` (string) - Task description text
- `category` (string) - Task category (Work, Kids, Spouse, House, Self, or General)
- `difficulty` (number) - Task difficulty (1-10)
- `duration` (number) - Estimated duration in minutes
- `completed` (boolean) - Task completion status
- `saved` (boolean) - Save/bookmark status
- `completed_at` (timestamp) - Completion timestamp
- `created_at` (timestamp) - Creation timestamp
- `updated_at` (timestamp) - Last modification timestamp

### Reward Goals Collection
Each reward goal document contains:
- `username` (string) - User identifier
- `description` (string) - Reward description
- `status` (string) - 'pending' or 'completed'
- `earned_by` (string) - Username who earned the reward
- `reward_themes` (array) - Reward themes/tags
- `created_at` (timestamp) - Creation timestamp
- `completed_at` (timestamp) - Completion timestamp

### Reward Tasks Collection (Challenges)
Each reward task document contains:
- `username` (string) - User identifier
- `reward_goal_id` (string) - Associated reward goal ID
- `description` (string) - Challenge description
- `difficulty` (number) - Challenge difficulty
- `duration` (number) - Estimated duration in minutes
- `status` (string) - 'pending' or 'completed'
- `expires_at` (timestamp) - Expiration timestamp
- `created_at` (timestamp) - Creation timestamp

### Earned Rewards Collection
Each earned reward document contains:
- `username` (string) - User identifier
- `task_difficulty` (number) - Difficulty of task that earned the reward
- `status` (string) - 'pending' or 'completed'
- `earned_at` (timestamp) - When reward was earned
- `selected_option` (object) - Selected reward option (if completed)

### Task Categories
The application supports the following task categories:
- **Work** - Professional and work-related tasks
- **Kids** - Tasks related to children and family care
- **Spouse** - Relationship and partner-focused tasks
- **House** - Home maintenance and household tasks
- **Self** - Self-care and personal wellness tasks
- **General** - Uncategorized tasks

## Authentication

The app uses **session-based** authentication with **three authenticated users** plus a **demo account**:

### **Authentication System**
- **No secret key** = `test_user` (demo account with 🧪 icon)
- **Valid secret key** = Authenticated user (`Ian`, `Karleigh`, or `user3` with 🔑 icon)
- **Unknown secret key** = Falls back to `test_user` (demo account)
- **All API endpoints work** regardless of authentication status
- **User separation** maintained in Firestore by username
- **User isolation** enforced - users can only modify their own tasks/rewards

### Environment Variables
Set these in your `.env` file or deployment environment:

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-project-id
FLASK_SECRET_KEY=your-flask-secret-key

# User-specific secret keys
USER1_SECRET_KEY=user1-demo-key-abc123
USER2_SECRET_KEY=user2-demo-key-def456
USER3_SECRET_KEY=user3-demo-key-ghi789
```

### Browser Access
**Demo Account (No Key Required):**
- `http://127.0.0.1:8080/` - Works immediately as `test_user`

**Authenticated Users:**
- `http://127.0.0.1:8080/?secret_key=user1-demo-key-abc123` - Logs in as `Ian`
- `http://127.0.0.1:8080/?secret_key=user2-demo-key-def456` - Logs in as `Karleigh`
- `http://127.0.0.1:8080/?secret_key=user3-demo-key-ghi789` - Logs in as `user3`

### API Authentication
The system uses **session-based authentication**:
1. **Initial login**: Pass `secret_key` via URL parameter or POST to `/api/login`
2. **Session persistence**: Authentication persists across page navigation
3. **Server-side username mapping**: Secret keys map to usernames on the server
4. **No client-side username handling**: Prevents username spoofing

## Development Status

### ✅ Completed
- **Complete Task Management System**
  - AI-generated tasks with difficulty scaling
  - Swipe-to-complete interface
  - Task categories and time-based weighting
  - Background task pregeneration
- **Complete Rewards System**
  - Rewards to claim (earned rewards)
  - Rewards owed (spouse-selected rewards)
  - Challenges (tasks to complete rewards)
  - AI-generated reward options
- **Session-based Authentication System**
  - Three authenticated users (`Ian`, `Karleigh`, `user3`) + demo account (`test_user`)
  - Server-side username mapping
  - User isolation and security
- **Background Processing**
  - Centralized `ensure_minimums()` function
  - Parallel thread execution
  - Pregenerated tasks, rewards, and challenges
- **Statistics & Tracking**
  - Weekly difficulty points (Friday 5pm to Friday 5pm)
  - Spouse reward comparison
  - Real-time updates
- **Firestore Integration**
  - Real-time synchronization
  - Optimized queries
  - User data isolation

### 🚧 Current Features
- **AI Integration**: OpenAI-powered task and reward generation
- **Mobile-Friendly**: Touch and swipe gestures
- **Real-time Updates**: Live statistics and comparisons
- **Performance Optimized**: Background processing for instant loading

### 📋 Future Enhancements
- Advanced reward themes and categories
- Task scheduling and recurring tasks
- Enhanced analytics and reporting
- Mobile app development

## Performance Optimization Notes

### Current Implementation (Test Phase)
- **Client-side filtering**: Queries use single-field ordering, filter incomplete tasks in Python
- **Why**: Allows flexible testing of different ordering approaches without index management
- **Performance**: Suitable for small test datasets (< 100 tasks per user)

### Future Migration (Production)
When ready for production optimization, create  Firestore composite indexes:
Replace client-side filtering with direct Firestore queries:


**Migration Benefits**: 10-40x faster queries, reduced network traffic, better scalability

## Testing

```bash
# Run all tests
test.bat
# or
python -m pytest tests/ -v

# Run only unit tests
python -m pytest tests/test_app.py -v

# Run only integration tests
python -m pytest tests/test_firestore.py -v
```

## Project Structure

```
├── App.py                # Main Flask application with all routes
├── Main.py               # Entry point
├── src/core/TaskMaster.py         # Task management and generation
├── src/core/TaskGenerator.py      # AI task generation
├── src/core/RewardGenerator.py    # Reward generation
├── src/core/RewardMaster.py       # Reward management
├── src/core/ChallengeMaster.py   # Challenge management
├── app.yaml              # App Engine development config
├── production.yaml       # App Engine production config
├── tests/                # Test files
│   ├── __init__.py
│   ├── test_app.py       # Unit tests
│   └── test_firestore.py # Integration tests
├── templates/            # HTML templates
│   ├── base.html         # Base template with navigation
│   ├── tasks.html        # Main task display (includes challenges)
│   ├── reward_claim.html # Rewards to claim page
│   ├── rewards_owed.html # Rewards owed page
│   ├── goals.html        # Goals management
│   ├── test.html         # Testing interface
│   └── about.html        # About page
├── requirements.txt      # Python dependencies
├── run.bat              # Run the application
├── test.bat             # Run tests
├── install.bat          # Install dependencies
├── .env                 # Environment variables
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## Available Commands

- `install.bat` - Install dependencies
- `test.bat` - Run all tests
- `run.bat` - Run locally
- `gcloud app deploy app.yaml` - Deploy to development
- `gcloud app deploy production.yaml` - Deploy to production

## Naming Convention

The application uses a clear naming convention to distinguish between different types of rewards:

- **Tasks** - Regular tasks (Work, Kids, Spouse, House, Self categories)
- **Rewards** - Rewards you need to claim (earned rewards waiting to be claimed)
- **Rewards Owed** - Rewards you need to do (rewards your spouse selected for you to fulfill)
- **Challenges** - Tasks to complete reward goals (displayed under Tasks page)

## User Flow

1. **Complete Tasks** → Earn rewards based on difficulty
2. **Claim Rewards** → Select from AI-generated reward options
3. **Spouse Selects Rewards** → Creates "Rewards Owed" for you
4. **Complete Challenges** → Fulfill the rewards your spouse selected
5. **Track Progress** → View weekly points and spouse comparison
