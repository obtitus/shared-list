# Project Progress

## To-Do
- [x] Create FastAPI backend with SQLite integration, ensure it runs outside docker
- [x] Setup Docker Compose for local development (Port 8000)
- [x] Add unittests with standard library unittest and ensure lint passes
- [x] Design OLED CSS theme for PWA that is easy to view while outside and a well lit grocery store
- [x] Add playwright tests and ensure they pass, target: Computer running Chrome, iPhone SE running IOS 26.1, iPhone Xr running IOS 18.7. Test basic functionality with typescript across browsers and more complex interactions with python unittest (test_pwa_functionality.py)
- [x] Create and add a simple and sleak shopping cart icon
- [ ] Change the CSS theme to white background, black text. Find a more pleasing color than the current green.
- [ ] Remove the strikethrough when items are checked, the checkbox is sufficients
- [ ] Ensure items can be re-arranged by dragging, item order must be syncronized
- [ ] Make the "Shopping List" name customizable.
- [ ] Ensure two or more instances of the webpage gets updated automatically on changes, use Server-Sent Events (SSE) and force a refresh every hour.
- [ ] Implement service worker for iOS "Add to Home Screen"
- [ ] Setup Ultra.cc deployment script

## Done
- [x] Project initialization and `.clinerules` setup
