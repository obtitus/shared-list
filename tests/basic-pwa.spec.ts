import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Handle confirm dialogs
  page.on('dialog', dialog => dialog.accept());

  await page.goto('http://localhost:8000');

  // Reset list name to default
  await page.evaluate(async () => {
    try {
      const response = await fetch('/lists/1', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Shopping List' })
      });
      if (response.ok) {
        document.title = 'Shopping List - Shared Shopping List';
        const titleEl = document.querySelector('.list-title');
        if (titleEl) titleEl.textContent = 'Shopping List';
      }
    } catch (e) {
      // Ignore errors during reset
    }
  });

  // Clear all existing items to start fresh
  if (await page.locator('.list-item').count() > 0) {
    await page.click('#clearBtn');
    await page.waitForTimeout(500);
  }
});

test.afterEach(async ({ page }) => {
  // Clean up SSE connections to prevent hanging
  await page.evaluate(() => {
    // Close any EventSource connections
    const win = window as any;
    if (win.eventSource) {
      win.eventSource.close();
      win.eventSource = null;
    }

    // Clear any pending timeouts
    if (win.hourlyRefreshTimer) {
      clearInterval(win.hourlyRefreshTimer);
      win.hourlyRefreshTimer = null;
    }
  });
});

test.describe('Basic PWA Functionality', () => {
  test('should load the PWA correctly', async ({ page }) => {
    await expect(page).toHaveTitle('Shopping List - Shared Shopping List');

    // Check main elements are present
    await expect(page.locator('#shoppingList')).toBeAttached();
    await expect(page.locator('#addItemForm')).toBeVisible();
    await expect(page.locator('#connectionStatus')).toBeVisible();
    await expect(page.locator('#emptyState')).toBeVisible(); // Should be visible when empty
  });

  test('should add an item to the shopping list', async ({ page }) => {
    // Fill in the form
    await page.fill('#itemName', 'Test Item');


    // Submit the form
    await page.click('.add-btn');

    // Wait for the item to appear
    await page.waitForSelector('.list-item');

    // Check the item was added (use first to avoid SSE duplicates)
    const itemText = await page.locator('.list-item .item-name').first().textContent();

    expect(itemText).toBe('Test Item');
  });

  test('should toggle item completion', async ({ page }) => {
    // Add an item first
    await page.fill('#itemName', 'Toggle Test');

    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Check initial state (use nth(0) to avoid SSE duplicates)
    const item = page.locator('.list-item').nth(0);
    const initialClass = await item.getAttribute('class') || '';
    expect(initialClass).not.toContain('completed');

    // Toggle completion
    await item.locator('.item-checkbox').click();

    // Wait for state change
    await page.waitForTimeout(500);

    // Check item is marked as completed (re-locate after toggle)
    const itemAfterToggle = page.locator('.list-item').nth(0);
    const toggleClass = await itemAfterToggle.getAttribute('class') || '';
    expect(toggleClass).toContain('completed');

    // Toggle back
    await itemAfterToggle.locator('.item-checkbox').click();

    // Wait for state change
    await page.waitForTimeout(500);

    // Check item is not completed again
    const itemAfterToggleBack = page.locator('.list-item').nth(0);
    const finalClass = await itemAfterToggleBack.getAttribute('class') || '';
    expect(finalClass).not.toContain('completed');
  });

  test('should delete an item', async ({ page }) => {
    // Add an item first
    await page.fill('#itemName', 'Delete Test');

    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Delete the item
    await page.click('.delete-btn');

    // Check item is removed
    await expect(page.locator('.list-item')).toHaveCount(0);
  });

  test('should edit item names', async ({ page }) => {
    // Add an item first
    await page.fill('#itemName', 'Original Name');

    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Check initial name
    const itemName = page.locator('.list-item .item-name');
    await expect(itemName).toHaveText('Original Name');

    // Check that the edit button exists and is visible
    const editBtn = page.locator('.edit-btn');
    await expect(editBtn).toBeVisible();
    console.log('Edit button found and visible');

    // Click the edit button
    await editBtn.click();
    console.log('Edit button clicked');

    // Check that an input field appears
    const inputField = page.locator('.item-name-input');
    await expect(inputField).toBeVisible();

    // Change the name
    await inputField.fill('Edited Name');
    await inputField.press('Enter');

    // Check that the name is updated
    await expect(itemName).toHaveText('Edited Name');
  });

  test('should display empty state when no items', async ({ page }) => {
    // Since beforeEach clears items, it should be empty
    await expect(page.locator('#emptyState')).toBeVisible();
    await expect(page.locator('#shoppingList')).not.toBeVisible();
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Add an item
    await page.fill('#itemName', 'Mobile Test');

    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Check that form inputs are appropriately sized for touch
    const nameInput = page.locator('#itemName');
    const height = await nameInput.evaluate(el => (el as HTMLElement).offsetHeight);
    expect(height).toBeGreaterThanOrEqual(40); // Minimum touch target size
  });

  test('should display drag handles on items', async ({ page }) => {
    // Add multiple items
    for (let i = 1; i <= 3; i++) {
      await page.fill('#itemName', `Drag Test Item ${i}`);

      await page.click('.add-btn');
      await page.waitForSelector('#loadingOverlay', { state: 'hidden' });
      await page.waitForTimeout(200);
    }

    // Check that drag handles are visible on all items (use first 3 to avoid SSE duplicates)
    for (let i = 0; i < 3; i++) {
      const handle = page.locator('.list-item').nth(i).locator('.drag-handle');
      await expect(handle).toBeVisible();
      expect(await handle.textContent()).toContain('⋮⋮');
    }

    // Check that items are draggable
    const firstItem = page.locator('.list-item').first();
    const isDraggable = await firstItem.getAttribute('draggable');
    expect(isDraggable).toBe('true');
  });

  test('should allow editing the list name', async ({ page }) => {
    // Get current list title (whatever it may be)
    const listTitle = page.locator('.list-title');
    const originalTitle = await listTitle.textContent();

    // Click on the list title to start editing
    await listTitle.click();

    // Check that an input field appears
    const inputField = page.locator('input.list-title-input');
    await expect(inputField).toBeVisible();

    // Get the current value in the input
    const currentValue = await inputField.inputValue();

    // Change the list name to something different
    const newTitle = currentValue === 'Test List' ? 'My Custom List' : 'Test List';
    await inputField.fill(newTitle);
    await inputField.press('Enter');

    // Check that the title is updated
    await expect(listTitle).toHaveText(newTitle);

    // Check that the page title is also updated
    await expect(page).toHaveTitle(`${newTitle} - Shared Shopping List`);

    // Refresh the page and check persistence
    await page.reload();
    await page.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });

    // Check that the list name persists after refresh
    await expect(page.locator('.list-title')).toHaveText(newTitle);
    await expect(page).toHaveTitle(`${newTitle} - Shared Shopping List`);
  });

  test('should reorder items via drag and drop', async ({ page, isMobile }) => {
    test.skip(isMobile, 'Touch drag and drop testing is complex in Playwright, manually verified to work on mobile');

    // Add three items
    const itemNames = ['First Item', 'Second Item', 'Third Item'];
    for (const name of itemNames) {
      await page.fill('#itemName', name);

      await page.click('.add-btn');
      await page.waitForTimeout(200);
    }

    // Wait for all items to be rendered
    await page.waitForTimeout(500);

    // Get initial order (use nth to get specific items and avoid SSE duplicates)
    const initialOrder = [];
    for (let i = 0; i < 3; i++) {
      const itemName = await page.locator('.list-item').nth(i).locator('.item-name').textContent();
      initialOrder.push(itemName);
    }
    expect(initialOrder).toEqual(itemNames);

    // Use mouse events for desktop
    const secondItemDragHandle = page.locator('.list-item').nth(1).locator('.drag-handle');
    const firstItem = page.locator('.list-item').nth(0);

    const dragHandleBox = await secondItemDragHandle.boundingBox();
    const firstItemBox = await firstItem.boundingBox();

    if (dragHandleBox && firstItemBox) {
      await page.mouse.move(
        dragHandleBox.x + dragHandleBox.width / 2,
        dragHandleBox.y + dragHandleBox.height / 2
      );
      await page.mouse.down();

      await page.mouse.move(
        firstItemBox.x + firstItemBox.width / 2,
        firstItemBox.y + firstItemBox.height / 4
      );

      await page.mouse.up();
    }

    // Wait for reorder to complete
    await page.waitForTimeout(1000);

    // Verify new order: Second item should now be first
    const newItems = page.locator('.list-item .item-name');
    const newOrder = await newItems.allTextContents();
    expect(newOrder).toEqual(['Second Item', 'First Item', 'Third Item']);

    // Test persistence: Refresh the page
    await page.reload();
    await page.waitForSelector('#shoppingList', { timeout: 10000 });

    // Wait for items to load
    await page.waitForSelector('.list-item', { timeout: 5000 });

    // Verify order persists after refresh
    const refreshedItems = page.locator('.list-item .item-name');
    const refreshedOrder = await refreshedItems.allTextContents();
    expect(refreshedOrder).toEqual(['Second Item', 'First Item', 'Third Item']);
  });

  test('should generate unique client IDs for different browser contexts', async ({ browser }) => {
    // Create two separate browser contexts (simulating different browser windows)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    // Navigate both pages to the app
    await page1.goto('http://localhost:8000');
    await page2.goto('http://localhost:8000');

    // Wait for both pages to initialize
    await page1.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });
    await page2.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });

    // Get client IDs from both pages
    const clientId1 = await page1.evaluate(() => (window as any).clientId);
    const clientId2 = await page2.evaluate(() => (window as any).clientId);

    // Client IDs should be defined and different
    expect(clientId1).toBeDefined();
    expect(clientId2).toBeDefined();
    expect(clientId1).not.toBe(clientId2);

    // Clean up
    await context1.close();
    await context2.close();
  });

  test('should demonstrate localStorage sharing issue within same browser context', async ({ browser }) => {
    // Create one browser context and two pages (simulating different tabs in same browser window)
    const context = await browser.newContext();

    const page1 = await context.newPage();
    const page2 = await context.newPage();

    // Navigate both pages to the app
    await page1.goto('http://localhost:8000');
    await page2.goto('http://localhost:8000');

    // Wait for both pages to initialize
    await page1.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });
    await page2.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });

    // Get client IDs from both pages
    const clientId1 = await page1.evaluate(() => (window as any).clientId);
    const clientId2 = await page2.evaluate(() => (window as any).clientId);

    // This test demonstrates the previous bug: same browser context shares localStorage
    // Both pages will have the same client ID, which breaks SSE filtering
    console.log('Page 1 client ID:', clientId1);
    console.log('Page 2 client ID:', clientId2);

    // This assertion will FAIL, demonstrating the old bug
    expect(clientId1).toBeDefined();
    expect(clientId2).toBeDefined();
    expect(clientId1).not.toBe(clientId2); // This should fail with previous implementation

    // Clean up
    await context.close();
  });
});
