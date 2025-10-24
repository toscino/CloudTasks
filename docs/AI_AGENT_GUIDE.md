# AI Agent Development Guide

This guide provides quick reference for AI agents working on the CloudTasks frontend. It covers common development tasks, patterns, and best practices.

## Before You Start

1. ✅ Read `docs/ARCHITECTURE.md` for overall structure
2. ✅ Review `docs/FRONTEND_COMPONENTS.md` for component patterns
3. ✅ Check `docs/API_CONTRACTS.md` for API endpoints
4. ✅ Look at `goals.html` as the cleanest example
5. ✅ Understand the backend in `app.py` and `src/services/`

## File Locations

### Frontend Files
- **Templates**: `templates/*.html`
- **Shared utilities**: `static/js/utils.js`
- **Base template**: `templates/base.html`

### Backend Files
- **Routes**: `app.py`
- **Business logic**: `src/services/*.py`
- **Models**: `src/models/*.py`
- **Core logic**: `src/core/*.py`

### Documentation
- **Architecture**: `docs/ARCHITECTURE.md`
- **Components**: `docs/FRONTEND_COMPONENTS.md`
- **API**: `docs/API_CONTRACTS.md`

## Common Development Tasks

### Adding a New Page

**Step 1**: Create template file
```bash
# Create new template in templates/your_page.html
```

**Step 2**: Template structure
```html
{% extends "base.html" %}

{% block title %}CloudTasks - Your Page{% endblock %}

{% block styles %}
    /* Page-specific styles here */
{% endblock %}

{% block content %}
    <div class="your-container">
        <h2>Your Page Title</h2>
        <!-- Your content -->
    </div>
{% endblock %}

{% block scripts %}
<script type="module">
    import { waitForAuth, apiCall, showError } from '/static/js/utils.js';
    
    let yourData = [];
    
    document.addEventListener('DOMContentLoaded', async function() {
        await waitForAuth();
        await loadData();
        renderInterface();
    });
    
    async function loadData() {
        try {
            const data = await apiCall('/api/your-endpoint');
            if (data.status === 'success') {
                yourData = data.items;
            } else {
                showError('#error-message', data.message);
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
    
    function renderInterface() {
        // Render your UI
    }
</script>
{% endblock %}
```

**Step 3**: Add route in `app.py`
```python
@app.route('/your-page')
def your_page():
    return render_template('your_page.html')
```

**Step 4**: Add navigation link in `base.html`
```html
<a href="/your-page" class="nav-menu-item">Your Page</a>
```

### Adding an API Endpoint

**Step 1**: Add route in `app.py`
```python
@app.route('/api/your-endpoint', methods=['GET'])
def get_your_data():
    username = get_user_info()
    result = your_service.get_data(username)
    
    if result['status'] == 'error':
        return jsonify(result), 500
    return jsonify(result)
```

**Step 2**: Return standard format
```python
return jsonify({
    'status': 'success',
    'items': items
})
```

**Step 3**: Document in `docs/API_CONTRACTS.md`

### Adding a Form

**Pattern**: Use standard form structure
```html
<div class="add-form">
    <div class="form-group">
        <label for="field-name">Label</label>
        <input type="text" id="field-name" placeholder="...">
    </div>
    
    <div class="form-row">
        <button class="btn" onclick="submitForm()">Submit</button>
        <button class="btn btn-secondary" onclick="cancelEdit()" style="display: none;">Cancel</button>
    </div>
</div>
```

**Validation**: Backend handles validation
```javascript
async function submitForm() {
    const fieldValue = document.getElementById('field-name').value;
    
    if (!fieldValue) {
        alert('Field is required');
        return;
    }
    
    const data = await apiCall('/api/endpoint', {
        method: 'POST',
        body: JSON.stringify({ field: fieldValue })
    });
    
    if (data.status === 'success') {
        await loadData();
        renderInterface();
    }
}
```

