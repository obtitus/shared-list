/**
 * Shared Shopping List PWA - JavaScript Application
 * Handles API interactions, UI updates, and PWA functionality
 */

// Configuration
const API_BASE_URL = '/items';
const API_ITEM_URL = (id) => `/items/${id}`;
const API_TOGGLE_URL = (id) => `/items/${id}/toggle`;
const API_CLEAR_URL = '/items';

// State Management
let shoppingList = [];
let isLoading = false;
let isOnline = navigator.onLine;

// DOM Elements
const elements = {
    shoppingList: document.getElementById('shoppingList'),
    emptyState: document.getElementById('emptyState'),
    addItemForm: document.getElementById('addItemForm'),
    itemNameInput: document.getElementById('itemName'),
    itemQuantityInput: document.getElementById('itemQuantity'),
    connectionStatus: document.getElementById('connectionStatus'),
    statusDot: document.querySelector('.status-dot'),
    statusText: document.querySelector('.status-text'),
    clearBtn: document.getElementById('clearBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    toastContainer: document.getElementById('toastContainer'),
    loadingOverlay: document.getElementById('loadingOverlay')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadShoppingList();
    updateConnectionStatus();
});

/**
 * Initialize Event Listeners
 */
function initializeEventListeners() {
    // Form submission
    elements.addItemForm.addEventListener('submit', handleAddItem);

    // Button actions
    elements.clearBtn.addEventListener('click', handleClearAll);
    elements.refreshBtn.addEventListener('click', handleRefresh);

    // Connection status monitoring
    window.addEventListener('online', () => {
        isOnline = true;
        updateConnectionStatus();
        loadShoppingList();
    });

    window.addEventListener('offline', () => {
        isOnline = false;
        updateConnectionStatus();
        showToast('You are now offline. Changes will sync when connection is restored.', 'warning');
    });

    // Input validation
    elements.itemNameInput.addEventListener('input', validateForm);
    elements.itemQuantityInput.addEventListener('input', validateForm);

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
}



/**
 * API Request Wrapper
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Handle responses that might not have a JSON body (e.g., DELETE requests)
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else {
            return {}; // Return empty object for non-JSON responses
        }
    } catch (error) {
        console.error('API Request failed:', error);
        throw error;
    }
}

/**
 * Load Shopping List from API
 */
async function loadShoppingList() {
    if (!isOnline) {
        showToast('Cannot load data while offline', 'error');
        return;
    }

    setLoading(true);

    try {
        shoppingList = await apiRequest(API_BASE_URL);
        renderShoppingList();
        updateEmptyState();
        showToast('Shopping list loaded successfully', 'success');
    } catch (error) {
        showToast('Failed to load shopping list', 'error');
        console.error('Load shopping list error:', error);
    } finally {
        setLoading(false);
    }
}

/**
 * Add New Item
 */
async function handleAddItem(e) {
    e.preventDefault();

    if (!isOnline) {
        showToast('Cannot add items while offline', 'error');
        return;
    }

    const name = elements.itemNameInput.value.trim();
    const quantity = parseInt(elements.itemQuantityInput.value, 10);

    if (!name || quantity <= 0) {
        showToast('Please enter a valid item name and quantity', 'error');
        return;
    }

    setLoading(true);

    try {
        const newItem = await apiRequest(API_BASE_URL, {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                quantity: quantity,
                completed: false
            })
        });

        shoppingList.push(newItem);
        renderShoppingList();
        updateEmptyState();

        // Reset form
        elements.addItemForm.reset();
        elements.itemQuantityInput.value = '1';

        showToast('Item added successfully', 'success');
    } catch (error) {
        showToast('Failed to add item', 'error');
        console.error('Add item error:', error);
    } finally {
        setLoading(false);
    }
}

/**
 * Toggle Item Completion Status
 */
async function handleToggleItem(itemId) {
    if (!isOnline) {
        showToast('Cannot update items while offline', 'error');
        return;
    }

    const itemIndex = shoppingList.findIndex(item => item.id === itemId);
    if (itemIndex === -1) return;

    // Optimistic update
    shoppingList[itemIndex].completed = !shoppingList[itemIndex].completed;
    renderShoppingList();

    try {
        await apiRequest(API_TOGGLE_URL(itemId), { method: 'PATCH' });
        showToast('Item updated successfully', 'success');
    } catch (error) {
        // Revert optimistic update on error
        shoppingList[itemIndex].completed = !shoppingList[itemIndex].completed;
        renderShoppingList();
        showToast('Failed to update item', 'error');
        console.error('Toggle item error:', error);
    }
}

/**
 * Delete Item
 */
