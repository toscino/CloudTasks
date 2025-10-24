# Frontend Architecture

## Overview

The CloudTasks frontend uses **vanilla JavaScript** with **Jinja2 templates**. The architecture emphasizes minimal frontend logic, with most business logic and data processing handled by the Python backend. The frontend focuses on UI rendering, user interactions, and API communication.

## Technology Stack

- **Templates**: Jinja2 (server-side rendering)
- **JavaScript**: Vanilla ES6 (no frameworks)
- **Styling**: Inline CSS in templates
- **Shared Utilities**: Module-based JavaScript (`static/js/utils.js`)

## File Organization

```
templates/
  base.html              # Base template with navigation and global auth
  tasks.html             # Main task display page
  daily_tasks.html       # Daily tasks management
  goals.html             # Goals management
  morning_cards.html     # Morning cards selection
  morning_cards_manage.html  # Morning cards management
  test.html              # Testing interface

static/
  js/
    utils.js             # Shared JavaScript utilities

docs/
  ARCHITECTURE.md        # This file
  FRONTEND_COMPONENTS.md # Component documentation
  API_CONTRACTS.md       # API documentation
  AI_AGENT_GUIDE.md      # Quick reference for AI agents
```

## Architecture Principles

### 1. Minimal Frontend Logic
- Frontend does **not** contain business rules
- No data validation logic in frontend
- No complex state management
- Python backend handles all data processing

### 2. Template Inheritance
- All pages extend `base.html`
- Shared styles and navigation in base template
- Page-specific content in `{% block content %}`
- Page-specific scripts in `{% block scripts %}`

### 3. State Management
- **No framework** - direct DOM manipulation
- State stored in module-level JavaScript variables
- UI updates via re-rendering functions
- Global auth state in `window.authState`

### 4. API Communication
- All endpoints return standard JSON format
- Session-based authentication (no tokens)
- Backend handles all validation and error handling

## Common Patterns

### Authentication Flow
1. Page loads
2. Wait for `window.authState` to initialize (via `waitForAuth()`)
3. Load user-specific data from API
4. Render interface with fetched data

### Page Initialization
```javascript
document.addEventListener('DOMContentLoaded', async function() {
    await waitForAuth();  // Wait for authentication
    await loadData();     // Fetch data from API
    renderInterface();   // Render UI
});
```

### API Communication
```javascript
const data = await apiCall('/api/endpoint');
if (data.status === 'success') {
    // Handle success
} else {
    // Handle error
    showError(errorContainer, data.message);
}
```

### List Rendering
```javascript
renderList(container, items, (item) => {
    const li = document.createElement('li');
    li.innerHTML = `...`;
    return li;
}, 'No items available');
```

## Key Global Variables

### `window.authState`
Global authentication state object, initialized in `base.html`:
```javascript
window.authState = {
    currentUsername: null,      // Current logged-in user
    isAuthenticated: false,     // Authentication status
    sessionBased: false,        // Session-based auth flag
    initialized: false         // Initialization complete flag
}
```

## Navigation System

The navigation is implemented in `base.html` and includes:
- Hamburger menu (mobile-friendly)
- User status indicator in nav bar
- Morning cards notification indicator
- Navigation overlay

## Shared Utilities

Location: `static/js/utils.js`

Provides common functions:
- `waitForAuth()` - Wait for authentication initialization
- `apiCall(url, options)` - Standardized API calls
- `showError(container, message)` - Display error messages
- `showSuccess(container, message)` - Display success messages
- `renderList(container, items, renderItem, emptyMessage)` - Generic list rendering
- `getCurrentUsername()` - Get current username
- `isAuthenticated()` - Check authentication status

## Page-Specific Patterns

### Goals Page (`goals.html`)
- Cleanest example of list rendering
- Form handling with validation
- Category-based organization
- Toggle between category views

### Daily Tasks Page (`daily_tasks.html`)
- CRUD operations for templates
- Checkbox-based day selection
- Goals management integration
- Real-time calculation updates

### Tasks Page (`tasks.html`)
- Task completion with swipe gestures
- Real-time statistics updates
- Collaboration tracker display
- Progress indicator with goals

### Morning Cards Page (`morning_cards.html`)
- Conditional rendering based on user
- Card selection interface
- Live summary updates
- Lock/unlock functionality

## CSS Organization

### Common Styles (in `base.html`)
- Button styles (`.btn`, `.btn-primary`, `.btn-secondary`, `.btn-danger`)
- Form styles (`.form-group`, `.form-row`, input/textarea/select)
- Card styles (`.card-item`, `.card-content`, `.card-text`)
- State styles (`.empty-state`, `.loading-state`)
- Message styles (`.error-message`, `.success-message`, `.info-banner`)
- Responsive utilities (media queries)

### Page-Specific Styles
Each page can override styles in `{% block styles %}` for page-specific needs.

## Responsive Design

- Mobile-first approach
- Breakpoint at 768px
- Flexbox layouts
- Responsive form rows
- Touch-friendly interactions

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES6+ JavaScript features
- CSS Grid and Flexbox
- No polyfills required

## Future Considerations

### Potential Improvements
1. Extract CSS to separate file (currently inline)
2. Add state management library if complexity grows
3. Consider build process for JavaScript minification
4. Add component library for common UI elements

### When to Add Complexity
- Add framework only if:
  - Page count exceeds 10+ pages
  - Component reuse becomes difficult
  - State management becomes complex
  - Team size grows significantly

## Development Workflow

1. **Add new page**: Create template extending `base.html`
2. **Add API endpoint**: Create route in `app.py`
3. **Use utilities**: Import from `utils.js` for common functions
4. **Follow patterns**: Use existing pages as reference
5. **Test**: Verify authentication flow and API calls

## Best Practices

1. **Keep frontend logic minimal** - Backend handles business rules
2. **Use shared utilities** - Don't duplicate code
3. **Follow consistent patterns** - Use existing pages as examples
4. **Document deviations** - If you must break a pattern, document why
5. **Test authentication flow** - Always verify auth state initialization
6. **Handle errors gracefully** - Use `showError()` for user feedback
7. **Responsive by default** - All UI should work on mobile

