# Intel Mac setup — macOS Sequoia 15.7.7

**For the standalone desktop app, use [DESKTOP-UPDATES.md](DESKTOP-UPDATES.md).** Download and extract the Mac-Intel release, move the app to your user Applications folder, then open it. Python, Node and the source setup steps below are only needed for development. Desktop releases include **App Updates → Check for Updates → Download → Install & Relaunch**.

This is the standalone **StarPower Content Studio**, separate from the live tarot website. Its Python server, React editor, complete artwork, date calculations, database code, and video encoder all live in this repository. It runs locally at http://127.0.0.1:5057.

## One-time setup

1. Install **Python 3.12** using the macOS **universal2** installer from [Python's macOS downloads](https://www.python.org/downloads/macos/). Universal2 runs natively on Intel. Python 3.11–3.13 are supported by the installer script. If Python reports a certificate error, run its included **Install Certificates.command** once.
2. Install **Node.js 22 LTS, macOS x64 / Intel**, from [Node's v22 downloads](https://nodejs.org/en/download/archive/v22). Choose x64 for this Mac. Use 22.12 or newer in the 22 series. Node is used to build the editor; the normal launcher runs Python afterward.
3. Clone your private repository in GitHub Desktop, or use Terminal after signing into GitHub:

   ```bash
   git clone https://github.com/CLOVETHEDESTROYER/tarot-content-studio.git
   cd tarot-content-studio
   ```

4. Double-click **Setup Content Studio.command**. It creates a fresh Mac `.venv`, installs the pinned Python packages and native Intel FFmpeg, installs the locked frontend packages, builds the editor, and verifies all artwork.
5. Double-click **Start Content Studio.command**. Keep the Terminal window open while using the studio. It opens the browser automatically; you can also visit http://127.0.0.1:5057. Press Ctrl+C to stop it.

If macOS will not open a `.command` launcher, run these commands from the repository folder in Terminal:

```bash
bash "Setup Content Studio.command"
bash "Start Content Studio.command"
```

Git tracks the executable bits and LF line endings for the Mac launchers. If you downloaded a ZIP instead of cloning, you can also restore permissions with:

```bash
chmod +x *.command scripts/setup-mac.sh
```

## Voices and features

- **macOS voice · free** is the default on a fresh Mac installation. It uses the built-in `say` command and requires no API key. Each script section is rendered separately; card transitions follow measured section audio lengths. Word timing inside each section is estimated, which the preview identifies explicitly.
- **Built-in writing**, all tarot decks, the 72 daily cards, numerology, sky/calendar calculations, previews, video exports, and the daily planner work locally. Optional RSS headlines need an internet connection.
- **Coral / Nova and OpenAI writing** remain optional. Windows credentials do not transfer through Git. If you want these features, configure your own key on the Mac in the ignored local `.env` file or environment. Keep keys out of Git and chat.
- **Windows voice** is unavailable on the Mac. When importing a Windows reading or planner, select **macOS voice** before rendering it.
- Exports remain 1080 × 1920 portrait MP4 with captions, audio, a cover, posting text, and saved sources. All artwork is included in Git; no Git LFS setup is required.

## Saved work and updating

A fresh clone starts with an empty local library. Readings, cached narration, source snapshots, exported videos, `.env`, `node_modules`, and `.venv` are deliberately ignored by Git. Git transfers the application and artwork; it does not synchronize the two computers' libraries.

To transfer saved work, stop the studio on both computers and copy the complete `data/` and `exports/` folders separately into the Mac clone. These contain your SQLite database, context snapshots, audio, and exports. Keep backups before replacing either folder. Avoid copying the Windows `.venv` or `node_modules`. Existing completed exports remain usable; change Windows voice to macOS voice before making new renders, including planner defaults.

To update after future code changes:

```bash
git pull --ff-only
bash "Setup Content Studio.command"
bash "Start Content Studio.command"
```

Keep the studio running and Mac awake for automatic local AM/PM preparation. Targets remain 6 AM and 6 PM **America/Denver**, including daylight saving changes. Facebook publishing is a separate future integration.

## Verification

```bash
.venv/bin/python scripts/doctor.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/smoke-test.py
```

The smoke test creates and fully decodes a real local video with the native system voice. It uses temporary files and no OpenAI calls. GitHub Actions runs these checks on Windows and explicitly on **macOS 15 Intel (`macos-15-intel`)**, using Python 3.12 and Node 22. See the repository's Actions tab for the actual result; adding a workflow alone does not mean it has passed.

The encoder is installed by the pinned [imageio-ffmpeg package, including an Intel macOS wheel](https://pypi.org/project/imageio-ffmpeg/0.6.0/). A separate system FFmpeg installation is unnecessary. Intel runner availability is documented in [GitHub's runner reference](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).
