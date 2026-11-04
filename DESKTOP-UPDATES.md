# Desktop installation and updates

Download the latest `desktop-v…` release while signed in to the private repository:
https://github.com/CLOVETHEDESTROYER/tarot-content-studio/releases/latest

## Intel Mac (macOS Sequoia 15+)

1. Download `StarPower-Content-Studio-Mac-Intel.zip` and extract it.
2. Create an Applications folder in your home folder if needed. Move `StarPower Content Studio.app` there before opening it; updates need a writable app folder. Do not run from the ZIP or a temporary download preview.
3. Open the app. This personal package is ad-hoc signed, not Apple notarized. If macOS blocks the first launch, use System Settings → Privacy & Security → Open Anyway after checking that the download came from this repository.
4. No Python, Node, FFmpeg, or terminal setup is required. Local narration uses the Mac's installed system voice.
5. In History & Agent Jobs, select your separate Tarot Google Drive exchange folder. Never select the Zenwave exchange. The Mac needs Google Drive Desktop syncing that folder locally.

Default Mac data and exports are in `~/Library/Application Support/StarPower Content Studio/`. An existing Windows studio's data is not automatically migrated to the Mac. Do not sync live SQLite files between running computers.

## Windows

Extract the entire `StarPower-Content-Studio-Windows-x64.zip` and open the executable inside its folder. The complete folder is the application. Default saved data is under `%LOCALAPPDATA%/StarPower Content Studio/`.

The existing development shortcut uses `--workspace` to preserve its original readings and exports. Keep using that shortcut for the existing studio; launching an unrelated copy directly uses the default data location instead.

## App Updates

Open **App Updates → Check for Updates → Download → Install & Relaunch**. Checks and downloads are user initiated. The private repository requires either an existing GitHub CLI sign-in or a fine-grained token limited to this repository with **Contents: read-only**. Save the token through App Updates; it goes to macOS Keychain / Windows Credential Manager. Never put it in source code, Muse exchange files, or release assets.

The updater verifies repository, platform, version, exact download size, GitHub SHA-256 digest, archive paths, app identity, compatible history/exchange schemas, and the native executable. Mac signatures are verified too; ad-hoc verification does not establish an Apple Developer identity.

Installation waits for accepted generation jobs to finish, pauses new mutations, snapshots SQLite, and copies the app beside the installed app. A detached installer retains the previous app and opens the new native window. Startup checks include rendered editor, artwork, FFmpeg, and readable history. If startup fails, the installer restores and relaunches the previous app. It **never overwrites the current database with the snapshot**, so later reading/publication records are preserved. Recovery and logs are beside the user's data in `Updates/Recovery` and `logs`.

**Restore Previous App & Relaunch** uses the same compatibility and startup checks. Saved readings, exports and Google Drive exchange remain outside the app. Keep your normal backups; these snapshots are local recovery aids.

## Release process

Update `resources/desktop-release.json` and frontend package versions together. Run **Desktop packages** in GitHub Actions with Publish selected. Separate Windows x64 and `macos-15-intel` runners build the full bundles, run tests, render/decode a narrated portrait video from the frozen executable, and launch the native window. Only when both platforms pass are both ZIPs and SHA-256 files published together as `desktop-vX.Y.Z`. The update checker ignores source-only releases, drafts, prereleases and other platforms.

For Apple-notarized public distribution, a Developer ID certificate and Apple notarization credentials still need to be configured. They are not embedded in this personal build.
