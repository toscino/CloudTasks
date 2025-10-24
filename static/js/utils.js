/**
 * Shared JavaScript utilities for CloudTasks frontend
 * Provides common functions for authentication, API calls, and UI management
 */

/**
 * Wait for authentication state to be initialized
 * @returns {Promise<void>}
 */
export function waitForAuth() {
    return new Promise(resolve => {
        const checkAuth = () => {
            if (window.authState && 
                window.authState.initialized &&
                window.authState.currentUsername && 
                window.authState.currentUsername !== 'Loading...' &&
                window.authState.currentUsername !== null) {
                resolve();
            } else {
                setTimeout(checkAuth, 100);
            }
        };
        checkAuth();
    });
}

/**
 * Standardized API call with error handling
 * 
 * Makes an HTTP request and handles both network-level and API-level errors.
 * 
 * @param {string} url - API endpoint URL
 * @param {object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise<object>} API response data with {status: 'success/error', ...}
 * @throws {Error} Throws on network errors or when response cannot be parsed
 * 
 * @example
 * // GET request
 * const data = await apiCall('/api/tasks');
 * if (data.status === 'success') {
 *     console.log(data.tasks);
 * }
 * 
 * @example
 * // POST request
 * const data = await apiCall('/api/goals', {
 *     method: 'POST',
 *     body: JSON.stringify({ description: 'My goal' })
 * });
 */
export async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        // Log HTTP status for debugging
        if (!response.ok) {
            console.warn(`API call to ${url} returned HTTP ${response.status}`);
        }
        
        // Parse JSON response
        const data = await response.json();
        
        // Add HTTP status to response for debugging
        data._httpStatus = response.status;
        
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Show error message to user in a designated error container
 * 
 * Use this for non-blocking inline error messages that don't prevent user interaction.
 * For critical blocking errors, use alert() instead.
 * 
 * @param {string|HTMLElement} container - Container element or selector (e.g., '#error-message')
 * @param {string} message - Error message to display
 * 
 * @example
 * // Show error in designated container
 * showError('#error-message', 'Failed to load tasks');
 * 
 * @example
 * // Clear error by showing empty message
 * showError('#error-message', '');
 */
export function showError(container, message) {
    const errorDiv = typeof container === 'string' 
        ? document.querySelector(container) 
        : container;
    
    if (!errorDiv) {
        console.warn(`Error container not found: ${container}`);
        return;
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = message ? 'block' : 'none';
    errorDiv.className = 'error-message';
}

/**
 * Show success message to user in a designated success container
 * 
 * @param {string|HTMLElement} container - Container element or selector (e.g., '#success-message')
 * @param {string} message - Success message to display
 * @param {number} autoHideMs - Optional: Auto-hide after this many milliseconds
 * 
 * @example
 * // Show success message
 * showSuccess('#success-message', 'Task completed successfully!');
 * 
 * @example
 * // Show success and auto-hide after 3 seconds
 * showSuccess('#success-message', 'Goal saved!', 3000);
 */
export function showSuccess(container, message, autoHideMs = 0) {
    const successDiv = typeof container === 'string' 
        ? document.querySelector(container) 
        : container;
    
    if (!successDiv) {
        console.warn(`Success container not found: ${container}`);
        return;
    }
    
    successDiv.textContent = message;
    successDiv.style.display = message ? 'block' : 'none';
    successDiv.className = 'success-message';
    
    // Auto-hide if requested
    if (autoHideMs > 0 && message) {
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, autoHideMs);
    }
}

/**
 * Show loading state
 * @param {string|HTMLElement} element - Element to show loading state
 */
export function showLoading(element) {
    const el = typeof element === 'string' ? document.querySelector(element) : element;
    if (el) el.style.display = 'block';
}

/**
 * Hide loading state
 * @param {string|HTMLElement} element - Element to hide loading state
 */
export function hideLoading(element) {
    const el = typeof element === 'string' ? document.querySelector(element) : element;
    if (el) el.style.display = 'none';
}

/**
 * Generic list rendering helper
 * @param {HTMLElement} container - Container element to render into
 * @param {Array} items - Array of items to render
 * @param {Function} renderItem - Function to render each item (returns HTMLElement)
 * @param {string} emptyMessage - Message to show when no items
 */
export function renderList(container, items, renderItem, emptyMessage) {
    if (!container) return;
    
    if (!items || items.length === 0) {
        container.innerHTML = emptyMessage 
            ? `<li class="empty-state">${emptyMessage}</li>` 
            : '';
        return;
    }
    
    container.innerHTML = '';
    items.forEach(item => {
        const element = renderItem(item);
        if (element) {
            container.appendChild(element);
        }
    });
}

/**
 * Reset form fields to initial state
 * 
 * Clears all input, textarea, and select fields within a form container.
 * Also clears any error/success messages.
 * 
 * @param {string|HTMLElement} formContainer - Form container element or selector
 * 
 * @example
 * // Reset form by ID
 * resetForm('#add-goal-form');
 * 
 * @example
 * // Reset form by element
 * const form = document.getElementById('add-goal-form');
 * resetForm(form);
 */
export function resetForm(formContainer) {
    const form = typeof formContainer === 'string' 
        ? document.querySelector(formContainer) 
        : formContainer;
    
    if (!form) {
        console.warn(`Form container not found: ${formContainer}`);
        return;
    }
    
    // Reset all input fields
    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        if (input.type === 'checkbox' || input.type === 'radio') {
            input.checked = false;
        } else {
            input.value = '';
        }
    });
    
    // Clear error and success messages
    const errorMessages = form.querySelectorAll('.error-message');
    errorMessages.forEach(msg => {
        msg.textContent = '';
        msg.style.display = 'none';
    });
    
    const successMessages = form.querySelectorAll('.success-message');
    successMessages.forEach(msg => {
        msg.textContent = '';
        msg.style.display = 'none';
    });
}

/**
 * Display blocking alert message (browser alert)
 * 
 * Use this for critical errors that require user acknowledgment before proceeding.
 * For non-blocking errors, prefer showError() instead.
 * 
 * @param {string} message - Message to display
 * 
 * @example
 * // Critical validation error
 * if (!taskDescription) {
 *     alert('Task description is required');
 *     return;
 * }
 */
export function alert(message) {
    window.alert(message);
}

/**
 * Display confirmation dialog (browser confirm)
 * 
 * Use this to get user confirmation before destructive actions.
 * 
 * @param {string} message - Message to display
 * @returns {boolean} True if user clicked OK, false if cancelled
 * 
 * @example
 * // Confirm before deletion
 * if (confirm('Are you sure you want to delete this goal?')) {
 *     await deleteGoal(goalId);
 * }
 */
export function confirm(message) {
    return window.confirm(message);
}

/**
 * Scroll to top of page smoothly
 */
export function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Get current username from auth state
 * @returns {string} Current username
 */
export function getCurrentUsername() {
    return window.authState?.currentUsername || 'test_user';
}

/**
 * Check if user is authenticated
 * @returns {boolean} True if authenticated
 */
export function isAuthenticated() {
    return window.authState?.isAuthenticated || false;
}

