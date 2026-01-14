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

// DOM Elements
const elements = {
    shoppingList: document.getElementById('shoppingList'),
    emptyState: document.getElementById('emptyState'),
    addItemForm: document.getElementById('addItemForm'),
    itemNameInput: document.getElementById('itemName'),
    itemQuantityInput: document.getElementById('itemQuantity'),
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

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeClientId();
    initializeEventListeners();
    loadListInfo();
    loadShoppingList();
    updateConnectionStatus();
    connectToSSE();
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
    elements.addItemForm.addEventListener('submit', handleAddItem);

    // Button actions
    elements.clearBtn.addEventListener('click', handleClearAll);
    elements.refreshBtn.addEventListener('click', handleRefresh);
    elements.exportBtn.addEventListener('click', handleExport);
    elements.importBtn.addEventListener('click', handleImport);

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
    });

    window.addEventListener('offline', () => {
        isOnline = false;
        updateConnectionStatus();
        showToast('You are now offline. Changes will sync when connection is restored.', 'warning');
    });

    // Input validation
    elements.itemNameInput.addEventListener('input', validateForm);
    elements.itemQuantityInput.addEventListener('input', validateForm);

    // Import modal event listeners
    elements.importModalClose.addEventListener('click', closeImportModal);
    elements.importCancel.addEventListener('click', closeImportModal);
    elements.importConfirm.addEventListener('click', handleImportConfirm);

    // Close modal when clicking outside
    elements.importModal.addEventListener('click', (e) => {
        if (e.target === elements.importModal) {
            closeImportModal();
        }
    });

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
                showToast('List name updated successfully', 'success');
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

    if (quantity <= 0) {
        showToast('Please enter a valid quantity', 'error');
        return;
    }

    // Allow empty names for visual spacers
    name = name.trim();

    setLoading(true);

    try {
        const payload = {
            name: name,
            quantity: quantity,
            completed: false
        };

        // If an item is selected, insert above it
        if (selectedItemId !== null) {
            const selectedItem = shoppingList.find(item => item.id === selectedItemId);
            if (selectedItem) {
                payload.order_index = selectedItem.order_index;
            }
        }

        const newItem = await apiRequest(API_BASE_URL, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

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

        // Clear selection
        selectedItemId = null;

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
            showToast('List shared successfully', 'success');
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

        showToast('List logged to console - copy manually', 'info');
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
            <div class="drag-handle" draggable="true" ondragstart="handleDragStart(event, ${item.id})" ontouchstart="handleTouchStart(event, ${item.id})" ontouchmove="handleTouchMove(event)" ontouchend="handleTouchEnd(event)" title="Drag to reorder">
                ⋮⋮
            </div>

            <button class="item-checkbox ${item.completed ? 'checked' : ''}"
                    onclick="handleToggleItem(${item.id})"
                    aria-label="${item.completed ? 'Mark as incomplete' : 'Mark as complete'}">
            </button>

            <div class="item-content">
                <span class="item-name ${!item.name ? 'empty-spacer' : ''}">${item.name ? escapeHtml(item.name) : '—'}</span>
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
    const name = elements.itemNameInput.value.trim();
    const quantity = parseInt(elements.itemQuantityInput.value, 10);

    // Allow empty names for visual spacers, just require valid quantity
    const isValid = quantity > 0;
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
        selectedItemId = null;
        renderShoppingList();
        document.activeElement.blur();
    }
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

        showToast('Item reordered successfully', 'success');
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

                showToast('Item reordered successfully', 'success');
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
            updateConnectionStatus();
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleSSEEvent(data);
            } catch (error) {
                console.error('SSE message parse error:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            isRealTimeConnected = false;
            updateConnectionStatus();

            // Close and cleanup
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }

            // Try to reconnect after a delay
            setTimeout(() => {
                if (isOnline) {
                    connectToSSE();
                }
            }, 5000);
        };

    } catch (error) {
        console.error('Failed to create SSE connection:', error);
    }
}

/**
 * Handle Server-Sent Events
 */
function handleSSEEvent(data) {
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
 * Handle item created event
 */
function handleItemCreated(data) {
    const newItem = data.item;
    const existingIndex = shoppingList.findIndex(item => item.id === newItem.id);

    if (existingIndex === -1) {
        // Add new item to the list
        shoppingList.push(newItem);
        renderShoppingList();
        updateEmptyState();
        showToast('Item added from another device', 'info');
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
 * Handle item deleted event
 */
function handleItemDeleted(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Remove item from the list
        shoppingList.splice(itemIndex, 1);
        renderShoppingList();
        updateEmptyState();
        showToast('Item deleted from another device', 'info');
    }
}

/**
 * Handle item toggled event
 */
function handleItemToggled(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Update completion status
        shoppingList[itemIndex].completed = data.completed;
        renderShoppingList();
        showToast('Item status changed from another device', 'info');
    }
}

/**
 * Handle item reordered event
 */
function handleItemReordered(data) {
    const itemIndex = shoppingList.findIndex(item => item.id === data.item_id);

    if (itemIndex !== -1) {
        // Reorder the item in the local list
        const item = shoppingList.splice(itemIndex, 1)[0];

        // Find new position based on order_index
        let newIndex = shoppingList.findIndex(i => i.order_index >= data.new_order);
        if (newIndex === -1) {
            newIndex = shoppingList.length;
        }

        shoppingList.splice(newIndex, 0, item);

        // Update order indices locally
        shoppingList.forEach((item, index) => {
            item.order_index = index + 1;
        });

        renderShoppingList();
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
