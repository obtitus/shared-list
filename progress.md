# Project Progress

## To-Do
- [x] Remove item-quantity from the frontend, set it to 1 when adding items to the database.
- [x] Remove the "Delete" text on the delete-btn, leaving only the Wastebasket emoji. Simplify "Clear All" to "Clear".
- [ ] Make item-name editable, maybe with a new edit button (use emoji only).
- [x] Improve caching behavior when changes are made by e.g. modify template to `<script src="{{ url_for('static', path='/app.js') }}?v={{ version }}"></script>`.
- [x] Add `{passive: true}` to our touch/scroll event listeners to improve scrolling performance.
- [ ] Add a robots.txt and any other simple tricks to avoid crawlers finding and indexing this page, altough security is not a major concern, anyone with a link can edit this list and I would like to avoid bots doing that.
- [ ] Reduce the SSE connection retries (especially when the server is actually oflline, there is no need to constantly refresh) and delay the initial SSE connection so the page fully loads before a connection attempt is made

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
- [x] When adding an item, make it simple to select where in the list it appears. One solution could be to allow the user to select existing items in the list and inserting above the selected item.
- [x] Add clipboard-based import/export feature with iOS-compatible Web Share API, supporting plain text format (one item per row) with flexible parsing for quantities and bullet points.
- [x] Allow empty items, they work nicely as a visual spacer
- [x] On a small IOS display the item description get shortened with ..., remove this and use multiple lines instead. At least for small displays, get rid of the wasted padding on the edges.
