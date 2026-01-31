/**
 * Shared Shopping List PWA - JavaScript Application
 * Handles API interactions, UI updates, and PWA functionality
 */

// Configuration
const API_LIST_URL = (id) => `/lists/${id}`;
const API_BASE_URL = '/items';
const API_ITEM_URL = (id) => `/items/${id}`;
const API_TOGGLE_URL = (id) => `/items/${id}/toggle`;
const API_CLEAR_URL = '/items';

// State Management
let shoppingList = [];
let currentList = { id: 1, name: 'Shopping List' };
let isLoading = false;
let isOnline = navigator.onLine;
let isRealTimeConnected = false;
let eventSource = null;
let hourlyRefreshTimer = null;
let clientId = null;
let selectedItemId = null;
let sseRetryCount = 0;
let sseRetryTimeout = null;

// DOM Elements (lazy-loaded)
let elements = null;

function getElements() {
    if (!elements) {
        elements = {
            shoppingList: document.getElementById('shoppingList'),
            emptyState: document.getElementById('emptyState'),
            addItemForm: document.getElementById('addItemForm'),
            itemNameInput: document.getElementById('itemName'),
            connectionStatus: document.getElementById('connectionStatus'),
            statusDot: document.querySelector('.status-dot'),
            clearBtn: document.getElementById('clearBtn'),
            refreshBtn: document.getElementById('refreshBtn'),
            exportBtn: document.getElementById('exportBtn'),
            importBtn: document.getElementById('importBtn'),
            importModal: document.getElementById('importModal'),
            importText: document.getElementById('importText'),
            importCancel: document.getElementById('importCancel'),
            importConfirm: document.getElementById('importConfirm'),
            importModalClose: document.getElementById('importModalClose'),
            toastContainer: document.getElementById('toastContainer'),
            loadingOverlay: document.getElementById('loadingOverlay')
        };
    }
    return elements;
}

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    elements = getElements(); // Initialize elements when DOM is ready
    initializeClientId();
    initializeEventListeners();
    loadListInfo();
    loadShoppingList();
    updateConnectionStatus();
    setupSSE();
    setupHourlyRefresh();
});

/**
 * Initialize Client ID
 */
function initializeClientId() {
    // Try to get client ID from sessionStorage, or generate a new one
    // sessionStorage is unique per tab/window, unlike localStorage
    clientId = sessionStorage.getItem('shopping-list-client-id');
    if (!clientId) {
        clientId = 'client-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('shopping-list-client-id', clientId);
    }
    console.log('Client ID:', clientId);

    // Expose clientId globally for testing
    window.clientId = clientId;
}

/**
 * Initialize Event Listeners
 */
function initializeEventListeners() {
    // Form submission
    if (elements.addItemForm) {
        elements.addItemForm.addEventListener('submit', handleAddItem);
    }

    // Button actions
    if (elements.clearBtn) {
        elements.clearBtn.addEventListener('click', handleClearAll);
    }
    if (elements.refreshBtn) {
        elements.refreshBtn.addEventListener('click', handleRefresh);
    }
    if (elements.exportBtn) {
        elements.exportBtn.addEventListener('click', handleExport);
    }
    if (elements.importBtn) {
        elements.importBtn.addEventListener('click', handleImport);
    }

    // List title editing
    const listTitleElement = document.querySelector('.list-title');
    if (listTitleElement) {
        listTitleElement.addEventListener('click', startListNameEdit);
    }

    // Connection status monitoring
    window.addEventListener('online', () => {
        isOnline = true;
        updateConnectionStatus();
        loadShoppingList();

        // Reset SSE retry count when coming back online
        sseRetryCount = 0;
        if (!eventSource && !sseRetryTimeout) {
            // Try to reconnect immediately if not already connected
            setTimeout(() => connectToSSE(), 1000);
        }
    });

    window.addEventListener('offline', () => {
        isOnline = false;
        updateConnectionStatus();
        showToast('You are now offline. Changes will sync when connection is restored.', 'warning');

        // Clear any pending retry timeouts when going offline
        if (sseRetryTimeout) {
            clearTimeout(sseRetryTimeout);
            sseRetryTimeout = null;
        }
        sseRetryCount = 0;
    });

    // Input validation
    if (elements.itemNameInput) {
        elements.itemNameInput.addEventListener('input', validateForm);
    }

    // Import modal event listeners
    if (elements.importModalClose) {
        elements.importModalClose.addEventListener('click', closeImportModal);
    }
    if (elements.importCancel) {
        elements.importCancel.addEventListener('click', closeImportModal);
    }
    if (elements.importConfirm) {
        elements.importConfirm.addEventListener('click', handleImportConfirm);
    }

    // Close modal when clicking outside
    if (elements.importModal) {
        elements.importModal.addEventListener('click', (e) => {
            if (e.target === elements.importModal) {
                closeImportModal();
            }
        });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);

    // Handle page visibility changes (iOS unlock, tab switching)
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && isOnline && !isLoading) {
            console.log('Page became visible - coordinating connection and refresh');
            // Coordinate connection check and refresh with debouncing
            handleVisibilityChange();
        }
    });

    // Handle page focus/blur events for tab switching scenarios
    window.addEventListener('focus', () => {
        if (isOnline && !isLoading) {
            console.log('Page gained focus - coordinating connection and refresh');
            // Coordinate connection check and refresh with debouncing
            handleFocusChange();
        }
    });

    window.addEventListener('blur', () => {
        console.log('Page lost focus');
        // Don't disconnect SSE on blur, let it handle natural disconnection
    });

    // Handle mobile-specific resume events (iOS)
    document.addEventListener('resume', () => {
        if (isOnline && !isLoading) {
            console.log('Mobile app resumed - forcing connection check and refresh');
            // Mobile devices often need explicit reconnection after resume
            handleMobileResume();
        }
    }, { passive: true });

    // Handle pageshow event for better mobile support
    window.addEventListener('pageshow', (event) => {
        if (event.persisted || (event.target && event.target.visibilityState === 'visible')) {
            console.log('Page shown (possibly from cache) - coordinating connection and refresh');
            if (isOnline && !isLoading) {
                handlePageShow(event);
            }
        }
    }, { passive: true });
}



