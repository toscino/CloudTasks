/**
 * CloudTasks shell: auth state, nav user display, streak/morning-card indicators.
 * Loaded from layout.html; flask-base handles hamburger nav and ?key= stripping.
 */

window.authState = {
    currentUsername: null,
    isAuthenticated: false,
    sessionBased: false,
    initialized: false,
    canSelectMorningCards: false,
    spouseUsername: null
};

window.taskPointsTodayCache = null;

function checkForInitialLogin() {
    const urlParams = new URLSearchParams(window.location.search);
    const secretKey = urlParams.get('secret_key');

    if (secretKey) {
        login(secretKey);
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
    }
}

async function login(secretKey) {
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ secret_key: secretKey })
        });

        if (!response.ok) {
            console.warn(`Login request returned HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            window.authState.currentUsername = data.username;
            window.authState.isAuthenticated = data.authenticated;
            window.authState.sessionBased = true;
            updateUserStatusNav();
            return true;
        }
        console.error('Login failed:', data.message);
        return false;
    } catch (error) {
        console.error('Login error:', error);
        return false;
    }
}

async function logout() {
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            console.warn(`Logout request returned HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            window.authState.currentUsername = 'test_user';
            window.authState.isAuthenticated = false;
            window.authState.sessionBased = false;
            updateUserStatusNav();
            return true;
        }
        console.error('Logout failed:', data.message);
        return false;
    } catch (error) {
        console.error('Logout error:', error);
        return false;
    }
}

function getApiHeaders() {
    return { 'Content-Type': 'application/json' };
}

function getApiParams() {
    return '';
}

async function getAuthStatus() {
    try {
        const response = await fetch('/api/user');

        if (!response.ok) {
            console.warn(`Auth status request returned HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            window.authState.currentUsername = data.username;
            window.authState.isAuthenticated = data.authenticated;
            window.authState.sessionBased = data.session_based || false;

            if (data.authenticated && data.username) {
                try {
                    const settingsResponse = await fetch('/api/user/settings');
                    const settingsData = await settingsResponse.json();
                    if (settingsData.status === 'success' && settingsData.settings) {
                        window.authState.canSelectMorningCards =
                            settingsData.settings.can_select_morning_cards || false;
                        window.authState.spouseUsername =
                            settingsData.settings.spouse_username || null;
                    }
                } catch (e) {
                    console.log('Could not fetch user settings:', e);
                }
            }

            window.authState.initialized = true;
            return { username: data.username, authenticated: data.authenticated };
        }
        console.error('Auth status check failed:', data.message);
    } catch (error) {
        console.log('Using fallback authentication:', error);
    }

    window.authState.currentUsername = 'test_user';
    window.authState.isAuthenticated = false;
    window.authState.sessionBased = false;
    window.authState.initialized = true;
    return { username: 'test_user', authenticated: false };
}

function updateUserStatusNav() {
    const wrap = document.querySelector('.nav-title-wrap');
    if (!wrap) return;

    let navUser = wrap.querySelector('.nav-user');
    if (!navUser) {
        navUser = document.createElement('div');
        navUser.className = 'nav-user';
        wrap.appendChild(navUser);
    }

    const username = window.authState.currentUsername || 'Loading...';
    navUser.textContent = username;
    if (window.authState.isAuthenticated) {
        navUser.classList.add('authenticated');
    } else {
        navUser.classList.remove('authenticated');
    }
}

async function checkPendingStreakMinimum() {
    const indicator = document.getElementById('streak-indicator');
    if (!indicator) return;
    if (!window.authState || !window.authState.isAuthenticated) {
        indicator.style.display = 'none';
        return;
    }
    try {
        const response = await fetch('/api/task-points/today');
        const data = await response.json();
        if (data.status !== 'success' || !data.today_points || !data.thresholds) {
            indicator.style.display = 'none';
            return;
        }
        window.taskPointsTodayCache = data;
        const todayPoints = data.today_points;
        const thresholds = data.thresholds;
        const currentUser = window.authState.currentUsername;
        let anyBelow = false;
        let youBelow = false;
        let spouseBelow = false;
        const parts = [];
        const belowNames = data.below_minimum || [];
        for (const [user, pts] of Object.entries(todayPoints)) {
            const thresh = thresholds[user] != null ? thresholds[user] : 10;
            const below = (pts == null ? 0 : pts) < thresh;
            if (below) {
                anyBelow = true;
                if (user === currentUser) youBelow = true;
                else spouseBelow = true;
            }
            parts.push(`${user}: ${pts == null ? 0 : pts}/${thresh} pts`);
        }
        if (anyBelow) {
            indicator.style.display = 'inline-block';
            indicator.classList.remove('below-you', 'below-spouse', 'below-both');
            indicator.classList.add('below-minimum');
            if (youBelow && spouseBelow) indicator.classList.add('below-both');
            else if (youBelow) indicator.classList.add('below-you');
            else indicator.classList.add('below-spouse');
            let title = parts.join(' • ');
            if (belowNames.length) title += ' — Below minimum: ' + belowNames.join(', ');
            indicator.title = title;
        } else {
            indicator.style.display = 'none';
            indicator.classList.remove('below-minimum', 'below-you', 'below-spouse', 'below-both');
        }
    } catch (error) {
        console.error('Error checking streak minimum:', error);
        indicator.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    await getAuthStatus();
    updateUserStatusNav();
    checkPendingStreakMinimum();
    checkForInitialLogin();
});
