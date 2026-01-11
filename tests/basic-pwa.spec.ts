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
});