/**
 * API Request Wrapper
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                'X-Client-ID': clientId,
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
 * Load List Information from API
 */
async function loadListInfo() {
    if (!isOnline) {
        updateListTitle();
        return;
    }

    try {
        const listInfo = await apiRequest(API_LIST_URL(currentList.id));
        currentList = listInfo;
        updateListTitle();
    } catch (error) {
        console.error('Load list info error:', error);
        // Continue with default list info
        updateListTitle();
    }
}

/**
 * Update List Title in UI
 */
function updateListTitle() {
    const listTitleElement = document.querySelector('.list-title');
    if (listTitleElement) {
        listTitleElement.textContent = currentList.name;
    }

    // Update page title
    document.title = `${currentList.name} - Shared Shopping List`;
}

/**
 * Start editing the list name
 */
function startListNameEdit() {
    const listTitleElement = document.querySelector('.list-title');
    if (!listTitleElement || !isOnline) {
        if (!isOnline) {
            showToast('Cannot edit list name while offline', 'warning');
        }
        return;
    }

    const currentName = currentList.name;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'list-title-input';
    input.style.cssText = `
        font-size: inherit;
        font-weight: inherit;
        background: transparent;
        border: 2px solid var(--accent-blue);
        border-radius: 4px;
        padding: 4px 8px;
        outline: none;
        color: inherit;
    `;

    // Replace title with input
    listTitleElement.textContent = '';
    listTitleElement.appendChild(input);
    input.focus();
    input.select();

    // Handle save/cancel
    const saveEdit = async () => {
        const newName = input.value.trim();
        if (newName && newName !== currentName) {
            try {
                await apiRequest(API_LIST_URL(currentList.id), {
                    method: 'PUT',
                    body: JSON.stringify({ name: newName })
                });

                currentList.name = newName;
                updateListTitle();
                console.log('List name updated successfully');
            } catch (error) {
                showToast('Failed to update list name', 'error');
                console.error('Update list name error:', error);
                updateListTitle(); // Revert to original
            }
        } else {
            updateListTitle(); // Revert to original
        }
    };

    const cancelEdit = () => {
        updateListTitle(); // Revert to original
    };

    input.addEventListener('blur', saveEdit);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            saveEdit();
        } else if (e.key === 'Escape') {
            cancelEdit();
        }
    });
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
        console.log('Shopping list loaded successfully');
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

    console.log('handleAddItem called');
    console.log('Form elements:', elements);
    console.log('Item name input value:', elements.itemNameInput.value);
    console.log('Item name trimmed:', elements.itemNameInput.value.trim());
    console.log('Selected item ID:', selectedItemId);

    if (!isOnline) {
        showToast('Cannot add items while offline', 'error');
        return;
    }

    let name = elements.itemNameInput.value.trim();

    // Allow empty names for visual spacers (name is already trimmed)

    console.log('Adding item with name:', name);

    setLoading(true);

    try {
        const payload = {
            name: name,
            quantity: 1,
            completed: false
        };

        // If an item is selected, insert above it
        if (selectedItemId !== null) {
            const selectedItem = shoppingList.find(item => item.id === selectedItemId);
            if (selectedItem) {
                payload.order_index = selectedItem.order_index;
            }
        }

        console.log('Sending API request with payload:', payload);

        const newItem = await apiRequest(API_BASE_URL, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        console.log('API response received:', newItem);

        // Insert at correct position locally
        if (selectedItemId !== null) {
            const selectedIndex = shoppingList.findIndex(item => item.id === selectedItemId);
            if (selectedIndex !== -1) {
                shoppingList.splice(selectedIndex, 0, newItem);
            } else {
                shoppingList.push(newItem);
            }
        } else {
            shoppingList.push(newItem);
        }

        console.log('Shopping list after adding item:', shoppingList);

        // Clear selection
        selectedItemId = null;

        renderShoppingList();
        updateEmptyState();

        // Reset form
        elements.addItemForm.reset();

        console.log('Item added successfully');
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
        console.log('Item updated successfully');
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
        console.log('Item deleted successfully');
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
        console.log('All items cleared successfully');
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
 * Handle Export Button Click
 */
async function handleExport() {
    if (shoppingList.length === 0) {
        showToast('No items to export', 'warning');
        return;
    }

    // Format items as plain text, one per line
    const exportText = shoppingList
        .sort((a, b) => a.order_index - b.order_index)
        .map(item => {
            const checkmark = item.completed ? '✓ ' : '';
            const quantity = item.quantity > 1 ? ` x ${item.quantity}` : '';
            return `${checkmark}${item.name}${quantity}`;
        })
        .join('\n');

    const exportData = {
        title: `${currentList.name} - Shopping List`,
        text: exportText,
    };

    try {
        // Try Web Share API first (excellent iOS support)
        if (navigator.share && navigator.canShare && navigator.canShare(exportData)) {
            await navigator.share(exportData);
            console.log('List shared successfully');
            return;
        }
    } catch (error) {
        console.log('Web Share API not available or failed, trying clipboard');
    }
    console.log('=== SHOPPING LIST EXPORT ===');
    console.log(exportText);
    console.log('=== END EXPORT ===');
    // Fallback to clipboard API
    try {
        await navigator.clipboard.writeText(exportText);
        showToast('List copied to clipboard', 'success');
    } catch (error) {
        console.error('Clipboard API failed:', error);

        console.log('List logged to console - copy manually');
    }
}

/**
 * Handle Import Button Click
 */
function handleImport() {
    // Clear previous content
    elements.importText.value = '';

    // Show modal
    elements.importModal.style.display = 'flex';

    // Focus on textarea
    setTimeout(() => {
        elements.importText.focus();
    }, 100);
}

/**
 * Close Import Modal
 */
function closeImportModal() {
    elements.importModal.style.display = 'none';
}

/**
 * Handle Import Confirm Button Click
 */
async function handleImportConfirm() {
    if (!isOnline) {
        showToast('Cannot import items while offline', 'error');
        closeImportModal();
        return;
    }

    const importText = elements.importText.value.trim();

    if (!importText) {
        showToast('Please enter some text to import', 'warning');
        return;
    }

    // Parse the text
    const parsedItems = parseImportText(importText);

    if (parsedItems.length === 0) {
        showToast('No valid items found to import', 'warning');
        return;
    }

    // Close modal first
    closeImportModal();

    // Show loading
    setLoading(true);

    try {
        let successCount = 0;
        let errorCount = 0;

        // Add items sequentially
        for (const item of parsedItems) {
            try {
                const newItem = await apiRequest(API_BASE_URL, {
                    method: 'POST',
                    body: JSON.stringify({
                        name: item.name,
                        quantity: item.quantity,
                        completed: item.completed
                    })
                });

                // Add to local list
                shoppingList.push(newItem);
                successCount++;
            } catch (error) {
                console.error('Failed to import item:', item, error);
                errorCount++;
            }
        }

        // Update UI
        renderShoppingList();
        updateEmptyState();

        // Show result message
        if (errorCount === 0) {
            showToast(`Successfully imported ${successCount} item${successCount !== 1 ? 's' : ''}`, 'success');
        } else {
            showToast(`Imported ${successCount} item${successCount !== 1 ? 's' : ''}, ${errorCount} failed`, 'warning');
        }

    } catch (error) {
        showToast('Failed to import items', 'error');
        console.error('Import error:', error);
    } finally {
        setLoading(false);
    }
}

/**
 * Parse import text into items
 */
function parseImportText(text) {
    const items = [];

    // Split by newlines and process each line
    const lines = text.split('\n');

    for (const line of lines) {
        const trimmedLine = line.trim();

        // Skip empty lines
        if (!trimmedLine) continue;

        // Remove leading bullets/markers
        const cleanLine = trimmedLine.replace(/^[\s\-\*\•\◦•○●■□▪▫]+/, '').trim();

        // Skip if line becomes empty after cleaning
        if (!cleanLine) continue;

        // Check for completion status
        let completed = false;
        let processedLine = cleanLine;

        // Check for checkmark patterns: ✓, [x], [X], etc.
        if (/^✓/.test(processedLine)) {
            completed = true;
            processedLine = processedLine.replace(/^✓\s*/, '');
        } else if (/^\[x\]/i.test(processedLine)) {
            completed = true;
            processedLine = processedLine.replace(/^\[x\]\s*/i, '');
        }
        // Also handle [ ] for explicitly incomplete items (though they're already false by default)
        else if (/^\[\s*\]/.test(processedLine)) {
            processedLine = processedLine.replace(/^\[\s*\]\s*/, '');
        }

        // Parse quantity patterns
        // Match patterns like: "Item x 2", "2 x Item", "Item x2", "2x Item"
        const quantityRegex = /^(.+?)\s*x\s*(\d+)$/i;
        const reverseQuantityRegex = /^(\d+)\s*x\s*(.+)$/i;

        let name = processedLine.trim();
        let quantity = 1;

        // Try "Item x Quantity" pattern
        const quantityMatch = processedLine.match(quantityRegex);
        if (quantityMatch) {
            name = quantityMatch[1].trim();
            quantity = parseInt(quantityMatch[2], 10);
        } else {
            // Try "Quantity x Item" pattern
            const reverseMatch = processedLine.match(reverseQuantityRegex);
            if (reverseMatch) {
                quantity = parseInt(reverseMatch[1], 10);
                name = reverseMatch[2].trim();
            }
        }

        // Validate quantity (allow empty names for visual spacers)
        if (quantity > 0) {
            items.push({
                name: name,
                quantity: quantity,
                completed: completed
            });
        }
    }

    return items;
}

/**
 * Render Shopping List
 */
function renderShoppingList() {
    elements.shoppingList.innerHTML = '';

    shoppingList.forEach(item => {
        const listItem = document.createElement('div');
        listItem.className = `list-item ${item.completed ? 'completed' : ''} ${item.id === selectedItemId ? 'selected' : ''}`;
        listItem.setAttribute('data-item-id', item.id);
        listItem.setAttribute('data-order-index', item.order_index || 0);
        listItem.draggable = true;
        listItem.onclick = () => handleSelectItem(item.id);

        listItem.innerHTML = `
            <div class="drag-handle" draggable="true" ondragstart="handleDragStart(event, ${item.id})" title="Drag to reorder">
                ⋮⋮
            </div>

            <button class="item-checkbox ${item.completed ? 'checked' : ''}"
                    onclick="handleToggleItem(${item.id})"
                    aria-label="${item.completed ? 'Mark as incomplete' : 'Mark as complete'}">
            </button>

            <div class="item-content">
                <span class="item-name ${!item.name ? 'empty-spacer' : ''}">${item.name ? escapeHtml(item.name) : '—'}</span>
                <button class="item-btn edit-btn" onclick="event.stopPropagation(); console.log('Edit button clicked for item:', ${item.id}); startItemNameEdit(${item.id})"
                        aria-label="Edit ${escapeHtml(item.name || 'item')}">
                    ✏️
                </button>
            </div>

            <div class="item-actions">
                <button class="item-btn delete-btn" onclick="handleDeleteItem(${item.id})"
                        aria-label="Delete ${escapeHtml(item.name)}">
                    🗑️
                </button>
            </div>
        `;

        // Add passive touch event listeners for better scrolling performance
        const dragHandle = listItem.querySelector('.drag-handle');
        if (dragHandle) {
            dragHandle.addEventListener('touchstart', (e) => handleTouchStart(e, item.id), { passive: false });
            dragHandle.addEventListener('touchmove', handleTouchMove, { passive: false });
            dragHandle.addEventListener('touchend', handleTouchEnd, { passive: true });
        }

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

    elements.statusDot.classList.remove('offline', 'connected');
    if (!isOnline || !isRealTimeConnected) {
        elements.statusDot.classList.add('offline');
        console.log(!isOnline ? 'Offline' : 'Online (no real-time connection)');
    } else {
        elements.statusDot.classList.add('connected');
        console.log('Online and real-time connected');
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
    // Allow empty names for visual spacers, no quantity validation needed
    // Button is always enabled since quantity is always 1
    const addBtn = elements.addItemForm.querySelector('.add-btn');
    if (addBtn) {
        addBtn.disabled = false;
    }
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
        selectedItemId = null;
        renderShoppingList();
        document.activeElement.blur();
    }
}

/**
 * Start editing an item name
 */
function startItemNameEdit(itemId) {
    console.log('startItemNameEdit called with itemId:', itemId);
    if (!isOnline) {
        showToast('Cannot edit items while offline', 'warning');
        return;
    }

    const itemIndex = shoppingList.findIndex(item => item.id === itemId);
    if (itemIndex === -1) return;

    const item = shoppingList[itemIndex];
    const itemElement = document.querySelector(`[data-item-id="${itemId}"]`);
    if (!itemElement) return;

    const itemNameSpan = itemElement.querySelector('.item-name');
    if (!itemNameSpan) return;

    const currentName = item.name || '';

    // Create input field (replace span entirely for proper flex layout)
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'item-name-input';
    input.style.cssText = `
        font-size: var(--font-size-base);
        font-weight: var(--font-weight-medium);
        color: var(--text-primary);
        background: transparent;
        border: 2px solid var(--accent-blue);
        border-radius: 4px;
        padding: 2px 6px;
        outline: none;
        flex: 1;
        min-width: 100px;
    `;

    // Replace span with input entirely (maintains flex layout)
    itemNameSpan.parentNode.replaceChild(input, itemNameSpan);

    // Focus and select text (with iOS compatibility)
    setTimeout(() => {
        input.focus();
        input.select();
        // For iOS, also set selection range
        if (input.setSelectionRange) {
            input.setSelectionRange(0, input.value.length);
        }
    }, 10);

    // Handle save/cancel
    const saveEdit = async () => {
        const newName = input.value.trim();
        if (newName !== currentName) {
            // Optimistic update
            shoppingList[itemIndex].name = newName;
            renderShoppingList();

            try {
                await apiRequest(API_ITEM_URL(itemId), {
                    method: 'PUT',
                    body: JSON.stringify({
                        name: newName,
                        quantity: item.quantity,
                        completed: item.completed,
                        order_index: item.order_index
                    })
                });
                console.log('Item name updated successfully');
            } catch (error) {
                // Revert on error
                shoppingList[itemIndex].name = currentName;
                renderShoppingList();
                showToast('Failed to update item name', 'error');
                console.error('Update item name error:', error);
            }
        } else {
            renderShoppingList(); // Re-render to restore original display
        }
    };

    const cancelEdit = () => {
        renderShoppingList(); // Re-render to restore original display
    };

    // Handle keyboard events
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveEdit();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelEdit();
        }
    });

    // Handle blur (save on blur, with iOS compatibility)
    input.addEventListener('blur', (e) => {
        // Small delay to allow click events on other elements to fire first
        setTimeout(() => {
            if (document.activeElement !== input) {
                saveEdit();
            }
        }, 150);
    });

    // Prevent item selection when clicking on input
    input.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

/**
 * Handle item selection for insertion
 */
function handleSelectItem(itemId) {
    // Toggle selection: if already selected, deselect; else select
    selectedItemId = (selectedItemId === itemId) ? null : itemId;
    renderShoppingList();
}

/**
 * Drag and Drop Functionality
 */
let draggedItemId = null;
let draggedElement = null;
let touchStartY = 0;
let touchStartX = 0;

/**
 * Handle drag start event
 */
function handleDragStart(event, itemId) {
    draggedItemId = itemId;
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/html', event.target.outerHTML);

    // Add visual feedback
    event.target.closest('.list-item').classList.add('dragging');
}

/**
 * Handle drag over event
 */
function handleDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';

    const target = event.target.closest('.list-item');
    if (!target) return;

    const draggedItem = document.querySelector('.list-item.dragging');
    if (!draggedItem || draggedItem === target) return;

    // Add visual feedback for drop zones
    const rect = target.getBoundingClientRect();
    const midpoint = rect.top + rect.height / 2;

    // Remove previous drop indicators
    document.querySelectorAll('.list-item.drop-above, .list-item.drop-below').forEach(item => {
        item.classList.remove('drop-above', 'drop-below');
    });

    if (event.clientY < midpoint) {
        target.classList.add('drop-above');
    } else {
        target.classList.add('drop-below');
    }
}

/**
 * Handle drop event
 */
async function handleDrop(event) {
    event.preventDefault();

    if (!draggedItemId || !isOnline) {
        if (!isOnline) {
            showToast('Cannot reorder items while offline', 'error');
        }
        return;
    }

    const targetItem = event.target.closest('.list-item');
    if (!targetItem) return;

    const targetItemId = parseInt(targetItem.getAttribute('data-item-id'));
    if (targetItemId === draggedItemId) return;

    const draggedItem = document.querySelector('.list-item.dragging');
    if (!draggedItem) return;

    // Determine new position
    const rect = targetItem.getBoundingClientRect();
    const midpoint = rect.top + rect.height / 2;
    const insertBefore = event.clientY < midpoint;

    // Find target index in current list
    const targetIndex = shoppingList.findIndex(item => item.id === targetItemId);
    const draggedIndex = shoppingList.findIndex(item => item.id === draggedItemId);

    if (targetIndex === -1 || draggedIndex === -1) return;

    // Calculate new order index
    let newOrderIndex;
    if (insertBefore) {
        newOrderIndex = shoppingList[targetIndex].order_index;
    } else {
        newOrderIndex = shoppingList[targetIndex].order_index + 1;
    }

    // Remove dragged item from current position
    const draggedItemData = shoppingList.splice(draggedIndex, 1)[0];

    // Insert at new position
    let insertIndex;
    if (insertBefore) {
        insertIndex = targetIndex;
    } else {
        insertIndex = targetIndex + 1;
    }

    shoppingList.splice(insertIndex, 0, draggedItemData);

    // Update order indices
    shoppingList.forEach((item, index) => {
        item.order_index = index + 1;
    });

    // Render updated list
    renderShoppingList();

    // Clear drag state
    document.querySelectorAll('.list-item.dragging, .list-item.drop-above, .list-item.drop-below').forEach(item => {
        item.classList.remove('dragging', 'drop-above', 'drop-below');
    });

    try {
        // Send reorder request to server
        await apiRequest(`/items/${draggedItemId}/reorder/${newOrderIndex}`, {
            method: 'PATCH'
        });

        console.log('Item reordered successfully');
    } catch (error) {
        // Revert on error
        await loadShoppingList();
        showToast('Failed to reorder item', 'error');
        console.error('Reorder item error:', error);
    }

    draggedItemId = null;
}

/**
 * Handle drag end event
 */
function handleDragEnd(event) {
    // Clear all drag-related classes
    document.querySelectorAll('.list-item.dragging, .list-item.drop-above, .list-item.drop-below').forEach(item => {
        item.classList.remove('dragging', 'drop-above', 'drop-below');
    });

    draggedItemId = null;
}

/**
 * Handle touch start event (for mobile drag)
 */
function handleTouchStart(event, itemId) {
    draggedItemId = itemId;
    draggedElement = event.target.closest('.list-item');

    const touch = event.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;

    // Add visual feedback
    draggedElement.classList.add('dragging');

    // Prevent scrolling while dragging
    event.preventDefault();
}

/**
 * Handle touch move event (for mobile drag)
 */
function handleTouchMove(event) {
    if (!draggedElement || !draggedItemId) return;

    const touch = event.touches[0];
    const deltaX = Math.abs(touch.clientX - touchStartX);
    const deltaY = Math.abs(touch.clientY - touchStartY);

    // Only start dragging if moved enough (prevent accidental drags)
    if (deltaX > 10 || deltaY > 10) {
        // Find the target element under the touch
        const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
        const targetItem = targetElement ? targetElement.closest('.list-item') : null;

        // Remove previous drop indicators
        document.querySelectorAll('.list-item.drop-above, .list-item.drop-below').forEach(item => {
            item.classList.remove('drop-above', 'drop-below');
        });

        if (targetItem && targetItem !== draggedElement) {
            const rect = targetItem.getBoundingClientRect();
            const midpoint = rect.top + rect.height / 2;

            if (touch.clientY < midpoint) {
                targetItem.classList.add('drop-above');
            } else {
                targetItem.classList.add('drop-below');
            }
        }
    }

    // Prevent scrolling
    event.preventDefault();
}

/**
 * Handle touch end event (for mobile drag)
 */
async function handleTouchEnd(event) {
    if (!draggedElement || !draggedItemId) return;

    const touch = event.changedTouches[0];
    const targetElement = document.elementFromPoint(touch.clientX, touch.clientY);
    const targetItem = targetElement ? targetElement.closest('.list-item') : null;

    // Clear visual feedback
    document.querySelectorAll('.list-item.dragging, .list-item.drop-above, .list-item.drop-below').forEach(item => {
        item.classList.remove('dragging', 'drop-above', 'drop-below');
    });

    if (targetItem && targetItem !== draggedElement && isOnline) {
        const targetItemId = parseInt(targetItem.getAttribute('data-item-id'));

        // Determine insert position
        const rect = targetItem.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        const insertBefore = touch.clientY < midpoint;

        // Find indices in current list
        const targetIndex = shoppingList.findIndex(item => item.id === targetItemId);
        const draggedIndex = shoppingList.findIndex(item => item.id === draggedItemId);

        if (targetIndex !== -1 && draggedIndex !== -1) {
            // Calculate new order index
            let newOrderIndex;
            if (insertBefore) {
                newOrderIndex = shoppingList[targetIndex].order_index;
            } else {
                newOrderIndex = shoppingList[targetIndex].order_index + 1;
            }

            // Reorder locally
            const draggedItemData = shoppingList.splice(draggedIndex, 1)[0];
            let insertIndex = insertBefore ? targetIndex : targetIndex + 1;
            shoppingList.splice(insertIndex, 0, draggedItemData);

            // Update order indices
            shoppingList.forEach((item, index) => {
                item.order_index = index + 1;
            });

            // Render updated list
            renderShoppingList();

            try {
                // Send reorder request to server
                await apiRequest(`/items/${draggedItemId}/reorder/${newOrderIndex}`, {
                    method: 'PATCH'
                });

                console.log('Item reordered successfully');
            } catch (error) {
                // Revert on error
                await loadShoppingList();
                showToast('Failed to reorder item', 'error');
                console.error('Reorder item error:', error);
            }
        }
    }

    // Reset drag state
    draggedItemId = null;
    draggedElement = null;
    touchStartX = 0;
    touchStartY = 0;
}

/**
 * Connection Health Monitoring
 */
let lastEventTime = Date.now();
let connectionHealthTimer = null;
let isConnectionHealthy = true;

/**
 * Check and reconnect SSE if needed
 */
function checkAndReconnectSSE() {
    // If we have an active connection, check its health
    if (eventSource) {
        const timeSinceLastEvent = Date.now() - lastEventTime;
        const maxEventAge = 60000; // 1 minute

        // If no events received for a while, force reconnection
        if (timeSinceLastEvent > maxEventAge) {
            console.log('No SSE events received for', timeSinceLastEvent, 'ms, forcing reconnection');
            forceSSEReconnection();
        }
    } else {
        // No active connection, try to connect
        connectToSSE();
    }
}

/**
 * Force SSE reconnection (used for mobile resume scenarios)
 */
function forceSSEReconnection() {
    console.log('Forcing SSE reconnection');

    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    // Clear any pending retry timeouts
    if (sseRetryTimeout) {
        clearTimeout(sseRetryTimeout);
        sseRetryTimeout = null;
    }

    // Reset retry count for forced reconnection
    sseRetryCount = 0;

    // Try immediate reconnection
    setTimeout(() => {
        if (isOnline) {
            connectToSSE();
        }
    }, 500);
}

/**
 * Monitor connection health
 */
function startConnectionHealthMonitoring() {
    // Clear existing timer
    if (connectionHealthTimer) {
        clearInterval(connectionHealthTimer);
    }

    // Check connection health every 30 seconds
    connectionHealthTimer = setInterval(() => {
        if (eventSource && isOnline) {
            const timeSinceLastEvent = Date.now() - lastEventTime;
            const maxEventAge = 60000; // 1 minute

            if (timeSinceLastEvent > maxEventAge) {
                if (isConnectionHealthy) {
                    console.log('SSE connection appears unhealthy, attempting reconnection');
                    isConnectionHealthy = false;
                    forceSSEReconnection();
                }
            } else {
                isConnectionHealthy = true;
            }
        }
    }, 30000); // Check every 30 seconds
}

/**
 * Connect to Server-Sent Events for real-time updates
 */
function connectToSSE() {
    if (!isOnline || eventSource) {
        return;
    }

    try {
        eventSource = new EventSource('/events');

        eventSource.onopen = () => {
            console.log('SSE connection established');
            isRealTimeConnected = true;
            isConnectionHealthy = true;
            updateConnectionStatus();
            startConnectionHealthMonitoring();
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                lastEventTime = Date.now();
                isConnectionHealthy = true;
                handleSSEEvent(data);
            } catch (error) {
                console.error('SSE message parse error:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            isRealTimeConnected = false;
            isConnectionHealthy = false;
            updateConnectionStatus();

            // Close and cleanup
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }

            // Clear any existing retry timeout
            if (sseRetryTimeout) {
                clearTimeout(sseRetryTimeout);
                sseRetryTimeout = null;
            }

            // Implement exponential backoff with max 1 minute
            if (isOnline) {
                sseRetryCount++;
                // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s, then max 60s
                const delay = Math.min(1000 * Math.pow(2, Math.min(sseRetryCount - 1, 6)), 60000);

                console.log(`SSE retry ${sseRetryCount} in ${delay}ms`);

                sseRetryTimeout = setTimeout(() => {
                    if (isOnline) {
                        connectToSSE();
                    }
                }, delay);
            } else {
                // Reset retry count when offline
                sseRetryCount = 0;
            }
        };

    } catch (error) {
        console.error('Failed to create SSE connection:', error);
    }
}

/**
 * Handle Server-Sent Events
 */
function handleSSEEvent(data) {
    // Test flag to simulate offline mode - ignore events when set
    if (window.TEST_OFFLINE_MODE) {
        console.log("TEST: Ignoring SSE event due to offline mode:", data);
        return;
    }

    // Skip ping events
    if (data.type === 'ping') {
        return;
    }

    // Ignore events triggered by this client
    if (data.client_id === clientId) {
        console.log('Ignoring own event:', data);
        return;
    }

    console.log('Received SSE event:', data);

    switch (data.type) {
        case 'item_created':
            handleItemCreated(data);
            break;
        case 'item_updated':
            handleItemUpdated(data);
            break;
        case 'item_deleted':
            handleItemDeleted(data);
            break;
        case 'item_toggled':
            handleItemToggled(data);
            break;
        case 'item_reordered':
            handleItemReordered(data);
            break;
        case 'clear':
            handleListCleared(data);
            break;
        case 'list_update':
            handleListUpdated(data);
            break;
        default:
            console.log('Unknown SSE event type:', data.type);
    }
}

/**
 * Handle item created event with count validation
 */
function handleItemCreated(data) {
    const newItem = data.item;
    const existingIndex = shoppingList.findIndex(item => item.id === newItem.id);

    if (existingIndex === -1) {
        // Step 1: Validate old count
        if (shoppingList.length !== data.old_count) {
            console.warn('Item creation count mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 2: Apply change
        shoppingList.push(newItem);
        renderShoppingList();
        updateEmptyState();

        // Step 3: Validate new count
        if (shoppingList.length !== data.new_count) {
            console.warn('Item creation new count mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 4: Show success message
        showToast('Item added from another device', 'info');
        console.log('New item added via SSE:', newItem);
    }
}

/**
 * Handle item updated event
 */
function handleItemUpdated(data) {
    const updatedItem = data.item;
    const itemIndex = shoppingList.findIndex(item => item.id === updatedItem.id);

    if (itemIndex !== -1) {
        // Update existing item
        shoppingList[itemIndex] = updatedItem;
        renderShoppingList();
        showToast('Item updated from another device', 'info');
    }
}

/**
 * Handle item deleted event with count validation
 */
function handleItemDeleted(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Step 1: Validate old count
        if (shoppingList.length !== data.old_count) {
            console.warn('Item deletion count mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 2: Apply change
        shoppingList.splice(itemIndex, 1);
        renderShoppingList();
        updateEmptyState();

        // Step 3: Validate new count
        if (shoppingList.length !== data.new_count) {
            console.warn('Item deletion new count mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 4: Show success message
        showToast('Item deleted from another device', 'info');
    }
}

/**
 * Handle item toggled event with state validation
 */
function handleItemToggled(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Step 1: Validate old state
        if (shoppingList[itemIndex].completed !== data.old_state) {
            console.warn('Item toggle state mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 2: Apply change
        shoppingList[itemIndex].completed = data.new_state;
        renderShoppingList();

        // Step 3: Validate new state
        if (shoppingList[itemIndex].completed !== data.new_state) {
            console.warn('Item toggle new state mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 4: Show success message
        showToast('Item status changed from another device', 'info');
    }
}

/**
 * Handle item reordered event with state validation
 */
function handleItemReordered(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Step 1: Validate old state
        if (shoppingList[itemIndex].order_index !== data.old_state) {
            console.warn('Item reorder state mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 2: Apply change
        const item = shoppingList.splice(itemIndex, 1)[0];

        // Find new position based on order_index
        let newIndex = shoppingList.findIndex(i => i.order_index >= data.new_state);
        if (newIndex === -1) {
            newIndex = shoppingList.length;
        }

        shoppingList.splice(newIndex, 0, item);

        // Update order indices locally
        shoppingList.forEach((item, index) => {
            item.order_index = index + 1;
        });

        renderShoppingList();

        // Step 3: Validate new state
        const finalItemIndex = shoppingList.findIndex(item => item.id === data.item_id);
        if (finalItemIndex !== -1 && shoppingList[finalItemIndex].order_index !== data.new_state) {
            console.warn('Item reorder new state mismatch, refreshing...');
            loadShoppingList();
            return;
        }

        // Step 4: Show success message
        showToast('Item reordered from another device', 'info');
    }
}

/**
 * Handle list cleared event
 */
function handleListCleared(data) {
    if (data.list_id === currentList.id) {
        shoppingList = [];
        renderShoppingList();
        updateEmptyState();
        showToast('List cleared from another device', 'info');
    }
}

/**
 * Handle list updated event
 */
function handleListUpdated(data) {
    if (data.list_id === currentList.id) {
        currentList.name = data.name;
        updateListTitle();
        showToast('List name updated from another device', 'info');
    }
}

/**
 * Setup SSE connection with delayed initialization and smart retry logic
 */
function setupSSE() {
    // Delay SSE connection until page fully loads to improve initial performance
    window.addEventListener('load', () => {
        setTimeout(() => {
            if (isOnline) {
                connectToSSE();
            }
        }, 500); // Small additional delay after page load
    });
}

/**
 * Setup hourly refresh timer
 */
function setupHourlyRefresh() {
    // Clear existing timer if any
    if (hourlyRefreshTimer) {
        clearInterval(hourlyRefreshTimer);
    }

    // Set up hourly refresh (3600000 ms = 1 hour)
    hourlyRefreshTimer = setInterval(() => {
        if (isOnline && !isLoading) {
            console.log('Performing hourly refresh');
            loadShoppingList();
            loadListInfo();
            showToast('Hourly refresh completed', 'info');
        }
    }, 3600000);

    console.log('Hourly refresh timer set up');
}

/**
 * iOS Reconnection and Refresh Coordination
 * Handles debounced refresh after ensuring connection is healthy
 */

let refreshDebounceTimer = null;
let connectionCheckTimer = null;

/**
 * Handle visibility change with connection coordination
 */
function handleVisibilityChange() {
    // Debounce multiple rapid events (visibilitychange + focus + resume)
    if (refreshDebounceTimer) {
        clearTimeout(refreshDebounceTimer);
    }

    refreshDebounceTimer = setTimeout(() => {
        console.log('Visibility change debounce complete - checking connection and refreshing');
        coordinateConnectionAndRefresh('visibility');
    }, 500); // 500ms debounce
}

/**
 * Handle focus change with connection coordination
 */
function handleFocusChange() {
    // Debounce multiple rapid events
    if (refreshDebounceTimer) {
        clearTimeout(refreshDebounceTimer);
    }

    refreshDebounceTimer = setTimeout(() => {
        console.log('Focus change debounce complete - checking connection and refreshing');
        coordinateConnectionAndRefresh('focus');
    }, 300); // 300ms debounce for focus
}

/**
 * Handle mobile resume with connection coordination
 */
function handleMobileResume() {
    // Mobile resume needs immediate attention but still debounce
    if (refreshDebounceTimer) {
        clearTimeout(refreshDebounceTimer);
    }

    refreshDebounceTimer = setTimeout(() => {
        console.log('Mobile resume debounce complete - forcing connection check and refresh');
        // Mobile devices often need explicit reconnection after resume
        forceSSEReconnection();
        // Wait a bit for connection to establish, then refresh
        setTimeout(() => {
            coordinateConnectionAndRefresh('mobile_resume');
        }, 1000);
    }, 200); // 200ms debounce for mobile resume
}

/**
 * Handle pageshow event with connection coordination
 */
function handlePageShow(event) {
    // Debounce pageshow events
    if (refreshDebounceTimer) {
        clearTimeout(refreshDebounceTimer);
    }

    refreshDebounceTimer = setTimeout(() => {
        console.log('Page show debounce complete - checking connection and refreshing');
        coordinateConnectionAndRefresh('pageshow');
    }, 400); // 400ms debounce for pageshow
}

/**
 * Coordinate connection check and data refresh
 */
async function coordinateConnectionAndRefresh(source) {
    console.log(`Coordinating connection and refresh from ${source}`);

    // First, ensure we have a healthy connection
    await ensureHealthyConnection();

    // Then refresh data if connection is healthy
    if (isConnectionHealthy && isOnline && !isLoading) {
        console.log(`Connection healthy after ${source} - refreshing data`);
        try {
            await loadShoppingList();
            await loadListInfo();
            console.log(`Data refreshed after ${source}`);
        } catch (error) {
            console.error(`Refresh failed after ${source}:`, error);
            showToast('Failed to refresh data after reconnection', 'error');
        }
    } else {
        console.log(`Connection not ready after ${source}, will retry in 2 seconds`);
        // Retry in 2 seconds if connection isn't ready yet
        if (connectionCheckTimer) {
            clearTimeout(connectionCheckTimer);
        }

        connectionCheckTimer = setTimeout(() => {
            coordinateConnectionAndRefresh(source);
        }, 2000);
    }
}

/**
 * Ensure we have a healthy SSE connection
 */
async function ensureHealthyConnection() {
    console.log('Ensuring healthy connection...');

    // If we're offline, don't show any toast and let the existing backoff logic handle it
    if (!isOnline) {
        console.log('Device is offline, letting existing backoff logic handle reconnection');
        return;
    }

    // If we have no connection, try to connect
    if (!eventSource) {
        console.log('No SSE connection, attempting to connect');
        connectToSSE();
    }

    // Wait for connection to be established and healthy
    let attempts = 0;
    const maxAttempts = 30; // Wait up to 30 seconds (30 * 100ms)

    while (attempts < maxAttempts) {
        if (isConnectionHealthy && isRealTimeConnected) {
            console.log('Connection is healthy');
            return;
        }

        // If connection is unhealthy, force reconnection
        if (eventSource && !isConnectionHealthy) {
            console.log('Connection unhealthy, forcing reconnection');
            forceSSEReconnection();
        }

        await new Promise(resolve => setTimeout(resolve, 100)); // Wait 100ms
        attempts++;
    }

    // Only show timeout toast if we were previously connected (unexpected disconnection)
    // Don't show it if we were never connected or if we're offline
    if (isRealTimeConnected) {
        console.log('Timed out waiting for healthy connection after unexpected disconnection');
        showToast('Connection taking longer than expected', 'warning');
    } else {
        console.log('Timed out waiting for initial connection, letting backoff logic handle it');
    }
}

/**
 * Cleanup function for page unload
 */
function cleanup() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    if (hourlyRefreshTimer) {
        clearInterval(hourlyRefreshTimer);
        hourlyRefreshTimer = null;
    }

    if (connectionHealthTimer) {
        clearInterval(connectionHealthTimer);
        connectionHealthTimer = null;
    }

    // Clear debouncing timers
    if (refreshDebounceTimer) {
        clearTimeout(refreshDebounceTimer);
        refreshDebounceTimer = null;
    }

    if (connectionCheckTimer) {
        clearTimeout(connectionCheckTimer);
        connectionCheckTimer = null;
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', cleanup);

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
window.handleDragStart = handleDragStart;
window.handleDragOver = handleDragOver;
window.handleDrop = handleDrop;
window.handleDragEnd = handleDragEnd;
window.handleTouchStart = handleTouchStart;
window.handleTouchMove = handleTouchMove;
window.handleTouchEnd = handleTouchEnd;
window.startItemNameEdit = startItemNameEdit;

// Expose for testing
window.app = {
    loadShoppingList,
    handleAddItem,
    handleToggleItem,
    handleDeleteItem,
    handleClearAll,
    handleRefresh,
    handleExport,
    handleImport,
    parseImportText,
    showToast,
    setLoading
};

// Expose global variables for testing
window.isConnectionHealthy = isConnectionHealthy;
window.sseRetryCount = sseRetryCount;
