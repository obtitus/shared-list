import { test, expect, type TestInfo } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Handle confirm dialogs
  page.on('dialog', dialog => dialog.accept());

  await page.goto('/');

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

    // Click the edit button
    await editBtn.click();

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

  test('should render items in correct order based on order_index', async ({ page }) => {
    // Clear all items first
    await page.click('#clearBtn');
    await page.waitForTimeout(1000);

    // Add items in reverse order to create order_index mismatch
    // This will create items with order_index: 1, 2, 3 but added in reverse sequence
    await page.fill('#itemName', 'Third Item');
    await page.click('.add-btn');
    await page.waitForTimeout(1000);

    await page.fill('#itemName', 'Second Item');
    await page.click('.add-btn');
    await page.waitForTimeout(1000);

    await page.fill('#itemName', 'First Item');
    await page.click('.add-btn');
    await page.waitForTimeout(1000);

    // Verify items were added (should be 3 items total)
    const itemCount = await page.locator('.list-item').count();
    expect(itemCount).toBe(3);

    // Get the order_index values from the DOM attributes
    const orderIndices = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        return orderIndex ? parseInt(orderIndex) : 0;
      });
    });

    // Get the item names in DOM order
    const itemNames = await page.locator('.list-item .item-name').evaluateAll((items) => {
      return items.map(item => {
        const text = item.textContent;
        return text ? text.trim() : '';
      });
    });

    console.log('Order indices from DOM:', orderIndices);
    console.log('Item names in DOM order:', itemNames);

    // The renderShoppingList function doesn't sort by order_index, causing items to appear in wrong order
    expect(orderIndices).toEqual([1, 2, 3]);
    expect(itemNames).toEqual(['Third Item', 'Second Item', 'First Item']);
  });

  test('should maintain order after manual array manipulation order_index', async ({ page }) => {
    // Clear all items first
    await page.click('#clearBtn');
    await page.waitForTimeout(1000);

    // Add three items
    const itemNames = ['Item A', 'Item B', 'Item C'];
    for (const name of itemNames) {
      await page.fill('#itemName', name);
      await page.click('.add-btn');
      await page.waitForTimeout(1000);
    }

    // Get initial order
    const initialOrderIndices = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        return orderIndex ? parseInt(orderIndex) : 0;
      });
    });
    console.log('Initial order indices:', initialOrderIndices);

    // Manually manipulate the shoppingList array to simulate the bug scenario
    // This simulates what happens when items are added/updated in different order than order_index
    await page.evaluate(() => {
      // Simulate the bug: items in array are not sorted by order_index
      // This happens when items are added/updated in different sequences
      const items = (window as any).shoppingList;

      // Create a scenario where array order doesn't match order_index
      if (items && items.length >= 3) {
        // Swap first and last items in the array (simulating the bug)
        const temp = items[0];
        items[0] = items[2];
        items[2] = temp;

        console.log('Array after manual manipulation:', items.map((i: any) => ({ id: i.id, order_index: i.order_index, name: i.name })));
      }
    });

    // Force re-render by calling the function directly
    await page.evaluate(() => {
      (window as any).renderShoppingList();
    });

    // Wait for DOM to update
    await page.waitForTimeout(500);

    // Check if renderShoppingList() respects order_index or array order
    const finalOrderIndices = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        return orderIndex ? parseInt(orderIndex) : 0;
      });
    });

    console.log('Final order indices after render:', finalOrderIndices);

    // renderShoppingList() should render items in order_index order, not array order
    // After re-render, items should maintain their order_index sequence [1, 2, 3]
    expect(finalOrderIndices).toEqual([1, 2, 3]);
  });

  test('should handle item reordering correctly with full list updates', async ({ page }) => {
    // Clear all items first
    await page.click('#clearBtn');
    await page.waitForTimeout(1000);

    // Add three items
    const itemNames = ['First Item', 'Second Item', 'Third Item'];
    for (const name of itemNames) {
      await page.fill('#itemName', name);
      await page.click('.add-btn');
      await page.waitForTimeout(1000);
    }

    // Get initial order indices from DOM
    const initialOrderIndices = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        return orderIndex ? parseInt(orderIndex) : 0;
      });
    });
    console.log('Initial order indices:', initialOrderIndices);

    // Simulate a reorder event from the server with full list data
    // This simulates what happens when the server sends an SSE event for a reorder
    await page.evaluate(() => {
      // Simulate an item reorder event from the server with full list
      const reorderData = {
        type: 'item_reordered',
        item_id: 2, // ID of Second Item
        old_state: 2, // Current order_index
        new_state: 1, // New order_index
        list_id: 1,
        client_id: 'other-client',
        timestamp: new Date().toISOString(),
        items: [
          { id: 2, name: 'Second Item', quantity: 1, completed: false, order_index: 1 },
          { id: 1, name: 'First Item', quantity: 1, completed: false, order_index: 2 },
          { id: 3, name: 'Third Item', quantity: 1, completed: false, order_index: 3 }
        ]
      };

      console.log('Simulating reorder event with full list:', reorderData);
      (window as any).handleSSEEvent(reorderData);
    });

    // Wait for the reorder to complete
    await page.waitForTimeout(1000);

    // Check the final order
    const finalOrderIndices = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        return orderIndex ? parseInt(orderIndex) : 0;
      });
    });

    const finalItemNames = await page.locator('.list-item .item-name').evaluateAll((items) => {
      return items.map(item => item.textContent?.trim() || '');
    });

    console.log('Final order indices:', finalOrderIndices);
    console.log('Final item names:', finalItemNames);

    // Verify the reorder worked correctly
    // Expected: Second Item should be first (order_index 1), First Item should be second (order_index 2)
    expect(finalItemNames).toEqual(['Second Item', 'First Item', 'Third Item']);
    expect(finalOrderIndices).toEqual([1, 2, 3]);

    // Verify that the local shoppingList array is updated with the full list
    const shoppingListArray = await page.evaluate(() => {
      return (window as any).shoppingList.map((item: any) => ({
        id: item.id,
        name: item.name,
        order_index: item.order_index
      }));
    });

    console.log('Local shoppingList array after reorder:', shoppingListArray);

    // The local array should match the expected order
    expect(shoppingListArray).toEqual([
      { id: 2, name: 'Second Item', order_index: 1 },
      { id: 1, name: 'First Item', order_index: 2 },
      { id: 3, name: 'Third Item', order_index: 3 }
    ]);
  });

  test('should test real-time synchronization during concurrent reorders order_index', async ({ page }) => {
    // Clear all items first
    await page.click('#clearBtn');
    await page.waitForTimeout(1000);

    // Add multiple items
    const itemNames = ['Item 1', 'Item 2', 'Item 3', 'Item 4', 'Item 5'];
    for (const name of itemNames) {
      await page.fill('#itemName', name);
      await page.click('.add-btn');
      await page.waitForTimeout(500);
    }

    // Get initial state
    const initialState = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        const name = item.querySelector('.item-name')?.textContent?.trim() || '';
        return { name, order_index: orderIndex ? parseInt(orderIndex) : 0 };
      });
    });
    console.log('Initial state:', initialState);

    // Simulate multiple rapid reorder events (simulating concurrent users)
    // NOTE: The new SSE handler expects `items` array in the event data
    await page.evaluate(() => {
      const events = [
        {
          type: 'item_reordered',
          id: 1,
          order_index: 3,
          items: [
            { id: 2, name: 'Item 2', quantity: 1, completed: false, order_index: 1 },
            { id: 3, name: 'Item 3', quantity: 1, completed: false, order_index: 2 },
            { id: 1, name: 'Item 1', quantity: 1, completed: false, order_index: 3 },
            { id: 4, name: 'Item 4', quantity: 1, completed: false, order_index: 4 },
            { id: 5, name: 'Item 5', quantity: 1, completed: false, order_index: 5 }
          ],
          client_id: 'client-1',
          timestamp: new Date().toISOString()
        },
        {
          type: 'item_reordered',
          id: 3,
          order_index: 1,
          items: [
            { id: 3, name: 'Item 3', quantity: 1, completed: false, order_index: 1 },
            { id: 2, name: 'Item 2', quantity: 1, completed: false, order_index: 2 },
            { id: 1, name: 'Item 1', quantity: 1, completed: false, order_index: 3 },
            { id: 4, name: 'Item 4', quantity: 1, completed: false, order_index: 4 },
            { id: 5, name: 'Item 5', quantity: 1, completed: false, order_index: 5 }
          ],
          client_id: 'client-2',
          timestamp: new Date().toISOString()
        },
        {
          type: 'item_reordered',
          id: 5,
          order_index: 2,
          items: [
            { id: 3, name: 'Item 3', quantity: 1, completed: false, order_index: 1 },
            { id: 5, name: 'Item 5', quantity: 1, completed: false, order_index: 2 },
            { id: 2, name: 'Item 2', quantity: 1, completed: false, order_index: 3 },
            { id: 1, name: 'Item 1', quantity: 1, completed: false, order_index: 4 },
            { id: 4, name: 'Item 4', quantity: 1, completed: false, order_index: 5 }
          ],
          client_id: 'client-3',
          timestamp: new Date().toISOString()
        }
      ];

      console.log('Simulating rapid reorder events:', events);

      // Process events rapidly to simulate concurrent reorders
      events.forEach((event, index) => {
        setTimeout(() => {
          (window as any).handleSSEEvent(event);
        }, index * 100); // 100ms delay between events
      });
    });

    // Wait for all reorders to complete
    await page.waitForTimeout(2000);

    // Check final state
    const finalState = await page.locator('.list-item').evaluateAll((items) => {
      return items.map(item => {
        const orderIndex = item.getAttribute('data-order-index');
        const name = item.querySelector('.item-name')?.textContent?.trim() || '';
        return { name, order_index: orderIndex ? parseInt(orderIndex) : 0 };
      });
    });

    console.log('Final state after concurrent reorders:', finalState);

    // After concurrent reorder events, items should have consistent sequential order indices
    const finalOrderIndices = finalState.map(item => item.order_index);
    const expectedIndices = [1, 2, 3, 4, 5];

    expect(finalOrderIndices).toEqual(expectedIndices);
  });

  test('should capture screenshots for visual verification', async ({ page, browserName}, testInfo) => {
    // Add sample items to show a populated state
    const sampleItems = [
      'Milk',
      'Bread',
      'Eggs',
      'Apples',
      'Bananas',
      'Chicken Breast',
      'Long Item Name That Should Wrap to Multiple Lines',
      'Second Item Name That Should Wrap to different Multiple Lines'
    ];

    for (const itemName of sampleItems) {
      await page.fill('#itemName', itemName);
      await page.click('.add-btn');
      await page.waitForTimeout(100);
    }

    // Mark some items as completed to show different states
    const firstItem = page.locator('.list-item').nth(0);
    await firstItem.locator('.item-checkbox').click();
    await page.waitForTimeout(500);

    const thirdItem = page.locator('.list-item').nth(2);
    await thirdItem.locator('.item-checkbox').click();
    await page.waitForTimeout(500);

    // Capture full page screenshot with project name for device identification
    const projectName = testInfo.project.name;
    const screenshotName = `pwa-${projectName.replace(/\s+/g, '-').toLowerCase()}.png`;

    await page.screenshot({
      path: `unittest_screenshots/${screenshotName}`,
      fullPage: true
    });

    // Verify the main elements are visible
    await expect(page.locator('#shoppingList')).toBeVisible();
    await expect(page.locator('#addItemForm')).toBeVisible();
    await expect(page.locator('#connectionStatus')).toBeVisible();
  });

  test.skip('should generate unique client IDs for different browser contexts', async ({ browser }) => {
    // Skipped: This test creates manual browser contexts that don't work with per-project baseURL setup
    // Create two separate browser contexts (simulating different browser windows)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    // Navigate both pages to the app
    await page1.goto('/');
    await page2.goto('/');

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

  test.skip('should demonstrate localStorage sharing issue within same browser context', async ({ browser }) => {
    // Skipped: This test creates manual browser contexts that don't work with per-project baseURL setup
    // Create one browser context and two pages (simulating different tabs in same browser window)
    const context = await browser.newContext();

    const page1 = await context.newPage();
    const page2 = await context.newPage();

    // Navigate both pages to the app
    await page1.goto('/');
    await page2.goto('/');

    // Wait for both pages to initialize
    await page1.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });
    await page2.waitForSelector('#shoppingList', { state: 'attached', timeout: 10000 });

    // Get client IDs from both pages
    const clientId1 = await page1.evaluate(() => (window as any).clientId);
    const clientId2 = await page2.evaluate(() => (window as any).clientId);

    // This assertion will FAIL, demonstrating the old bug
    expect(clientId1).toBeDefined();
    expect(clientId2).toBeDefined();
    expect(clientId1).not.toBe(clientId2); // This should fail with previous implementation

    // Clean up
    await context.close();
  });
});
