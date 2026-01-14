# Project Progress

## To-Do
- [x] When adding an item, make it simple to select where in the list it appears. One solution could be to allow the user to select existing items in the list and inserting above the selected item.
- [x] Add clipboard-based import/export feature with iOS-compatible Web Share API, supporting plain text format (one item per row) with flexible parsing for quantities and bullet points.
- [x] Allow empty items, they work nicely as a visual spacer

## Done
- [x] Project initialization and `.clinerules` setup
- [x] Create FastAPI backend with SQLite integration, ensure it runs outside docker
- [x] Setup Docker Compose for local development (Port 8000)
- [x] Add unittests with standard library unittest and ensure lint passes
- [x] Design OLED CSS theme for PWA that is easy to view while outside and a well lit grocery store
- [x] Add playwright tests and ensure they pass, target: Computer running Chrome, iPhone SE running IOS 26.1, iPhone Xr running IOS 18.7. Test basic functionality with typescript across browsers and more complex interactions with python unittest (test_pwa_functionality.py)
- [x] Create and add a simple and sleak shopping cart icon
- [x] Change the CSS theme to white background, black text. Find a more pleasing color than the current green.
- [x] Remove the strikethrough when items are checked, the checkbox is sufficients
- [x] Ensure items can be re-arranged by dragging, item order must be syncronized
- [x] Make the "Shopping List" name customizable
- [x] Ensure two or more instances of the webpage gets updated automatically on changes, use Server-Sent Events (SSE) and force a refresh every hour.
- [x] When the server connects and disconnects, don't show the "Real-time updates" banner, simply toggle the connection-status indicator.
- [x] Add missing favicon.ico
- [x] Ensure all unittests use logging (keep it a simple stdout log) consistently
- [x] Setup apoc.usbx.me deployment script
