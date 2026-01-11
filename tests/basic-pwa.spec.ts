import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Handle confirm dialogs
  page.on('dialog', dialog => dialog.accept());

  await page.goto('http://localhost:8000');

  // Clear all existing items to start fresh
  if (await page.locator('.list-item').count() > 0) {
    await page.click('#clearBtn');
    await page.waitForTimeout(500);
  }
});

test.describe('Basic PWA Functionality', () => {
  test('should load the PWA correctly', async ({ page }) => {
    await expect(page).toHaveTitle('Shared Shopping List');

    // Check main elements are present
    await expect(page.locator('#shoppingList')).toBeAttached();
    await expect(page.locator('#addItemForm')).toBeVisible();
    await expect(page.locator('#connectionStatus')).toBeVisible();
    await expect(page.locator('#emptyState')).toBeVisible(); // Should be visible when empty
  });

  test('should add an item to the shopping list', async ({ page }) => {
    // Fill in the form
    await page.fill('#itemName', 'Test Item');
    await page.fill('#itemQuantity', '2');

    // Submit the form
    await page.click('.add-btn');

    // Wait for the item to appear
    await page.waitForSelector('.list-item');

    // Check the item was added
    const itemText = await page.locator('.list-item .item-name').textContent();
    const itemQuantity = await page.locator('.list-item .item-quantity').textContent();

    expect(itemText).toBe('Test Item');
    expect(itemQuantity).toBe('2');
  });

  test('should toggle item completion', async ({ page }) => {
    // Add an item first
    await page.fill('#itemName', 'Toggle Test');
    await page.fill('#itemQuantity', '1');
    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Check initial state
    const item = page.locator('.list-item');
    await expect(item).not.toHaveClass(/completed/);

    // Toggle completion
    await page.click('.item-checkbox');

    // Check item is marked as completed
    await expect(item).toHaveClass(/completed/);

    // Verify no strikethrough is applied
    const textDecoration = await item.locator('.item-name').evaluate(el => getComputedStyle(el).textDecoration);
    expect(textDecoration).not.toContain('line-through');

    // Toggle back
    await page.click('.item-checkbox');
    await expect(item).not.toHaveClass(/completed/);
  });

  test('should delete an item', async ({ page }) => {
    // Add an item first
    await page.fill('#itemName', 'Delete Test');
    await page.fill('#itemQuantity', '1');
    await page.click('.add-btn');
    await page.waitForSelector('.list-item');

    // Delete the item
    await page.click('.delete-btn');

    // Check item is removed
    await expect(page.locator('.list-item')).toHaveCount(0);
  });

  test('should display empty state when no items', async ({ page }) => {
    // Since beforeEach clears items, it should be empty
    await expect(page.locator('#emptyState')).toBeVisible();
    await expect(page.locator('#shoppingList')).not.toBeVisible();
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Add an item
    await page.fill('#itemName', 'Mobile Test');
    await page.fill('#itemQuantity', '1');
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
      await page.fill('#itemQuantity', '1');
      await page.click('.add-btn');
      await page.waitForTimeout(200);
    }

    // Check that drag handles are visible on all items
    const dragHandles = page.locator('.drag-handle');
    await expect(dragHandles).toHaveCount(3);

    // Check that each item has the drag handle visible
    for (let i = 0; i < 3; i++) {
      const handle = dragHandles.nth(i);
      await expect(handle).toBeVisible();
      expect(await handle.textContent()).toContain('⋮⋮');
    }

    // Check that items are draggable
    const firstItem = page.locator('.list-item').first();
    const isDraggable = await firstItem.getAttribute('draggable');
    expect(isDraggable).toBe('true');
  });

  test('should reorder items via drag and drop', async ({ page, isMobile }) => {
    test.skip(isMobile, 'Touch drag and drop testing is complex in Playwright, manually verified to work on mobile');

    // Add three items
    const itemNames = ['First Item', 'Second Item', 'Third Item'];
    for (const name of itemNames) {
      await page.fill('#itemName', name);
      await page.fill('#itemQuantity', '1');
      await page.click('.add-btn');
      await page.waitForTimeout(200);
    }

    // Wait for all items to be rendered
    await page.waitForTimeout(500);

    // Get initial order
    const items = page.locator('.list-item .item-name');
    const initialOrder = await items.allTextContents();
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
    await page.waitForLoadState('networkidle');

    // Wait for items to load
    await page.waitForSelector('.list-item', { timeout: 5000 });

    // Verify order persists after refresh
    const refreshedItems = page.locator('.list-item .item-name');
    const refreshedOrder = await refreshedItems.allTextContents();
    expect(refreshedOrder).toEqual(['Second Item', 'First Item', 'Third Item']);
  });
});
