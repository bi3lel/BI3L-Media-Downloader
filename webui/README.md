# Local redesigned interface

This interface uses the supplied redesign's charcoal/red styling and the original BI3L logo. It calls the existing Python download workers through an authenticated loopback-only HTTP bridge; it does not simulate downloads. No hosting account is needed.

Build with Node.js 22.12+ (or a newer supported Node release):

```powershell
cd webui
npm ci
npm run build
npx tsc --noEmit
cd ..
python desktop_web.py
```

On Windows, `run.bat` and `run-web.bat` use the `.venv` created by `setup.bat`. The app opens in a native WebView2 window with working minimize, maximize/restore and close controls. The standard Windows title bar supports dragging down to restore a maximized window, snapping and edge resizing. Microsoft WebView2 Runtime must be installed for source/portable use; the offline installer includes it when missing. After changing frontend sources, run `npm run build` again and reopen the app. `python desktop_web.py --browser` opens an optional browser preview; its window controls are supplied by the browser.

Paste one or multiple media links. Continue only analyzes them. Choose individual playlist or Drive entries, choose quality/format, then download. Drive folders start with nothing selected and retain original file formats. MP4 downloads reuse hardware detection, encoder fallback and editing-compatible H.264/AAC conversion. Spotify candidates that cannot be confidently matched require a selection. Settings retain English/Portuguese, destination folder and downloader updates.

The redesign ZIP supplied only a demo single-item flow. Queue, Drive selection and Spotify matching screens extend its existing visual language. The fake letter-B mark was replaced with the unchanged original mascot. Windows controls appear at the top right; the Settings cogwheel is at the bottom left. The destination folder appears only inside the centered Settings dialog.

Validation: `python -m unittest discover` covers bridge selection, cancellation, Spotify request identity, playlist event accumulation, session authorization and path boundaries alongside the existing backend tests. No GitHub publication is performed by these build or launch commands.
