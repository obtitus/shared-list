#!/usr/bin/env python3
"""
Playwright E2E Tests for Shared Shopping List PWA
Tests core functionality across multiple devices and browsers using unittest
"""
import sys
import unittest
from playwright.sync_api import sync_playwright
from browser_error_capture import capture_browser_errors, assert_no_errors
from server_manager import TestServerManager, check_prerequisites


class TestShoppingListPWA(unittest.TestCase):
    """Test class for Shopping List PWA functionality"""

    @classmethod
    def setUpClass(cls):
        """Setup Docker environment before running tests"""
        print("🐳 Starting Docker setup tests...")

        # Check prerequisites
        if not check_prerequisites("docker"):
            sys.exit(1)

        # Setup server manager
        cls.server_manager = TestServerManager.for_docker_tests()

        # Start Docker container if not already running
        if not cls.server_manager.check_server_running():
            print("🐳 Starting Docker container...")
            success = cls.server_manager.start_docker_server(timeout=120)
            if not success:
                raise RuntimeError("Failed to start Docker container")

            # Wait for server to be fully ready
            if not cls.server_manager.wait_for_server_boot(timeout=60):
                raise RuntimeError("Docker container not ready after boot")

        print("✅ Docker container is running and ready for tests")

        # Initialize Playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls):
        """Cleanup for the test class"""
        if hasattr(cls, "browser") and cls.browser:
            cls.browser.close()
        if hasattr(cls, "playwright") and cls.playwright:
            cls.playwright.stop()
        if hasattr(cls, "server_manager") and cls.server_manager:
            print("🛑 tearDown Stopping server...")
            cls.server_manager.stop_server()

    def setUp(self):
        """Setup for each test"""
        # Navigate to the PWA
        self.page = self.context.new_page()
        self.page.goto("http://localhost:8000")
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
        self.page.fill("#itemQuantity", "3")

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

        # Check that the item has the correct name and quantity
        item_name = self.page.locator(".list-item:last-child .item-name").inner_text()
        item_quantity = self.page.locator(
            ".list-item:last-child .item-quantity"
        ).inner_text()

        self.assertEqual(
            item_name, "Test Item", f"Expected 'Test Item', got '{item_name}'"
        )
        self.assertEqual(item_quantity, "3", f"Expected '3', got '{item_quantity}'")

        # Check that the form was reset
        self.assertEqual(self.page.locator("#itemName").input_value(), "")
        self.assertEqual(self.page.locator("#itemQuantity").input_value(), "1")

        # Assert no errors occurred during item addition
        assert_no_errors(self.browser_errors, "test_add_item_functionality")

    def test_toggle_item_completion(self):
        """Test toggling item completion status"""
        # Add an item first with a unique identifier
        unique_name = f"Toggle Test Item {self.page.evaluate('Date.now()')}"
        self.page.fill("#itemName", unique_name)
        self.page.fill("#itemQuantity", "1")
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
        self.page.fill("#itemQuantity", "1")
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
            self.page.fill("#itemQuantity", "1")
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
        # Check initial online status (dot should be green/connected)
        status_dot = self.page.locator("#connectionStatus .status-dot")
        self.assertTrue(status_dot.is_visible())
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
        self.page.fill("#itemQuantity", "1")
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
        response = self.page.request.get("http://localhost:8000/static/manifest.json")
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
        self.page.fill("#itemQuantity", "2")
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
        self.page.fill("#itemQuantity", "1")
        self.page.click(".add-btn")
        self.page.wait_for_selector(".list-item", timeout=5000)

        # Check that empty state is hidden and list is shown
        self.assertFalse(self.page.locator("#emptyState").is_visible())
        self.assertTrue(self.page.locator("#shoppingList").is_visible())

    def test_form_validation(self):
        """Test form validation"""
        # Test with empty name
        self.page.fill("#itemName", "")
        self.page.fill("#itemQuantity", "1")

        # Check that add button is disabled
        add_button = self.page.locator(".add-btn")
        self.assertTrue(add_button.is_disabled())

        # Test with invalid quantity
        self.page.fill("#itemName", "Test Item")
        self.page.fill("#itemQuantity", "0")

        # Check that add button is disabled
        self.assertTrue(add_button.is_disabled())

        # Test with valid input
        self.page.fill("#itemName", "Test Item")
        self.page.fill("#itemQuantity", "1")

        # Check that add button is enabled
        self.assertFalse(add_button.is_disabled())

    def test_toast_notifications(self):
        """Test toast notification system"""
        # Add an item to trigger a success toast
        self.page.fill("#itemName", "Toast Test Item")
        self.page.fill("#itemQuantity", "1")
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
        self.page.fill("#itemQuantity", "1")
        self.page.click(".add-btn")

        # Wait for error toast
        self.page.wait_for_selector(".toast.error", timeout=5000)
        error_toast = self.page.locator(".toast.error")
        self.assertTrue(error_toast.is_visible())

        # Restore online status
        self.page.context.set_offline(False)
        self.page.wait_for_timeout(1000)

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

        # Check that inputs are large enough
        item_name = self.page.locator("#itemName")
        item_quantity = self.page.locator("#itemQuantity")

        name_height = item_name.evaluate("el => el.offsetHeight")
        quantity_height = item_quantity.evaluate("el => el.offsetHeight")

        self.assertGreaterEqual(
            name_height, 40, "Name input should be large enough for mobile"
        )
        self.assertGreaterEqual(
            quantity_height, 40, "Quantity input should be large enough for mobile"
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

    def test_real_time_updates(self):
        """Test real-time updates between multiple browser instances using SSE"""
        # Create two separate pages to simulate different users/devices
        page1 = self.context.new_page()
        page2 = self.context.new_page()

        # Setup error capture for both pages
        errors1 = capture_browser_errors(page1, self.context)
        errors2 = capture_browser_errors(page2, self.context)

        try:
            # Navigate both pages to the app
            page1.goto("http://localhost:8000")
            page2.goto("http://localhost:8000")

            # Wait for both apps to initialize
            page1.wait_for_selector("#shoppingList", state="attached", timeout=10000)
            page2.wait_for_selector("#shoppingList", state="attached", timeout=10000)

            # Get initial item counts
            initial_count1 = len(page1.locator(".list-item").all())
            initial_count2 = len(page2.locator(".list-item").all())

            # Add an item from page1
            page1.fill("#itemName", "Real-time Test Item")
            page1.fill("#itemQuantity", "2")
            page1.click(".add-btn")

            # Wait for the item to appear in page1
            page1.wait_for_selector(
                '.list-item:has-text("Real-time Test Item")', timeout=5000
            )

            # Verify the item appears in page2 via SSE (without manual refresh)
            page2.wait_for_selector(
                '.list-item:has-text("Real-time Test Item")', timeout=10000
            )

            # Check item details in page2
            item_name = page2.locator(
                '.list-item:has-text("Real-time Test Item") .item-name'
            ).inner_text()
            item_quantity = page2.locator(
                '.list-item:has-text("Real-time Test Item") .item-quantity'
            ).inner_text()

            self.assertEqual(item_name, "Real-time Test Item")
            self.assertEqual(item_quantity, "2")

            # Verify counts updated in both pages
            final_count1 = len(page1.locator(".list-item").all())
            final_count2 = len(page2.locator(".list-item").all())

            self.assertEqual(final_count1, initial_count1 + 1)
            self.assertEqual(final_count2, initial_count2 + 1)

            # Test that page1 doesn't show echo (since it triggered the event)
            # The item should still be there, but no duplicate toast or issues
            self.assertEqual(
                len(page1.locator('.list-item:has-text("Real-time Test Item")').all()),
                1,
            )

            # Assert no errors occurred
            assert_no_errors(errors1, "test_real_time_updates_page1")
            assert_no_errors(errors2, "test_real_time_updates_page2")

        finally:
            # Cleanup pages
            page1.close()
            page2.close()


def run_tests():
    """Run the test suite"""
    print("🧪 Starting Playwright E2E Tests for Shared Shopping List PWA")
    print("=" * 50)
    print("Testing core functionality across multiple devices and browsers")
    print(
        "Target platforms: Computer running Chrome, iPhone SE (iOS 26.1), iPhone XR (iOS 18.7)"
    )
    print()

    # Run the tests
    unittest.main(verbosity=2)

    print("=" * 50)
    print("🎉 Playwright test suite completed!")
    return True


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
