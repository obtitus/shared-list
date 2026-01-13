#!/usr/bin/env python3
"""
Browser Error Capture System for Playwright Tests
Captures JavaScript errors, console errors, and network failures during test execution
"""

import json
import logging
from typing import List, Dict, Any
from playwright.sync_api import Page, BrowserContext, ConsoleMessage, Dialog, Error

# Create logger
logger = logging.getLogger("test." + __name__)


class BrowserErrorCapture:
    """Captures and reports browser errors during test execution"""

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context
        self.errors: List[Dict[str, Any]] = []
        self.console_messages: List[Dict[str, Any]] = []
        self.network_failures: List[Dict[str, Any]] = []
        self.dialogs: List[Dict[str, Any]] = []

        # Setup error capture
        self._setup_error_capture()

    def _setup_error_capture(self):
        """Setup event listeners for capturing browser errors"""
        # Capture JavaScript errors
        self.page.on("pageerror", self._handle_page_error)

        # Capture console messages
        self.page.on("console", self._handle_console_message)

        # Capture dialog interactions
        self.page.on("dialog", self._handle_dialog)

        # Capture network failures
        self.context.on("requestfailed", self._handle_request_failed)

    def _handle_page_error(self, error: Error):
        """Handle JavaScript errors"""
        self.errors.append(
            {
                "type": "page_error",
                "message": str(error),
                "timestamp": self._get_timestamp(),
                "url": self.page.url,
            }
        )
        logger.error(f"JavaScript Error: {error}")

    def _handle_console_message(self, message: ConsoleMessage):
        """Handle console messages"""
        msg_data = {
            "type": "console",
            "level": message.type,
            "text": message.text,
            "timestamp": self._get_timestamp(),
            "url": self.page.url,
            "location": None,
        }

        # Add location info if available
        if message.location:
            msg_data["location"] = {
                "url": getattr(message.location, "url", None),
                "line": getattr(message.location, "line", None),
                "column": getattr(message.location, "column", None),
            }
        self.console_messages.append(msg_data)

        # Log errors and warnings
        if message.type in ["error", "warn"]:
            logger.warning(f"Console {message.type}: {message.text}")

    def _handle_dialog(self, dialog: Dialog):
        """Handle dialog interactions"""
        dialog_data = {
            "type": "dialog",
            "dialog_type": dialog.type,
            "message": dialog.message,
            "timestamp": self._get_timestamp(),
            "url": self.page.url,
        }
        self.dialogs.append(dialog_data)
        logger.info(f"Dialog {dialog.type}: {dialog.message}")

        # Auto-accept confirmation dialogs for testing
        try:
            if dialog.type == "confirm":
                dialog.accept()
            else:
                dialog.dismiss()
        except Exception as e:
            logger.warning(f"Failed to handle dialog: {e}")

    def _handle_request_failed(self, request):
        """Handle network request failures"""
        # Skip SSE connection aborts as they are expected when pages unload/navigate
        if "/events" in request.url and "aborted" in str(request.failure).lower():
            logger.debug(f"SSE connection aborted (expected): {request.url}")
            return

        failure_data = {
            "type": "network_failure",
            "url": request.url,
            "failure": request.failure,
            "timestamp": self._get_timestamp(),
            "method": request.method,
            "headers": dict(request.headers) if hasattr(request, "headers") else {},
        }
        self.network_failures.append(failure_data)
        logger.error(f"Network Failure: {request.url} - {request.failure}")

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        import datetime

        return datetime.datetime.now().isoformat()

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all captured errors"""
        return {
            "total_errors": len(self.errors),
            "total_console_messages": len(self.console_messages),
            "total_network_failures": len(self.network_failures),
            "total_dialogs": len(self.dialogs),
            "errors": self.errors,
            "console_messages": self.console_messages,
            "network_failures": self.network_failures,
            "dialogs": self.dialogs,
        }

    def print_error_report(self):
        """Print detailed error report"""
        summary = self.get_error_summary()

        print("\n" + "=" * 60)
        print("BROWSER ERROR CAPTURE REPORT")
        print("=" * 60)

        print(f"Total Errors: {summary['total_errors']}")
        print(f"Total Console Messages: {summary['total_console_messages']}")
        print(f"Total Network Failures: {summary['total_network_failures']}")
        print(f"Total Dialogs: {summary['total_dialogs']}")

        if summary["errors"]:
            print("\n--- JAVASCRIPT ERRORS ---")
            for error in summary["errors"]:
                print(f"❌ {error['message']} (at {error['url']})")

        if summary["console_messages"]:
            print("\n--- CONSOLE MESSAGES ---")
            for msg in summary["console_messages"]:
                level_icon = (
                    "⚠️"
                    if msg["level"] == "warn"
                    else "❌" if msg["level"] == "error" else "ℹ️"
                )
                print(f"{level_icon} [{msg['level'].upper()}] {msg['text']}")

        if summary["network_failures"]:
            print("\n--- NETWORK FAILURES ---")
            for failure in summary["network_failures"]:
                print(f"❌ {failure['method']} {failure['url']}: {failure['failure']}")

        if summary["dialogs"]:
            print("\n--- DIALOGS ---")
            for dialog in summary["dialogs"]:
                print(f"💬 [{dialog['dialog_type']}] {dialog['message']}")

        print("=" * 60)

    def save_error_report(self, filename: str):
        """Save error report to JSON file"""
        summary = self.get_error_summary()
        with open(filename, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Error report saved to {filename}")

    def clear_errors(self):
        """Clear all captured errors"""
        self.errors.clear()
        self.console_messages.clear()
        self.network_failures.clear()
        self.dialogs.clear()


def capture_browser_errors(page: Page, context: BrowserContext) -> BrowserErrorCapture:
    """Factory function to create and setup browser error capture"""
    return BrowserErrorCapture(page, context)


def assert_no_errors(capture: BrowserErrorCapture, test_name: str = ""):
    """Assert that no errors occurred during test"""
    summary = capture.get_error_summary()

    critical_errors = []
    for error in summary["errors"]:
        critical_errors.append(f"JavaScript Error: {error['message']}")

    for failure in summary["network_failures"]:
        if "failed" in str(failure["failure"]).lower():
            critical_errors.append(
                f"Network Failure: {failure['url']} - {failure['failure']}"
            )

    if critical_errors:
        error_msg = f"Critical errors found in {test_name}:\n" + "\n".join(
            critical_errors
        )
        capture.print_error_report()
        raise AssertionError(error_msg)

    warnings = []
    for msg in summary["console_messages"]:
        if msg["level"] in ["warn", "error"]:
            warnings.append(f"Console {msg['level']}: {msg['text']}")

    if warnings:
        error_msg = f"Warnings found in {test_name}:\n" + "\n".join(warnings)
        capture.print_error_report()
        raise AssertionError(error_msg)


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