async function handleDeleteItem(itemId) {
    if (!isOnline) {
        showToast('Cannot delete items while offline', 'error');
        return;
    }

    if (!confirm('Are you sure you want to delete this item?')) {
        return;
    }

    const itemIndex = shoppingList.findIndex(item => item.id === itemId);
    if (itemIndex === -1) return;

    // Store for rollback
    const deletedItem = shoppingList[itemIndex];
    shoppingList.splice(itemIndex, 1);
    renderShoppingList();
    updateEmptyState();

    try {
        await apiRequest(API_ITEM_URL(itemId), { method: 'DELETE' });
        showToast('Item deleted successfully', 'success');
    } catch (error) {
        // Restore item on error
        shoppingList.splice(itemIndex, 0, deletedItem);
        renderShoppingList();
        updateEmptyState();
        showToast('Failed to delete item', 'error');
        console.error('Delete item error:', error);
    }
}

/**
 * Clear All Items
 */
async function handleClearAll() {
    if (!isOnline) {
        showToast('Cannot clear list while offline', 'error');
        return;
    }

    if (!confirm('Are you sure you want to clear all items? This action cannot be undone.')) {
        return;
    }

    const backupList = [...shoppingList];
    shoppingList = [];
    renderShoppingList();
    updateEmptyState();

    try {
        await apiRequest(API_CLEAR_URL, { method: 'DELETE' });
        showToast('All items cleared successfully', 'success');
    } catch (error) {
        // Restore on error
        shoppingList = backupList;
        renderShoppingList();
        updateEmptyState();
        showToast('Failed to clear items', 'error');
        console.error('Clear all error:', error);
    }
}

/**
 * Refresh List
 */
async function handleRefresh() {
    await loadShoppingList();
}

/**
 * Render Shopping List
 */
function renderShoppingList() {
    elements.shoppingList.innerHTML = '';

    shoppingList.forEach(item => {
        const listItem = document.createElement('div');
        listItem.className = `list-item ${item.completed ? 'completed' : ''}`;

        listItem.innerHTML = `
            <button class="item-checkbox ${item.completed ? 'checked' : ''}"
                    onclick="handleToggleItem(${item.id})"
                    aria-label="${item.completed ? 'Mark as incomplete' : 'Mark as complete'}">
            </button>

            <div class="item-content">
                <span class="item-name">${escapeHtml(item.name)}</span>
                <span class="item-quantity">${item.quantity}</span>
            </div>

            <div class="item-actions">
                <button class="delete-btn" onclick="handleDeleteItem(${item.id})"
                        aria-label="Delete ${escapeHtml(item.name)}">
                    🗑️ Delete
                </button>
            </div>
        `;

        elements.shoppingList.appendChild(listItem);
    });
}

/**
 * Update Empty State
 */
function updateEmptyState() {
    if (shoppingList.length === 0) {
        elements.emptyState.style.display = 'block';
        elements.shoppingList.style.display = 'none';
    } else {
        elements.emptyState.style.display = 'none';
        elements.shoppingList.style.display = 'flex';
    }
}

/**
 * Update Connection Status
 */
function updateConnectionStatus() {
    isOnline = navigator.onLine;

    if (isOnline) {
        elements.statusDot.classList.remove('offline');
        elements.statusText.textContent = 'Online';
        elements.statusText.style.color = '#ffffff';
    } else {
        elements.statusDot.classList.add('offline');
        elements.statusText.textContent = 'Offline';
        elements.statusText.style.color = '#ff4444';
    }
}

/**
 * Show Toast Notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

/**
 * Set Loading State
 */
function setLoading(loading) {
    isLoading = loading;

    if (isLoading) {
        elements.loadingOverlay.style.display = 'flex';
    } else {
        elements.loadingOverlay.style.display = 'none';
    }
}

/**
 * Validate Form
 */
function validateForm() {
    const name = elements.itemNameInput.value.trim();
    const quantity = parseInt(elements.itemQuantityInput.value, 10);

    const isValid = name.length > 0 && quantity > 0;
    elements.addItemForm.querySelector('.add-btn').disabled = !isValid;
}

/**
 * Handle Keyboard Shortcuts
 */
function handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + R: Refresh
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        handleRefresh();
    }

    // Ctrl/Cmd + K: Focus on add item input
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        elements.itemNameInput.focus();
        elements.itemNameInput.select(); // Ensure it's focused and ready for input
    }

    // Escape: Clear selection/focus
    if (e.key === 'Escape') {
        document.activeElement.blur();
    }
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Global Functions (for onclick handlers)
 */
window.handleToggleItem = handleToggleItem;
window.handleDeleteItem = handleDeleteItem;

// Expose for testing
window.app = {
    loadShoppingList,
    handleAddItem,
    handleToggleItem,
    handleDeleteItem,
    handleClearAll,
    handleRefresh,
    showToast,
    setLoading
};
