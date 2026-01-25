#!/usr/bin/env python3
"""
Dual Browser Tests for Shared Shopping List PWA
Tests requiring multiple browser instances for real-time functionality
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
PORT = 8012


class TestDualBrowserPWA(unittest.TestCase):
    """Test class for dual browser PWA functionality"""

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

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        if hasattr(cls, "playwright") and cls.playwright:
            cls.playwright.stop()
        if hasattr(cls, "server_manager"):
            cls.server_manager.__exit__()

    def setUp(self):
        """Setup for each test - create two separate browsers"""
        # Create separate browser instances for User A and User B to ensure true network isolation
        self.browser_a = self.playwright.chromium.launch(headless=True)
        self.browser_b = self.playwright.chromium.launch(headless=True)

        # Create contexts and pages in each browser
        self.context_a = self.browser_a.new_context()
        self.context_b = self.browser_b.new_context()
        self.page_a = self.context_a.new_page()
        self.page_b = self.context_b.new_page()

        # Navigate both pages to the app
        self.page_a.goto(self.BASE_URL)
        self.page_b.goto(self.BASE_URL)

        # Setup error capture for both pages
        self.errors_a = capture_browser_errors(self.page_a, self.context_a)
        self.errors_b = capture_browser_errors(self.page_b, self.context_b)

        # Wait for both apps to initialize
        self.page_a.wait_for_selector("#shoppingList", state="attached", timeout=10000)
        self.page_b.wait_for_selector("#shoppingList", state="attached", timeout=10000)

        # Wait for SSE connections to establish
        self.page_a.wait_for_timeout(3000)  # Extra time for SSE setup
        self.page_b.wait_for_timeout(3000)  # Extra time for SSE setup

    def tearDown(self):
        """Cleanup after each test"""
        # Close pages, contexts, and browsers in the correct order
        self.page_a.close()
        self.page_b.close()
        self.context_a.close()
        self.context_b.close()
        self.browser_a.close()
        self.browser_b.close()

        if hasattr(self, "errors_a") and self.errors_a:
            self.errors_a.clear_errors()
        if hasattr(self, "errors_b") and self.errors_b:
            self.errors_b.clear_errors()

    def test_real_time_updates(self):
        """Test real-time updates between multiple browser instances using SSE"""
        # Get initial item counts
        initial_count_a = len(self.page_a.locator(".list-item").all())
        initial_count_b = len(self.page_b.locator(".list-item").all())

        # Add an item from page A
        self.page_a.fill("#itemName", "Real-time Test Item")
        self.page_a.click(".add-btn")

        # Wait for the item to appear in page A
        self.page_a.wait_for_selector(
            '.list-item:has-text("Real-time Test Item")', timeout=5000
        )

        # Verify the item appears in page B via SSE (without manual refresh)
        self.page_b.wait_for_selector(
            '.list-item:has-text("Real-time Test Item")', timeout=10000
        )

        # Check item details in page B
        item_name = self.page_b.locator(
            '.list-item:has-text("Real-time Test Item") .item-name'
        ).inner_text()

        self.assertEqual(item_name, "Real-time Test Item")

        # Verify counts updated in both pages
        final_count_a = len(self.page_a.locator(".list-item").all())
        final_count_b = len(self.page_b.locator(".list-item").all())

        self.assertEqual(final_count_a, initial_count_a + 1)
        self.assertEqual(final_count_b, initial_count_b + 1)

        # Test that page A doesn't show echo (since it triggered the event)
        # The item should still be there, but no duplicate toast or issues
        self.assertEqual(
            len(
                self.page_a.locator('.list-item:has-text("Real-time Test Item")').all()
            ),
            1,
        )

        # Assert no errors occurred
        assert_no_errors(self.errors_a, "test_real_time_updates_page_a")
        assert_no_errors(self.errors_b, "test_real_time_updates_page_b")

    def test_user_a_adds_item_user_b_sees_via_sse(self):
        """Test User A adds item, User B sees it via SSE, then User B disconnects and reconnects"""
        # Clear all items first to start fresh
        self.page_a.click("#clearBtn")
        self.page_a.wait_for_timeout(1000)
        self.page_b.wait_for_timeout(1000)

        # Verify both pages show empty state
        self.assertTrue(self.page_a.locator("#emptyState").is_visible())
        self.assertTrue(self.page_b.locator("#emptyState").is_visible())

        # User A adds first item
        self.page_a.fill("#itemName", "User A First Item")
        self.page_a.click(".add-btn")
        self.page_a.wait_for_timeout(2000)  # Increased wait time for first item

        # Verify User A sees the item
        user_a_item_exists = self.page_a.locator(
            '.list-item:has-text("User A First Item")'
        ).is_visible()
        self.assertTrue(user_a_item_exists, "User A should see their own item")

        # Verify User B sees the item via SSE (without manual refresh)
        self.page_b.wait_for_selector(
            '.list-item:has-text("User A First Item")', timeout=10000
        )
        user_b_sees_item = self.page_b.locator(
            '.list-item:has-text("User A First Item")'
        ).is_visible()
        self.assertTrue(user_b_sees_item, "User B should see User A's item via SSE")

        # Verify both pages show the item in the list
        user_a_items = self.page_a.locator(".list-item .item-name").all_text_contents()
        user_b_items = self.page_b.locator(".list-item .item-name").all_text_contents()
        self.assertIn("User A First Item", user_a_items)
        self.assertIn("User A First Item", user_b_items)

        # Now simulate User B going offline using test flag (using separate browser, this won't affect User A)
        self.context_b.set_offline(True)
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = true")

        # Verify User A is still online (this is the key test - separate browsers should be completely independent)
        status_dot_a = self.page_a.locator("#connectionStatus .status-dot")
        dot_class_a = status_dot_a.get_attribute("class") or ""
        self.assertIn(
            "connected",
            dot_class_a,
            "User A should remain online when User B goes offline",
        )

        # User A adds second item while User B is offline
        self.page_a.fill("#itemName", "User A Second Item")
        self.page_a.click(".add-btn")
        self.page_a.wait_for_timeout(1000)

        # Verify only page A shows the item in the list
        user_a_item_after = self.page_a.locator(
            ".list-item .item-name"
        ).all_text_contents()

        # Verify User A sees both items
        self.assertIn("User A First Item", user_a_item_after)
        self.assertIn("User A Second Item", user_a_item_after)
        self.assertEqual(len(user_a_item_after), 2)

        # User B should still only see the first item (no SSE updates while offline due to test flag)
        user_b_item_after = self.page_b.locator(
            ".list-item .item-name"
        ).all_text_contents()

        self.assertIn("User A First Item", user_b_item_after)
        self.assertNotIn("User A Second Item", user_b_item_after)
        self.assertEqual(len(user_b_item_after), 1)

        # Simulate User B coming back online
        self.context_b.set_offline(False)
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = false")
        self.page_b.wait_for_timeout(1000)

        # User B should now see both items after reconnection (data reload)
        user_b_items_online = self.page_b.locator(
            ".list-item .item-name"
        ).all_text_contents()
        self.assertIn("User A First Item", user_b_items_online)
        self.assertIn("User A Second Item", user_b_items_online)
        self.assertEqual(len(user_b_items_online), 2)

        # Verify the order is correct (first item should come before second)
        self.assertEqual(user_b_items_online[0], "User A First Item")
        self.assertEqual(user_b_items_online[1], "User A Second Item")

        # Assert no errors occurred
        assert_no_errors(
            self.errors_a, "test_user_a_adds_item_user_b_sees_via_sse_page_a"
        )
        assert_no_errors(
            self.errors_b, "test_user_a_adds_item_user_b_sees_via_sse_page_b"
        )

    def test_event_state_mismatch_handling(self):
        """Test that state mismatches trigger warnings and force refreshes"""
        # Clear all items first
        self.page_a.click("#clearBtn")
        self.page_a.wait_for_timeout(1000)
        self.page_b.wait_for_timeout(1000)

        # Add an item to both pages
        self.page_a.fill("#itemName", "Mismatch Test Item")
        self.page_a.click(".add-btn")
        self.page_a.wait_for_timeout(2000)

        # Verify both pages see the item
        self.page_a.wait_for_selector(
            '.list-item:has-text("Mismatch Test Item")', timeout=10000
        )
        self.page_b.wait_for_selector(
            '.list-item:has-text("Mismatch Test Item")', timeout=10000
        )

        # Create a state mismatch by simulating User B going offline
        # This will cause User B to miss subsequent events
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = true")

        # User A toggles the item while User B is offline (generates SSE event)
        item_checkbox_a = self.page_a.locator(
            '.list-item:has-text("Mismatch Test Item") .item-checkbox'
        )
        item_checkbox_a.click()
        self.page_a.wait_for_timeout(1000)

        # User B should still see the item (outdated state)
        item_checkbox_b = self.page_b.locator(
            '.list-item:has-text("Mismatch Test Item") .item-checkbox'
        )
        class_a = item_checkbox_a.get_attribute("class") or ""
        class_b = item_checkbox_b.get_attribute("class") or ""
        is_checked_a = "checked" in class_a
        is_checked_b = "checked" in class_b
        self.assertTrue(is_checked_a, "User A should see item as checked")
        self.assertFalse(is_checked_b, "User B should see item as unchecked (outdated)")

        # Now bring User B back online
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = false")
        self.page_b.wait_for_timeout(2000)

        # Now let user A toggle again while user B is online, should trigger refresh
        item_checkbox_a.click()
        self.page_a.wait_for_timeout(1000)

        # User A and B should see the same state
        class_a_after = item_checkbox_a.get_attribute("class") or ""
        class_b_after = item_checkbox_b.get_attribute("class") or ""
        is_checked_a_after = "checked" in class_a_after
        is_checked_b_after = "checked" in class_b_after
        self.assertFalse(is_checked_a_after, "User A should see item as unchecked")
        self.assertFalse(is_checked_b_after, "User B should see item as unchecked")

        # Check that a warning was logged for count mismatch
        warn_a = self.errors_a.get_all_warnings()
        warn_b = self.errors_b.get_all_warnings()
        self.assertEqual(warn_a, [], "No warnings should be present on page A")
        self.assertEqual(len(warn_b), 1, "page B should have a refresh warning")
        self.assertIn(
            "refreshing...", warn_b[0], "page B should have a refresh warning"
        )
        # Assert no errors occurred (warnings are expected)
        assert_no_errors(self.errors_a, "test_event_state_mismatch_handling_page_a")
        assert_no_errors(self.errors_b, "test_event_state_mismatch_handling_page_b")

    def test_count_mismatch_handling(self):
        """Test that count mismatches trigger warnings and force refreshes"""
        # Clear all items first
        self.page_a.click("#clearBtn")
        self.page_a.wait_for_timeout(1000)
        self.page_b.wait_for_timeout(1000)

        # Add two items
        for i in range(2):
            self.page_a.fill("#itemName", f"Count Mismatch Item {i+1}")
            self.page_a.click(".add-btn")
            self.page_a.wait_for_timeout(1000)

        # Verify both pages see both items
        self.page_b.wait_for_timeout(2000)
        user_a_count = len(self.page_a.locator(".list-item").all())
        user_b_count = len(self.page_b.locator(".list-item").all())
        self.assertEqual(user_a_count, 2)
        self.assertEqual(user_b_count, 2)

        # Create a count mismatch by simulating User B going offline
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = true")

        # User A adds another item while User B is offline
        self.page_a.fill("#itemName", "Count Mismatch Item 3")
        self.page_a.click(".add-btn")
        self.page_a.wait_for_timeout(1000)

        # User A should now have 3 items
        user_a_count = len(self.page_a.locator(".list-item").all())
        user_b_count = len(self.page_b.locator(".list-item").all())
        self.assertEqual(user_a_count, 3)
        # User B should still think it has 2 items (outdated state)
        self.assertEqual(user_b_count, 2)

        # Now bring User B back online
        self.page_b.evaluate("window.TEST_OFFLINE_MODE = false")
        self.page_b.wait_for_timeout(2000)

        # Now let user A add an additional item while user B is online, should trigger refresh
        self.page_a.fill("#itemName", "Count Item 4")
        self.page_a.click(".add-btn")
        self.page_a.wait_for_timeout(1000)

        # User B should now see the correct count after force refresh
        user_a_count = len(self.page_a.locator(".list-item").all())
        user_b_count = len(self.page_b.locator(".list-item").all())
        self.assertEqual(user_a_count, 4)

        # Check that a warning was logged for count mismatch
        warn_a = self.errors_a.get_all_warnings()
        warn_b = self.errors_b.get_all_warnings()
        self.assertEqual(warn_a, [], "No warnings should be present on page A")
        self.assertEqual(len(warn_b), 1, "page B should have a refresh warning")
        self.assertIn(
            "refreshing...", warn_b[0], "page B should have a refresh warning"
        )
        # Assert no errors occurred (warnings are expected)
        assert_no_errors(self.errors_a, "test_count_mismatch_handling_page_a")
        assert_no_errors(self.errors_b, "test_count_mismatch_handling_page_b")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s[%(levelname)s] - %(name)s\t%(message)s",
    )
    unittest.main(verbosity=2)
