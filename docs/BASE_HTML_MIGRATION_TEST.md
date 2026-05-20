# Manual test checklist: flask-base layout migration

After `.\.venv\Scripts\python.exe app.py --run` with a valid `.env`:

## Shell and navigation

- [ ] Home (`/`) loads with centered card layout and hamburger menu
- [ ] Hamburger lists all pages (Tasks, Stats, Morning Cards, Dice Rolls, Daily Tasks, Manage Cards, Goals, Test, Settings, Rewards Owed)
- [ ] Active page is highlighted in the menu
- [ ] Username appears under the page title after load (demo: `test_user`)

## Authentication

- [ ] Visit `/?key=<your CT_KEY value>` — redirects/strips key, shows real username (e.g. Ian)
- [ ] `/api/user` in browser or DevTools shows correct `authenticated` flag

## CloudTasks-specific chrome

- [ ] Streak indicator (fire) appears when you or spouse is below daily points minimum
- [ ] Indicator links to `/stats` when clicked

## Pages (data loads)

- [ ] Tasks — task list loads after brief wait
- [ ] Goals, Stats, Daily Tasks, Morning Cards, Settings — no JS console errors about `authState`
- [ ] `/morning-cards/manage` loads

## Regression

- [ ] Page-specific styling still looks correct (buttons, task cards, forms)
- [ ] `utils.js` module pages work (`waitForAuth` no longer hangs)