### Adding a List Display

**Pattern**: Use standard list structure
```html
<ul class="your-list" id="list-container">
    <li class="loading-state">Loading...</li>
</ul>
```

**JavaScript**: Use renderList helper
```javascript
import { renderList } from '/static/js/utils.js';

function renderList() {
    const container = document.getElementById('list-container');
    
    if (items.length === 0) {
        container.innerHTML = '<li class="empty-state">No items</li>';
        return;
    }
    
    container.innerHTML = '';
    items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'item-class';
        li.innerHTML = `
            <div class="item-content">
                <div class="item-text">${item.description}</div>
                <div class="item-actions">
                    <button class="btn btn-sm btn-secondary" onclick="editItem('${item.id}')">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteItem('${item.id}')">Delete</button>
                </div>
            </div>
        `;
        container.appendChild(li);
    });
}
```

## Code Patterns

### Authentication Pattern

**Every page**:
```javascript
import { waitForAuth } from '/static/js/utils.js';

document.addEventListener('DOMContentLoaded', async function() {
    await waitForAuth();  // Wait for auth
    await loadData();     // Load data
    renderInterface();    // Render UI
});
```

### API Call Pattern

**Standard pattern**:
```javascript
import { apiCall, showError } from '/static/js/utils.js';

async function loadData() {
    try {
        const data = await apiCall('/api/endpoint');
        
        if (data.status === 'success') {
            items = data.items;
            renderInterface();
        } else {
            showError('#error-message', data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('#error-message', 'Failed to load data');
    }
}
```

### Edit/Update Pattern

