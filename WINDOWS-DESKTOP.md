# Windows desktop app

Version 2.3 adds **App Updates** for private release checks, verified downloads, and **Install & Relaunch**. See [DESKTOP-UPDATES.md](DESKTOP-UPDATES.md) for authentication and recovery. Earlier desktop builds need this version installed once before they gain in-app updates.

Open **StarPower Content Studio.lnk** in this project folder, or **Start Desktop Studio.cmd**. The launcher uses the packaged executable when available. It opens a native Windows window using the installed Microsoft Edge WebView2 runtime; no browser tab or Terminal needs to stay open.

The local executable is `desktop-dist/StarPower Content Studio/StarPower Content Studio.exe`. Keep the entire `StarPower Content Studio` directory together: `_internal` contains the embedded Python runtime, encoder, artwork, and interface. The packaged app does not require Python or Node to use it. The generated shortcut is local to this computer and is ignored by Git.

## Saved work

This computer's shortcut passes `--workspace` pointing to the existing project, preserving its `data/`, `exports/`, saved readings, and Muse exchange settings. Those folders remain outside the executable package and are not replaced by rebuilding the app.

Without a workspace argument, a distributed executable defaults to `%LOCALAPPDATA%/StarPower Content Studio/data` and `exports`. A new installation starts a new library. The app doesn't silently import another computer's database. Optional credentials can live in that user folder's `.env` or the process environment; none are bundled.

The app reuses an already running studio only when its export folder matches the selected workspace. Otherwise it starts its own loopback-only engine. Closing an owned app waits for active batches/exports to finish before allowing exit. The native close confirmation also protects against accidentally closing an edited reading. Keep the app and computer awake for Muse inbox processing.

## Build

On Windows, after the normal frontend build:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-desktop.txt
./.venv/Scripts/python.exe scripts/build-windows-desktop.py
```

The builder bundles the built frontend, all artwork, agent instructions, FFmpeg, and the native narration helper, excluding local data, credentials and exports. Edge WebView2 Runtime must be installed on the target Windows system.

`StarPower Content Studio.exe --self-test --report <absolute-json-path>` checks the frozen package's assets, Windows narration, rendered frames, and a fully decoded portrait MP4 without OpenAI calls. Native-window QA separately exercises History & Agent Jobs, a real reading, narration, and export inside WebView2.

## Scope

This is the Windows desktop build. The Intel Mac desktop bundle and in-app update installer are subsequent work. The existing browser/source launchers remain available for development; the desktop launcher does not open them. Do not replace the app directory while it is running.
