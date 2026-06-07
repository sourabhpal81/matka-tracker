# Building the Matka Tracker APK

This turns the app screen (`app_ui/`) into an installable Android app. You do
**not** need Android Studio — a free GitHub Action compiles the APK in the cloud
and gives you a download link.

## What this app is
A WebView app that bundles the screen we designed (`app_ui/index.html` + your
`feed.js` data). It works offline with the bundled data, and — once you set a
feed URL — pulls fresh data each time it opens.

## Option A — build in the cloud (recommended, no tools needed)

1. **Create a free GitHub account** at github.com if you don't have one.
2. **Create a new repository** (e.g. `matka-tracker`), Private is fine.
3. **Upload this whole project folder** to the repo. Easiest way: on the repo
   page click **Add file → Upload files**, drag in the contents of
   `matka_tracker/` (including the `android/`, `app_ui/`, and `.github/`
   folders), and commit.
4. GitHub automatically runs the **Build Android APK** workflow (see the
   **Actions** tab). It takes ~3–5 minutes the first time.
5. When it finishes, open the **Releases** section of your repo (right sidebar) →
   release **"Matka Tracker (latest build)"** → download **`matka-tracker.apk`**.
   (You can also grab it from the workflow run's **Artifacts**.)

To rebuild after any change (new data, UI tweaks), just upload the changed files
again — the APK rebuilds automatically. The web UI is copied from `app_ui/` at
build time, so editing `app_ui/index.html` is all it takes to change the app.

## Option B — build locally (if you have Android Studio)
1. First copy the web files into the app:
   `app_ui/index.html`, `app_ui/feed.js`, `app_ui/config.js`
   → `android/app/src/main/assets/`
2. Open the `android/` folder in Android Studio, let it sync, then
   **Build → Build APK(s)**. The APK lands in
   `android/app/build/outputs/apk/debug/`.

## Installing the APK on a phone (sideloading)
1. Copy `matka-tracker.apk` to the phone (or download it directly on the phone).
2. Tap it. Android will ask to allow installing from this source — enable
   **"Allow from this source"** for your browser/Files app, then install.
3. Open **Matka Tracker** from the app drawer.

This is normal sideloading — no Play Store needed. Share the same `.apk` with
your users the same way.

## Turning on daily auto-updates
Out of the box the app shows the data that was bundled at build time. To make it
update by itself:

1. Host your `feed.json` somewhere public over **https** (see
   `BUILD_ANDROID_APP.md` — Firebase or a GitHub "feed" repo both work free).
2. Edit `app_ui/config.js` and set:
   `window.FEED_URL = "https://.../feed.json";`
3. Rebuild the APK (re-upload / re-run the Action) and reshare it once.

From then on, each day you run `admin_daily.py` it updates `matka.db`, rebuilds
`feed.json`, and uploads it — and every installed app pulls the new data on open.
(Push notifications are the Phase-2 Firebase step in `BUILD_ANDROID_APP.md`.)

## Notes
- `minSdk 26` → runs on Android 8.0 and newer.
- The app requests only INTERNET access (to fetch the feed).
- It shows results and statistics only — no accounts, money, or betting.
- A debug-signed APK installs fine for sideloading. For wider distribution you
  can later add a release signing key; ask and I'll wire it into the workflow.