**Common pattern**:
```javascript
let editingId = null;

function editItem(id) {
    editingId = id;
    const item = items.find(i => i.id === id);
    
    // Pre-fill form
    document.getElementById('field-name').value = item.name;
    
    // Change button
    const btn = document.getElementById('submit-btn');
    btn.textContent = 'Update';
    btn.onclick = updateItem;
    
    // Show cancel button
    document.getElementById('cancel-btn').style.display = 'inline-block';
    
    scrollToTop();
}

async function updateItem() {
    const data = await apiCall(`/api/endpoint/${editingId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: document.getElementById('field-name').value })
    });
    
    if (data.status === 'success') {
        editingId = null;
        resetForm();
        await loadData();
        renderInterface();
    }
}
```

### Delete Pattern

**Standard pattern**:
```javascript
async function deleteItem(id) {
    if (!confirm('Are you sure?')) return;
    
    const data = await apiCall(`/api/endpoint/${id}`, {
        method: 'DELETE'
    });
    
    if (data.status === 'success') {
        await loadData();
        renderInterface();
    }
}
```

## Utility Functions

### From `utils.js`

Available functions:
- `waitForAuth()` - Wait for authentication
- `apiCall(url, options)` - Make API call
- `showError(container, message)` - Show error
- `showSuccess(container, message)` - Show success
- `showLoading(element)` - Show loading state
- `hideLoading(element)` - Hide loading state
- `renderList(container, items, renderItem, emptyMessage)` - Render list
- `resetForm(formContainer)` - Reset form fields
- `getCurrentUsername()` - Get username
- `isAuthenticated()` - Check auth status
- `scrollToTop()` - Scroll to top

### Usage Example

```javascript
import { 
    waitForAuth, 
    apiCall, 
    showError,
    resetForm,
    getCurrentUsername,
    scrollToTop 
} from '/static/js/utils.js';
```

### Form Reset Pattern

After successful form submission, reset the form:

```javascript
async function submitForm() {
    const data = await apiCall('/api/endpoint', {
        method: 'POST',
        body: JSON.stringify(formData)
    });
    
    if (data.status === 'success') {
        resetForm('#add-form');  // Clear form fields
        showSuccess('#success-message', 'Form submitted successfully!');
        await loadData();  // Reload data
        renderInterface();  // Refresh UI
    }
}
```

## Styling Guidelines

### Use Existing Classes

**Buttons**:
- `.btn` - Primary button
- `.btn-secondary` - Secondary button
- `.btn-danger` - Delete button
- `.btn-sm` - Small button

**Forms**:
- `.form-group` - Form field container
- `.form-row` - Horizontal form layout

**States**:
- `.empty-state` - Empty state message
- `.loading-state` - Loading message
- `.error-message` - Error message
- `.success-message` - Success message

### Add Page-Specific Styles

```html
{% block styles %}
    /* Page-specific styles */
    .your-custom-class {
        /* styles */
    }
{% endblock %}
```

## Error Handling Best Practices

### When to Use Each Error Method

#### 1. Use `alert()` for Critical Validation Errors
**Use when**: User must acknowledge before proceeding with form submission

```javascript
// Example: Required field validation
if (!taskDescription) {
    alert('Task description is required');
    return;  // Stop execution
}
```

**Characteristics**:
- Blocking dialog that halts user interaction
- User must click OK to dismiss
- Use for validation errors that prevent form submission

#### 2. Use `showError()` for Non-Blocking Errors
**Use when**: Displaying API errors or failures that don't prevent user interaction

```javascript
// Example: Failed to load data
async function loadData() {
    try {
        const data = await apiCall('/api/tasks');
        if (data.status === 'success') {
            tasks = data.tasks;
        } else {
            showError('#error-message', data.message);
        }
    } catch (error) {
        showError('#error-message', 'Failed to load tasks');
    }
}
```

**Characteristics**:
- Inline error display in designated container
- Non-blocking - user can continue interacting
- Auto-clears when new actions succeed

#### 3. Use `console.error()` for Developer Debugging
**Use when**: Logging errors for debugging purposes

```javascript
// Example: Log detailed error for debugging
catch (error) {
    console.error('Failed to update goal:', error);
    console.error('Goal ID:', goalId);
    console.error('Request data:', requestData);
    showError('#error-message', 'Failed to update goal');
}
```

**Characteristics**:
- Visible only in browser console
- Provides detailed debugging information
- Often paired with user-facing error display

### Standard Error Handling Pattern

```javascript
async function performAction() {
    try {
        const data = await apiCall('/api/endpoint', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        // Check API-level status
        if (data.status === 'success') {
            // Success handling
            showSuccess('#success-message', 'Action completed successfully!');
            await loadData();
            renderInterface();
        } else {
            // API returned error status
            showError('#error-message', data.message);
        }
    } catch (error) {
        // Network error or other exception
        console.error('Action failed:', error);
        showError('#error-message', 'Failed to perform action. Please try again.');
    }
}
```

### HTTP Status Codes

**Backend sets proper HTTP status codes** (400, 403, 404, 500) but frontend primarily checks `data.status` field.

**`apiCall()` adds HTTP status to response**:
```javascript
const data = await apiCall('/api/endpoint');
console.log('HTTP Status:', data._httpStatus);  // Available for debugging
```

**Common HTTP status codes**:
- `200` - Success
- `400` - Bad Request (validation error)
- `403` - Forbidden (unauthorized access)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

## Validation Strategy

### Client-Side Validation (UX)
**Purpose**: Provide immediate feedback to improve user experience

**Examples**:
```javascript
// Quick validation before API call
if (!description) {
    alert('Description is required');
    return;
}

if (points < -100 || points > 100) {
    alert('Points must be between -100 and 100');
    return;
}
```

**Characteristics**:
- Instant feedback without waiting for server
- Prevents unnecessary API calls
- Can be bypassed, so backend validation is still required

### Server-Side Validation (Security)
**Purpose**: Enforce data integrity and security

**Backend always validates**:
```python
# Example from daily_task_service.py
if not data.get('description'):
    return {'status': 'error', 'message': 'Task description is required'}

if data.get('points') < -100 or data.get('points') > 100:
    return {'status': 'error', 'message': 'Points must be between -100 and 100'}
```

**Characteristics**:
- Source of truth for validation rules
- Cannot be bypassed
- Provides security against malicious requests

**Best Practice**: Keep validation rules synchronized between client and server

## API Debugging Guide

### Common API Issues and Solutions

#### Issue: API returns error status
**Symptoms**: `data.status === 'error'` in response

**Debugging steps**:
1. Check the error message: `console.log(data.message)`
2. Verify request data: `console.log(requestData)`
3. Check HTTP status: `console.log(data._httpStatus)`
4. Review backend logs for server-side errors

**Example**:
```javascript
const data = await apiCall('/api/goals', {
    method: 'POST',
    body: JSON.stringify({ description: 'My goal' })
});

if (data.status === 'error') {
    console.error('Error message:', data.message);
    console.error('HTTP Status:', data._httpStatus);
    console.error('Request data:', { description: 'My goal' });
    showError('#error-message', data.message);
}
```

#### Issue: Network error (catch block)
**Symptoms**: Exception thrown, fetch fails

**Debugging steps**:
1. Check browser console for CORS errors
2. Verify backend is running
3. Check network tab in DevTools
4. Verify endpoint URL is correct

**Example**:
```javascript
try {
    const data = await apiCall('/api/endpoint');
} catch (error) {
    console.error('Network error:', error);
    console.error('Endpoint:', '/api/endpoint');
    showError('#error-message', 'Network error. Please check your connection.');
}
```

#### Issue: Unexpected response format
**Symptoms**: `data.status` is undefined or unexpected value

**Debugging steps**:
1. Log full response: `console.log('Full response:', data)`
2. Check API contract in `docs/API_CONTRACTS.md`
3. Verify backend endpoint implementation

**Example**:
```javascript
const data = await apiCall('/api/endpoint');
console.log('Full response:', JSON.stringify(data, null, 2));
console.log('Response keys:', Object.keys(data));
```

### Debugging Checklist

When debugging API issues:

- [ ] Check browser console for errors
- [ ] Verify endpoint URL is correct
- [ ] Check request method (GET, POST, PUT, DELETE)
- [ ] Verify request body is valid JSON
- [ ] Check authentication state
- [ ] Review backend logs for server errors
- [ ] Check HTTP status code in response
- [ ] Verify API contract matches actual response

## Best Practices

### DO ✅

1. **Import utilities** from `utils.js`
2. **Use standard patterns** from existing pages
3. **Wait for auth** before loading data
4. **Handle errors** gracefully with appropriate error display method
5. **Follow naming conventions** (camelCase for JS, kebab-case for CSS)
6. **Document deviations** if you break patterns
7. **Test on mobile** (responsive design)
8. **Use client-side validation** for UX, always keep server-side validation
9. **Log errors** with console.error for debugging
10. **Check HTTP status codes** when debugging API issues

### DON'T ❌

1. **Don't duplicate** authentication waiting code
2. **Don't add** business logic to frontend
3. **Don't skip** error handling
4. **Don't hardcode** usernames or IDs
5. **Don't bypass** API layer
6. **Don't forget** mobile responsiveness
7. **Don't use** inline event handlers (use onclick in HTML or addEventListener)

## Debugging Tips

### Check Authentication

```javascript
console.log('Current user:', window.authState.currentUsername);
console.log('Authenticated:', window.authState.isAuthenticated);
```

### Debug API Calls

```javascript
console.log('API response:', data);
```

### Check Page Load

```javascript
console.log('Page loaded:', window.location.href);
```

## Common Issues

### Issue: Authentication not working

**Solution**: Make sure you're calling `await waitForAuth()` before loading data

### Issue: API call fails

**Symptoms**: Network error or unexpected response

**Check**: 
1. Endpoint URL is correct
2. Request method is correct (GET, POST, PUT, DELETE)
3. Request body is valid JSON
4. Backend route exists in `app.py`
5. Check browser console for CORS errors
6. Verify backend is running

**Debugging**:
```javascript
try {
    const data = await apiCall('/api/endpoint');
    console.log('Response:', data);
} catch (error) {
    console.error('API call failed:', error);
    console.error('Error details:', error.message);
}
```

### Issue: API returns error status

**Symptoms**: `data.status === 'error'`

**Check**:
1. Review error message: `console.log(data.message)`
2. Check HTTP status: `console.log(data._httpStatus)`
3. Verify request data matches API contract
4. Check backend logs for validation errors

**Common causes**:
- Validation errors (missing fields, invalid values)
- Authorization errors (403 Forbidden)
- Resource not found (404)
- Server errors (500)

### Issue: Error display not showing

**Symptoms**: Error message not visible to user

**Check**:
1. Error container exists in HTML: `<div id="error-message"></div>`
2. Using correct selector: `showError('#error-message', 'Error')`
3. Container has appropriate CSS styles
4. Not being cleared by other code

**Solution**:
```javascript
// Ensure container exists
const errorDiv = document.querySelector('#error-message');
if (!errorDiv) {
    console.error('Error container not found');
}

// Show error
showError('#error-message', 'Error message');
```

### Issue: Styles not applying

**Check**:
1. CSS classes are correct
2. Styles are in `{% block styles %}`
3. No CSS conflicts
4. Check browser DevTools for overridden styles

### Issue: List not rendering

**Check**:
1. Container element exists
2. Items array is populated
3. Render function is called
4. Check console for JavaScript errors

## Testing Checklist

After making changes:

- [ ] Page loads without errors
- [ ] Authentication works
- [ ] API calls succeed
- [ ] Forms validate correctly
- [ ] Lists render properly
- [ ] Mobile responsive
- [ ] No console errors
- [ ] Navigation works

## Quick Reference

### Template Structure
```html
{% extends "base.html" %}
{% block title %}Page Title{% endblock %}
{% block styles %}{% endblock %}
{% block content %}{% endblock %}
{% block scripts %}{% endblock %}
```

### JavaScript Initialization
```javascript
import { waitForAuth } from '/static/js/utils.js';

document.addEventListener('DOMContentLoaded', async function() {
    await waitForAuth();
    await loadData();
    renderInterface();
});
```

### API Call
```javascript
const data = await apiCall('/api/endpoint');
if (data.status === 'success') { /* handle */ }
```

### Form Submission
```javascript
const data = await apiCall('/api/endpoint', {
    method: 'POST',
    body: JSON.stringify(formData)
});
```

### Error Handling
```javascript
// Complete error handling pattern
try {
    const data = await apiCall('/api/endpoint');
    
    if (data.status === 'success') {
        // Handle success
        showSuccess('#success-message', 'Action completed!');
    } else {
        // Handle API error
        showError('#error-message', data.message);
    }
} catch (error) {
    // Handle network error
    console.error('Action failed:', error);
    showError('#error-message', 'Failed to perform action');
}
```

### Validation
```javascript
// Client-side validation (UX)
if (!description) {
    alert('Description is required');
    return;
}

// Server always validates - trust backend validation
```

## Getting Help

- **Architecture questions**: See `docs/ARCHITECTURE.md`
- **Component questions**: See `docs/FRONTEND_COMPONENTS.md`
- **API questions**: See `docs/API_CONTRACTS.md`
- **Example code**: Look at `goals.html` (cleanest example)

## Summary

The CloudTasks frontend follows these principles:

1. **Minimal Logic** - Frontend doesn't contain business rules
2. **Clear Patterns** - Follow existing patterns
3. **Shared Utilities** - Use `utils.js` functions
4. **Standard API** - All endpoints return standard format
5. **Mobile First** - Responsive by default

When in doubt, look at `goals.html` as the reference implementation.

