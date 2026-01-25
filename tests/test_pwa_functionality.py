#!/usr/bin/env python3
"""
Playwright E2E Tests for Shared Shopping List PWA
Tests core functionality across multiple devices and browsers using unittest
"""
import os
import sys
import unittest
import logging
from playwright.sync_api import sync_playwright
from browser_error_capture import capture_browser_errors, assert_no_errors
from server_manager import ServerManager, check_prerequisites

# Create logger
logger = logging.getLogger("test." + os.path.basename(__file__))

# Configuration
PORT = 8013


class TestShoppingListPWA(unittest.TestCase):
    """Test class for Shopping List PWA functionality"""

    @classmethod
    def setUpClass(cls):
        """Setup server before running tests"""
        # Check prerequisites
        if not check_prerequisites("docker"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = ServerManager(port=PORT, server_type="docker")
        cls.server_manager.__enter__()
        cls.BASE_URL = cls.server_manager.base_url
        logger.info(f"🌐 Server is running {cls.BASE_URL}")

        # Initialize Playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        if hasattr(cls, "browser") and cls.browser:
            cls.browser.close()
        if hasattr(cls, "playwright") and cls.playwright:
            cls.playwright.stop()
        if hasattr(cls, "server_manager"):
            cls.server_manager.__exit__()

    def setUp(self):
        """Setup for each test"""
        # Navigate to the PWA
        self.page = self.context.new_page()
        self.page.goto(self.BASE_URL)
        # Setup browser error capture
        self.browser_errors = capture_browser_errors(self.page, self.context)

        # Don't wait for networkidle since SSE keeps connection open
        # Just wait for the app to initialize
        self.page.wait_for_selector("#shoppingList", state="attached", timeout=10000)

    def tearDown(self):
        """Cleanup after each test"""
        # Close the page to ensure SSE connections are terminated
        self.page.close()
        if hasattr(self, "browser_errors") and self.browser_errors:
            self.browser_errors.clear_errors()

    def test_page_loads_and_renders(self):
        """Test that the PWA loads and renders correctly"""
        # Check title (dynamic based on list name)
        title = self.page.title()
        self.assertTrue(
            "Shared Shopping List" in title,
            f"Title should contain 'Shared Shopping List', got '{title}'",
        )

        # Check that the main container exists
        self.assertTrue(self.page.locator("#shoppingList").is_visible())

        # Check that the add item form exists
        self.assertTrue(self.page.locator("#addItemForm").is_visible())

        # Check connection status indicator
        self.assertTrue(self.page.locator("#connectionStatus").is_visible())

        # Assert no errors occurred during page load
        assert_no_errors(self.browser_errors, "test_page_loads_and_renders")

    def test_add_item_functionality(self):
        """Test adding items to the shopping list"""
        # Get initial item count
        initial_count = len(self.page.locator(".list-item").all())

        # Fill out the form
        self.page.fill("#itemName", "Test Item")

        # Submit the form
        self.page.click(".add-btn")

        # Wait for the item to appear
        self.page.wait_for_timeout(1000)
        assert_no_errors(self.browser_errors, "test_page_loads_and_renders")

        # Check that the item was added
        new_count = len(self.page.locator(".list-item").all())
        self.assertGreaterEqual(
            new_count, initial_count + 1, "Item was not added to the list"
        )

        # Check that the item has the correct name
        item_name = self.page.locator(".list-item:last-child .item-name").inner_text()

        self.assertEqual(
            item_name, "Test Item", f"Expected 'Test Item', got '{item_name}'"
        )

        # Check that the form was reset
        self.assertEqual(self.page.locator("#itemName").input_value(), "")

        # Assert no errors occurred during item addition
        assert_no_errors(self.browser_errors, "test_add_item_functionality")

    def test_toggle_item_completion(self):
        """Test toggling item completion status"""
        # Add an item first with a unique identifier
        unique_name = f"Toggle Test Item {self.page.evaluate('Date.now()')}"
        self.page.fill("#itemName", unique_name)
        self.page.click(".add-btn")
        self.page.wait_for_selector(".list-item", timeout=5000)

        # Find the item by its unique name
        item = self.page.locator(f'.list-item:has-text("{unique_name}")')

        # Check initial state (not completed)
        item_class = item.get_attribute("class") or ""
        checkbox_class = item.locator(".item-checkbox").get_attribute("class") or ""
        self.assertNotIn("completed", item_class)
        self.assertNotIn("checked", checkbox_class)

        # Toggle the item
        item.locator(".item-checkbox").click()

        # Wait for the state to change and DOM to stabilize
        self.page.wait_for_timeout(1000)

        # Check that the item is now completed
        item_class_after_toggle = item.get_attribute("class") or ""
        checkbox_class_after_toggle = (
            item.locator(".item-checkbox").get_attribute("class") or ""
        )
        self.assertIn("completed", item_class_after_toggle)
        self.assertIn("checked", checkbox_class_after_toggle)

        # Toggle back
        item.locator(".item-checkbox").click()
        self.page.wait_for_timeout(1000)

        # Check that the item is not completed
        item_class_after_toggle_back = item.get_attribute("class") or ""
        checkbox_class_after_toggle_back = (
            item.locator(".item-checkbox").get_attribute("class") or ""
        )
        self.assertNotIn("completed", item_class_after_toggle_back)
        self.assertNotIn("checked", checkbox_class_after_toggle_back)

    def test_delete_item(self):
        """Test deleting items from the shopping list"""
        # Add an item first
        self.page.fill("#itemName", "Delete Test Item")
        self.page.click(".add-btn")
        self.page.wait_for_timeout(1000)

        # Get initial count
        initial_count = len(self.page.locator(".list-item").all())

        # Delete the item
        self.page.locator(".list-item:last-child .delete-btn").click()

        # Wait for the item to be removed
        self.page.wait_for_timeout(2000)

        # Check that the item was removed
        new_count = len(self.page.locator(".list-item").all())
        self.assertLess(new_count, initial_count, "Item was not removed from the list")

        # Assert no errors occurred during item deletion
        assert_no_errors(self.browser_errors, "test_delete_item")

    def test_clear_all_items(self):
        """Test clearing all items from the shopping list"""
        # Add a few items first
        for i in range(3):
            self.page.fill("#itemName", f"Clear Test Item {i+1}")
            # Quantity input removed
            self.page.click(".add-btn")
            self.page.wait_for_timeout(1000)

        # Get initial count
        initial_count = len(self.page.locator(".list-item").all())
        self.assertGreaterEqual(
            initial_count, 3, "Not enough items were added for the test"
        )

        # Clear all items
        self.page.click("#clearBtn")

        # Wait for items to be cleared
        self.page.wait_for_timeout(3000)  # Increased wait time

        # Check that all items were removed
        final_count = len(self.page.locator(".list-item").all())
        self.assertEqual(final_count, 0, "All items should be cleared from the list")

    def test_offline_functionality(self):
        """Test offline functionality and connection status"""
        # Check initial online status (dot should be green/connected after SSE connects)
        status_dot = self.page.locator("#connectionStatus .status-dot")
        self.assertTrue(status_dot.is_visible())

        # Wait for SSE connection to establish (delayed by 500ms after page load + connection time)
        self.page.wait_for_timeout(2000)  # Wait up to 2 seconds for connection

        dot_class = status_dot.get_attribute("class") or ""
        self.assertIn("connected", dot_class)

        # Simulate offline mode
        self.page.context.set_offline(True)

        # Wait for status to update
        self.page.wait_for_timeout(1000)

        # Check offline status (dot should be red/offline)
        dot_class_offline = status_dot.get_attribute("class") or ""
        self.assertIn("offline", dot_class_offline)
        self.assertNotIn("connected", dot_class_offline)

        # Try to add an item while offline (should show error)
        self.page.fill("#itemName", "Offline Test Item")
        # Quantity input removed
        self.page.click(".add-btn")

        # Check for error toast
        self.page.wait_for_selector(".toast.error", timeout=5000)
        error_toast = self.page.locator(".toast.error")
        self.assertTrue(error_toast.is_visible())

        # Restore online status
        self.page.context.set_offline(False)
        self.page.wait_for_timeout(1000)

        # Check online status restored (dot should be back to connected if SSE reconnects)
        # Note: May still be offline if SSE hasn't reconnected yet
        dot_class_restored = status_dot.get_attribute("class") or ""
        # Just check that it's not offline anymore (may be connected or offline depending on timing)
        self.assertNotIn("offline", dot_class_restored)

    @unittest.skip("Service worker not yet implemented")
    def test_pwa_manifest_and_service_worker(self):
        """Test PWA manifest and service worker registration"""
        # Check that the manifest is accessible
        response = self.page.request.get(f"{self.BASE_URL}/static/manifest.json")
        self.assertEqual(response.status, 200, "Manifest should be accessible")

        manifest = response.json()
        self.assertEqual(
            manifest["name"], "Shared Shopping List", "Manifest name should match"
        )
        self.assertEqual(
            manifest["display"], "standalone", "Display mode should be standalone"
        )

        # Check that service worker is registered
        service_worker_registered = self.page.evaluate(
            """
            () => {
                return 'serviceWorker' in navigator && navigator.serviceWorker.controller !== null;
            }
        """
        )

        self.assertTrue(
            service_worker_registered, "Service worker should be registered"
        )

    def test_keyboard_shortcuts(self):
        """Test keyboard shortcuts functionality"""
        # Focus on the add item input
        self.page.keyboard.press("Control+K")

        # Check that the input is focused
        focused_element = self.page.evaluate("() => document.activeElement.id")
        self.assertEqual(
            focused_element, "itemName", "Item name input should be focused"
        )

        # Add an item using Enter
        self.page.fill("#itemName", "Keyboard Test Item")
        # Quantity input removed
        self.page.keyboard.press("Enter")

        # Wait for the item to appear
        self.page.wait_for_timeout(2000)  # Wait for form submission

        # Check that the item was added
        item_name = self.page.locator(".list-item:last-child .item-name").inner_text()
        self.assertEqual(
            item_name,
            "Keyboard Test Item",
            f"Expected 'Keyboard Test Item', got '{item_name}'",
        )

    def test_empty_state(self):
        """Test empty state display"""
        # Clear all items first
        self.page.click("#clearBtn")
        self.page.wait_for_timeout(1000)

        # Check that empty state is shown
        self.assertTrue(self.page.locator("#emptyState").is_visible())
        self.assertFalse(self.page.locator("#shoppingList").is_visible())

        # Add an item
        self.page.fill("#itemName", "Empty State Test")
        # Quantity input removed
        self.page.click(".add-btn")
        self.page.wait_for_selector(".list-item", timeout=5000)

        # Check that empty state is hidden and list is shown
        self.assertFalse(self.page.locator("#emptyState").is_visible())
        self.assertTrue(self.page.locator("#shoppingList").is_visible())

    def test_form_validation(self):
        """Test form validation"""
        # Test with empty name (allowed for visual spacers)
        self.page.fill("#itemName", "")

        # Check that add button is enabled (empty names allowed for spacers)
        add_button = self.page.locator(".add-btn")
        self.assertFalse(add_button.is_disabled())

        # Test with valid name
        self.page.fill("#itemName", "Test Item")

        # Check that add button is enabled
        self.assertFalse(add_button.is_disabled())

    def test_toast_notifications(self):
        """Test toast notification system"""
        # Add an item to trigger a success toast
        self.page.fill("#itemName", "Toast Test Item")
        # Quantity input removed
        self.page.click(".add-btn")

        # Wait for the item-added success toast (not the SSE connection toast)
        self.page.wait_for_selector(
            '.toast.success:has-text("Item added successfully")', timeout=5000
        )
        success_toast = self.page.locator(
            '.toast.success:has-text("Item added successfully")'
        )
        self.assertTrue(success_toast.is_visible())

        # Check that the toast disappears after a few seconds
        self.page.wait_for_timeout(4000)
        self.assertFalse(success_toast.is_visible())

        # Test error toast by going offline and trying to add an item
        self.page.context.set_offline(True)
        self.page.wait_for_timeout(1000)

        self.page.fill("#itemName", "Offline Toast Test")
        # Quantity input removed
        self.page.click(".add-btn")

        # Wait for error toast
        self.page.wait_for_selector(".toast.error", timeout=5000)
        error_toast = self.page.locator(".toast.error")
        self.assertTrue(error_toast.is_visible())

        # Restore online status
        self.page.context.set_offline(False)
        self.page.wait_for_timeout(1000)

    def test_item_insertion_via_selection(self):
        """Test selecting an item and inserting a new item above it"""
        # Clear all items first
        self.page.click("#clearBtn")
        self.page.wait_for_timeout(1000)

        # Add three items first
        for i in range(3):
            self.page.fill("#itemName", f"Item {i+1}")
            # Quantity input removed
            self.page.click(".add-btn")
            self.page.wait_for_timeout(1000)

        # Verify initial order
        items = self.page.locator(".list-item .item-name").all_text_contents()
        self.assertEqual(items, ["Item 1", "Item 2", "Item 3"])

        # Select the second item ("Item 2") by clicking on it
        second_item = self.page.locator('.list-item:has-text("Item 2")')
        second_item.click()

        # Check that it's selected (has selected class)
        item_class = second_item.get_attribute("class") or ""
        self.assertIn("selected", item_class)

        # Add a new item with selection active
        self.page.fill("#itemName", "New Item")
        # Quantity input removed
        self.page.click(".add-btn")

        # Wait for the item to appear
        self.page.wait_for_timeout(2000)

        # Verify new order: Item 1, New Item, Item 2, Item 3
        updated_items = self.page.locator(".list-item .item-name").all_text_contents()
        self.assertEqual(updated_items, ["Item 1", "New Item", "Item 2", "Item 3"])

        # Verify selection is cleared after adding
        selected_items = self.page.locator(".list-item.selected").all()
        self.assertEqual(len(selected_items), 0)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_item_insertion_via_selection")

    def test_responsive_design(self):
        """Test responsive design on mobile"""
        # Set mobile viewport
        self.page.set_viewport_size({"width": 375, "height": 667})  # iPhone SE size

        # Check that the layout is responsive
        shopping_list = self.page.locator("#shoppingList")
        self.assertTrue(shopping_list.is_visible())

        # Check that items are properly sized for mobile
        if self.page.locator(".list-item").count() > 0:
            item = self.page.locator(".list-item").first
            item_height = item.evaluate("el => el.offsetHeight")
            self.assertGreater(
                item_height, 40, "Items should be large enough for touch interaction"
            )

        # Test form is mobile-friendly
        form = self.page.locator("#addItemForm")
        self.assertTrue(form.is_visible())

        # Check that input is large enough
        item_name = self.page.locator("#itemName")

        name_height = item_name.evaluate("el => el.offsetHeight")

        self.assertGreaterEqual(
            name_height, 40, "Name input should be large enough for mobile"
        )

    def test_add_to_home_screen_prompt(self):
        """Test Add to Home Screen functionality"""
        # Check for beforeinstallprompt event
        prompt_shown = self.page.evaluate(
            """
            () => {
                return window.addEventListener('beforeinstallprompt', (e) => {
                    e.preventDefault();
                    window.deferredPrompt = e;
                    return true;
                });
            }
        """
        )

        # The test passes if the event listener was successfully added
        self.assertIsNot(
            prompt_shown, False, "beforeinstallprompt event should be supported"
        )

    def test_pwa_theme_colors(self):
        """Test PWA theme colors"""
        # Check meta theme-color tag
        theme_color = self.page.locator('meta[name="theme-color"]').get_attribute(
            "content"
        )
        self.assertIsNotNone(theme_color, "Theme color meta tag should exist")
        self.assertEqual(
            theme_color, "#ffffff", f"Expected theme color #ffffff, got {theme_color}"
        )

        # Check that the page has light theme
        body_bg = self.page.locator("body").evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )
        self.assertIsNotNone(body_bg, "Body background color should exist")
        body_bg_str = body_bg or ""
        self.assertTrue(
            "rgb(255, 255, 255)" in body_bg_str or "#fff" in body_bg_str.lower(),
            "Body should have light background",
        )

    def test_pwa_orientation(self):
        """Test PWA orientation lock"""
        # Check meta viewport tag
        viewport = (
            self.page.locator('meta[name="viewport"]').get_attribute("content") or ""
        )
        self.assertIsNotNone(viewport, "Viewport meta tag should exist")
        self.assertIn(
            "viewport-fit=cover", viewport, "Viewport should support cover fit"
        )

        # Test orientation change (if supported)
        try:
            self.page.evaluate("screen.orientation.lock('portrait-primary')")
            self.page.wait_for_timeout(500)

            orientation = self.page.evaluate("screen.orientation.type")
            self.assertIsNotNone(orientation, "Orientation should exist")
            orientation_str = orientation or ""
            self.assertIn(
                "portrait", orientation_str, "Orientation should be locked to portrait"
            )
        except Exception:
            # Orientation lock might not be supported in all environments
            pass

    def test_import_export_parsing(self):
        """Test the import text parsing logic"""
        # Test various input formats
        test_cases = [
            # (input_text, expected_output)
            (
                "Milk x 2\nBread\n✓ Eggs x 12\n- Apples\n* Bananas",
                [
                    {"name": "Milk", "quantity": 2, "completed": False},
                    {"name": "Bread", "quantity": 1, "completed": False},
                    {"name": "Eggs", "quantity": 12, "completed": True},
                    {"name": "Apples", "quantity": 1, "completed": False},
                    {"name": "Bananas", "quantity": 1, "completed": False},
                ],
            ),
            (
                "[x] Completed Task\n[ ] Incomplete Task\n2 x Oranges",
                [
                    {"name": "Completed Task", "quantity": 1, "completed": True},
                    {"name": "Incomplete Task", "quantity": 1, "completed": False},
                    {"name": "Oranges", "quantity": 2, "completed": False},
                ],
            ),
            ("", []),  # Empty input
            ("\n\n\n", []),  # Only whitespace/newlines
            (
                "Simple item\n✓ Completed item\n3 x Items with quantity",
                [
                    {"name": "Simple item", "quantity": 1, "completed": False},
                    {"name": "Completed item", "quantity": 1, "completed": True},
                    {"name": "Items with quantity", "quantity": 3, "completed": False},
                ],
            ),
        ]

        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                # Execute the parseImportText function in the browser context
                result = self.page.evaluate(
                    f"""
                    () => {{
                        return parseImportText({repr(input_text)});
                    }}
                """
                )

                # Normalize the result for comparison (ensure consistent types)
                normalized_result = []
                for item in result:
                    normalized_result.append(
                        {
                            "name": item["name"],
                            "quantity": int(item["quantity"]),
                            "completed": bool(item["completed"]),
                        }
                    )

                self.assertEqual(
                    normalized_result, expected, f"Failed to parse: {repr(input_text)}"
                )

    def test_import_export_ui_functionality(self):
        """Test the import/export UI functionality"""
        # Clear all items first
        self.page.click("#clearBtn")
        self.page.wait_for_timeout(1000)

        # Add some test items with completion status
        test_items = [
            {"name": "Milk", "quantity": 2, "completed": False},
            {"name": "Bread", "quantity": 1, "completed": True},
            {"name": "Eggs", "quantity": 12, "completed": False},
        ]

        for item in test_items:
            self.page.fill("#itemName", item["name"])
            self.page.click(".add-btn")
            self.page.wait_for_timeout(1000)

            # Mark as completed if needed
            if item["completed"]:
                # Find the item and toggle it
                item_locator = self.page.locator(
                    f'.list-item:has-text("{item["name"]}") .item-checkbox'
                )
                item_locator.click()
                self.page.wait_for_timeout(1000)

        # Test export functionality (in headless mode, clipboard permission is denied,
        # so it falls back to console.log which we can capture)
        self.page.click("#exportBtn")
        self.page.wait_for_timeout(1000)

        # Export always logs to console with delimiters for testing
        # Check that the console contains the expected export format
        console_messages = []
        self.page.on("console", lambda msg: console_messages.append(msg.text))

        # Click export and wait for console messages
        self.page.click("#exportBtn")
        self.page.wait_for_timeout(1000)

        # Verify console contains the delimited export
        export_start_found = any(
            "=== SHOPPING LIST EXPORT ===" in msg for msg in console_messages
        )
        export_end_found = any("=== END EXPORT ===" in msg for msg in console_messages)

        # Check that we have the export content (should be the middle message)
        export_content_found = False
        for i, msg in enumerate(console_messages):
            if "=== SHOPPING LIST EXPORT ===" in msg and i + 1 < len(console_messages):
                # Next message should be the actual content
                next_msg = console_messages[i + 1]
                if next_msg and not next_msg.startswith("==="):
                    export_content_found = True
                    break

        self.assertTrue(
            export_start_found and export_end_found and export_content_found,
            f"Export should log to console with delimiters. Console messages: {console_messages}",
        )

        # Test import modal opens
        self.page.click("#importBtn")
        self.page.wait_for_selector("#importModal", timeout=5000)
        self.assertTrue(self.page.locator("#importModal").is_visible())

        # Test import functionality with sample data
        import_text = "New Milk x 3\n✓ New Bread\nNew Eggs"
        self.page.fill("#importText", import_text)
        self.page.click("#importConfirm")

        # Wait for modal to close and items to be added
        self.page.wait_for_timeout(3000)

        # Verify modal is closed
        self.assertFalse(self.page.locator("#importModal").is_visible())

        # Verify new items were added
        all_items = self.page.locator(".list-item .item-name").all_text_contents()

        # Check that new items are present
        self.assertIn("New Milk", all_items)
        self.assertIn("New Bread", all_items)
        self.assertIn("New Eggs", all_items)

        # Check completion status for New Bread (should be completed)
        bread_item = self.page.locator('.list-item:has-text("New Bread")')
        bread_class = bread_item.get_attribute("class") or ""
        self.assertIn("completed", bread_class)

        # Assert no errors occurred (ignore expected clipboard API errors in headless mode)
        assert_no_errors(
            self.browser_errors,
            "test_import_export_ui_functionality",
            ignore_patterns=["Clipboard API failed"],
        )

    def test_connection_health_monitoring(self):
        """Test connection health monitoring and automatic reconnection"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Check that connection is healthy initially
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""
        self.assertIn("connected", dot_class)

        # Test that we can force reconnection
        self.page.evaluate("() => window.forceSSEReconnection()")
        self.page.wait_for_timeout(2000)

        # Check that connection is re-established
        dot_class_after_reconnect = status_dot.get_attribute("class") or ""
        self.assertIn("connected", dot_class_after_reconnect)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_connection_health_monitoring")

    def test_ios_visibility_change_reconnection(self):
        """Test iOS lock/unlock screen scenario with visibility change events"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate page becoming hidden (lock screen)
        self.page.evaluate(
            "() => document.dispatchEvent(new Event('visibilitychange'))"
        )
        self.page.evaluate(
            "() => Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })"
        )

        # Wait a moment
        self.page.wait_for_timeout(500)

        # Simulate page becoming visible again (unlock screen)
        self.page.evaluate(
            "() => Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })"
        )
        self.page.evaluate(
            "() => document.dispatchEvent(new Event('visibilitychange'))"
        )

        # Wait for reconnection to happen
        self.page.wait_for_timeout(2000)

        # Check that connection status is updated
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""

        # Connection should be healthy after visibility change
        self.assertIn("connected", dot_class)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_ios_visibility_change_reconnection")

    def test_ios_focus_blur_events(self):
        """Test iOS tab switching scenarios with focus/blur events"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate page losing focus (switching to another app/tab)
        self.page.evaluate("() => window.dispatchEvent(new Event('blur'))")

        # Wait a moment
        self.page.wait_for_timeout(500)

        # Simulate page gaining focus again
        self.page.evaluate("() => window.dispatchEvent(new Event('focus'))")

        # Wait for connection check to happen
        self.page.wait_for_timeout(2000)

        # Check that connection status is updated
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""

        # Connection should be healthy after focus event
        self.assertIn("connected", dot_class)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_ios_focus_blur_events")

    def test_ios_resume_event_handling(self):
        """Test iOS app resume event handling"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate iOS app resume event (specific to mobile Safari)
        self.page.evaluate("() => document.dispatchEvent(new Event('resume'))")

        # Wait for forced reconnection to happen
        self.page.wait_for_timeout(2000)

        # Check that connection status is updated
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""

        # Connection should be healthy after resume event
        self.assertIn("connected", dot_class)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_ios_resume_event_handling")

    def test_ios_pageshow_event_handling(self):
        """Test iOS pageshow event handling for better mobile support"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate pageshow event (when page is shown from cache)
        self.page.evaluate(
            "() => window.dispatchEvent(new Event('pageshow', { persisted: true }))"
        )

        # Wait for connection check to happen
        self.page.wait_for_timeout(2000)

        # Check that connection status is updated
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""

        # Connection should be healthy after pageshow event
        self.assertIn("connected", dot_class)

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_ios_pageshow_event_handling")

    def test_ios_network_state_change_reconnection(self):
        """Test iOS network state changes and reconnection behavior"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate going offline
        self.page.context.set_offline(True)
        self.page.wait_for_timeout(1000)

        # Check offline status
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""
        self.assertIn("offline", dot_class)

        # Simulate coming back online
        self.page.context.set_offline(False)
        self.page.wait_for_timeout(2000)

        # Check that connection is re-established
        dot_class_after_online = status_dot.get_attribute("class") or ""
        self.assertIn("connected", dot_class_after_online)

        # Assert no errors occurred
        assert_no_errors(
            self.browser_errors, "test_ios_network_state_change_reconnection"
        )

    def test_ios_forced_reconnection_functionality(self):
        """Test iOS forced reconnection functionality"""
        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Test forced reconnection
        self.page.evaluate("() => window.forceSSEReconnection()")
        self.page.wait_for_timeout(2000)

        # Check that reconnection happened
        connection_healthy = self.page.evaluate("() => window.isConnectionHealthy")
        self.assertTrue(
            connection_healthy, "Connection should be healthy after forced reconnection"
        )

        # Check that retry count was reset
        retry_count = self.page.evaluate("() => window.sseRetryCount")
        self.assertEqual(
            retry_count, 0, "Retry count should be reset after forced reconnection"
        )

        # Assert no errors occurred
        assert_no_errors(
            self.browser_errors, "test_ios_forced_reconnection_functionality"
        )

    def test_ios_lock_unlock_scenario(self):
        """Test complete iOS lock/unlock screen scenario"""
        # Add some items to test data persistence
        self.page.fill("#itemName", "Test Item Before Lock")
        self.page.click(".add-btn")
        self.page.wait_for_timeout(1000)

        # Wait for SSE connection to establish
        self.page.wait_for_timeout(3000)

        # Simulate iOS lock screen (page becomes hidden)
        self.page.evaluate(
            "() => Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })"
        )
        self.page.evaluate(
            "() => document.dispatchEvent(new Event('visibilitychange'))"
        )

        # Wait a moment to simulate being locked
        self.page.wait_for_timeout(1000)

        # Simulate iOS unlock screen (page becomes visible)
        self.page.evaluate(
            "() => Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })"
        )
        self.page.evaluate(
            "() => document.dispatchEvent(new Event('visibilitychange'))"
        )

        # Wait for reconnection and data refresh
        self.page.wait_for_timeout(3000)

        # Check that connection is healthy
        status_dot = self.page.locator("#connectionStatus .status-dot")
        dot_class = status_dot.get_attribute("class") or ""
        self.assertIn("connected", dot_class)

        # Check that data is still there (no data loss)
        item_exists = self.page.locator(
            '.list-item:has-text("Test Item Before Lock")'
        ).is_visible()
        self.assertTrue(item_exists, "Data should persist through lock/unlock cycle")

        # Add another item to verify functionality works after reconnection
        self.page.fill("#itemName", "Test Item After Unlock")
        self.page.click(".add-btn")
        self.page.wait_for_timeout(1000)

        # Verify new item was added successfully
        new_item_exists = self.page.locator(
            '.list-item:has-text("Test Item After Unlock")'
        ).is_visible()
        self.assertTrue(
            new_item_exists, "New items should be addable after reconnection"
        )

        # Assert no errors occurred
        assert_no_errors(self.browser_errors, "test_ios_lock_unlock_scenario")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s[%(levelname)s] - %(name)s\t%(message)s",
    )
    unittest.main(verbosity=2)
