# Frontend Components Guide

This document describes the major UI components and patterns used throughout the CloudTasks frontend.

## Navigation Components

### Hamburger Menu (`base.html`)

**Location**: Top navigation bar

**Features**:
- Slide-out menu on mobile
- Overlay background
- Smooth animations
- Keyboard support (Escape to close)

**JavaScript Functions**:
- `toggleNavMenu()` - Toggle menu visibility
- `closeNavMenu()` - Close menu

**HTML Structure**:
```html
<button class="hamburger" onclick="toggleNavMenu()">
    <span class="hamburger-line"></span>
    <span class="hamburger-line"></span>
    <span class="hamburger-line"></span>
</button>
```

### User Status Indicator

**Location**: Navigation bar title

**Displays**: Current username from `window.authState.currentUsername`

**Updates**: Automatically when authentication state changes

### Morning Cards Notification

**Location**: Navigation bar (right side)

**Displays**: 🃏 emoji when Karleigh needs to lock in morning cards

**Behavior**: Animated wiggle to draw attention

**JavaScript**: `checkPendingMorningCards()` checks and updates display

## Form Components

### Standard Form Pattern

**Structure**:
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

### Form Row Layout

**Usage**: Multiple fields side-by-side

**CSS Classes**:
- `.form-row` - Flex container
- `.form-group` - Individual field (flex: 1)

**Responsive**: Stacks vertically on mobile (< 768px)

### Day Checkboxes (Daily Tasks)

**Pattern**: Custom styled checkboxes for days of week

**HTML Structure**:
```html
<div class="days-of-week">
    <div class="day-checkbox checked" data-day="0">Mon</div>
    <div class="day-checkbox checked" data-day="1">Tue</div>
    <!-- ... -->
</div>
```

**JavaScript**: Toggle `.checked` class on click

## List Components

### Standard List Pattern

**Structure**:
```html
<ul class="list-name" id="list-container">
    <li class="empty-state">Loading...</li>
</ul>
```

**Loading State**:
```html
<li class="loading-state">Loading...</li>
```

**Empty State**:
```html
<li class="empty-state">No items available</li>
```

**Rendering Pattern**:
```javascript
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

### Card Item Pattern

**Common Structure**:
```html
<li class="card-item">
    <div class="card-content">
        <div class="card-text">
            <!-- Main content -->
        </div>
        <div class="card-actions">
            <!-- Action buttons -->
        </div>
    </div>
    <div class="card-meta">
        <!-- Metadata tags -->
    </div>
</li>
```

**Variations**:
- `.goal-item` - Goals page
- `.template-item` - Daily tasks templates
- `.todays-item` - Daily task instances
- `.card-item` - Morning cards

## Button Components

### Standard Buttons

**Primary Button**:
```html
<button class="btn">Action</button>
```

**Secondary Button**:
```html
<button class="btn btn-secondary">Cancel</button>
```

**Danger Button**:
```html
<button class="btn btn-danger">Delete</button>
```

**Small Button**:
```html
<button class="btn btn-sm">Small</button>
```

**Disabled Button**:
```html
<button class="btn" disabled>Disabled</button>
```

### Edit/Update Pattern

**Common Pattern**:
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

function cancelEdit() {
    editingId = null;
    // Reset form
    // Reset button
    // Hide cancel button
}
```

## Message Components

### Error Message

**Usage**: Display errors to user

**HTML**:
```html
<div class="error-message" style="display: none;"></div>
```

**JavaScript**:
```javascript
showError(errorContainer, 'Something went wrong');
```

### Success Message

**Usage**: Display success feedback

**HTML**:
```html
<div class="success-message" style="display: none;"></div>
```

**JavaScript**:
```javascript
showSuccess(successContainer, 'Saved successfully!');
```

### Info Banner

**Usage**: Informational messages

**HTML**:
```html
<div class="info-banner">
    Important information here
</div>
```

## Progress Indicators

### Progress Bar

