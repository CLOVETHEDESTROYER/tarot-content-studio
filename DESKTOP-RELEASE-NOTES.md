Native desktop packages for Intel Macs running macOS Sequoia 15 or newer and Windows x64.

- The complete studio, artwork, local narration and video renderer are included. Python and Node installation are unnecessary.
- App Updates checks this private repository, verifies the downloaded package, and offers Install & Relaunch.
- Updates wait for active work, retain the previous app, and check the new native window before completing. Failed startup automatically restores the previous app.
- Readings, exports, Google Drive exchange settings, Muse requests, and publication history stay outside the application and remain in place.

Mac: download the Mac-Intel ZIP, extract it, and move StarPower Content Studio.app to your user Applications folder. This personal build is ad-hoc signed, not Apple notarized; on first launch use macOS System Settings → Privacy & Security → Open Anyway if macOS blocks it.

Windows: extract the entire Windows-x64 ZIP and launch StarPower Content Studio.exe inside its folder. Keep the _internal folder beside the executable.

Private updates use an existing GitHub CLI sign-in or a repository token with read-only Contents access saved through App Updates in the operating system credential store. No credentials are included in either package.