**Structure**:
```html
<div class="progress-bar">
    <div class="progress-fill" style="width: 50%;"></div>
    <div class="goal-marker par-marker" style="left: 30%;"></div>
    <div class="goal-marker stretch-marker" style="left: 100%;"></div>
</div>
```

**Classes**:
- `.par-reached` - Yellow when par goal reached
- `.stretch-reached` - Green when stretch goal reached

### Collaboration Tracker

**Location**: Tasks page

**Display**: Slider showing collaboration score (1-9)

**JavaScript**: Updates position based on `tracker_value`

## Stats Cards

### Stat Card Pattern

**Structure**:
```html
<div class="stat-card">
    <div class="stat-detail">Description</div>
    <div class="stat-value">42</div>
</div>
```

**Gradient Background**: Purple gradient by default

**Usage**: Daily points, weekly stats, goal comparisons

## Responsive Design

### Mobile Breakpoint

**Breakpoint**: 768px

**Behavior**:
- Form rows stack vertically
- Card content stacks vertically
- Actions align to flex-end
- Full-width inputs

### Media Query Pattern

```css
@media (max-width: 768px) {
    .form-row {
        flex-direction: column;
        gap: 10px;
    }
    
    .card-content {
        flex-direction: column;
        gap: 10px;
    }
    
    .card-actions {
        align-self: flex-end;
    }
}
```

## Common UI Patterns

### Loading State

**Pattern**: Show loading, hide content

```javascript
showLoading('#loading-state');
hideLoading('#main-content');

// After data loads:
hideLoading('#loading-state');
showLoading('#main-content');
```

### Empty State

**Pattern**: Show message when no data

```html
<li class="empty-state">No items yet. Add your first item!</li>
```

### Conditional Rendering

**Pattern**: Show different UI based on state

```javascript
if (isLocked) {
    document.getElementById('summary-display').style.display = 'block';
    document.getElementById('selection-interface').style.display = 'none';
} else {
    document.getElementById('summary-display').style.display = 'none';
    document.getElementById('selection-interface').style.display = 'block';
}
```

### Toggle Pattern

**Pattern**: Switch between two states

```javascript
function toggleCard(cardId) {
    const cardDiv = document.querySelector(`[data-card-id="${cardId}"]`);
    const isSelected = selectedCardIds.includes(cardId);
    
    if (!isSelected) {
        selectedCardIds.push(cardId);
        cardDiv.classList.add('selected');
    } else {
        selectedCardIds = selectedCardIds.filter(id => id !== cardId);
        cardDiv.classList.remove('selected');
    }
}
```

## Component Integration

### Authentication Flow

Every page component follows this pattern:

1. Wait for auth (`await waitForAuth()`)
2. Load data (`await loadData()`)
3. Render interface (`renderInterface()`)

### API Integration

Standard pattern for API calls:

```javascript
async function loadData() {
    try {
        const data = await apiCall('/api/endpoint');
        
        if (data.status === 'success') {
            items = data.items;
            renderList();
        } else {
            showError('#error-message', data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('#error-message', 'Failed to load data');
    }
}
```

## Styling Guidelines

### Colors

- **Primary**: `#007bff` (blue)
- **Success**: `#28a745` (green)
- **Danger**: `#dc3545` (red)
- **Secondary**: `#6c757d` (gray)
- **Warning**: `#ffc107` (yellow)

### Spacing

- **Margin**: 15px between form groups
- **Padding**: 15px inside cards
- **Gap**: 10px between flex items

### Borders

- **Standard**: `1px solid #e0e0e0`
- **Hover**: `box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1)`
- **Border radius**: `8px` for cards, `4px` for inputs

### Typography

- **Font**: System font stack
- **Base size**: 14px
- **Large text**: 16px
- **Small text**: 12px

## Accessibility

### Keyboard Support

- Tab navigation works
- Enter submits forms
- Escape closes menus

### Screen Readers

- Semantic HTML elements
- Alt text for emojis (via title attributes)
- ARIA labels where needed

### Touch Targets

- Minimum 44px × 44px for buttons
- Adequate spacing between touch targets

