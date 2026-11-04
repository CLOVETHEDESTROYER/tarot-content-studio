"""Local exchange folder validation and actionable filesystem errors."""
import sys
from pathlib import Path


def exchange_path(value):
    if not isinstance(value,str):raise ValueError('Choose a folder on this computer.')
    value=value.strip()
    if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1].strip()
    if not value:raise ValueError('Choose a dedicated Tarot exchange folder on this computer.')
    if '://' in value or value.lower().startswith(('drive.google.com','docs.google.com','www.')):
        raise ValueError('Choose the local Google Drive folder from File Explorer or Finder, not a website link. Open Google Drive for desktop and use Browse folders.')
    root=Path(value).expanduser()
    if not root.is_absolute():raise ValueError('Choose the full local folder path. Use Browse folders to select it from this computer.')
    if sys.platform=='win32' and not Path(root.anchor).is_dir():
        raise ValueError(f'The drive {root.anchor} is not available. Open Google Drive for desktop, sign in, and wait for its drive to appear in File Explorer. Then use Browse folders; the drive letter may differ.')
    if sys.platform=='darwin' and root.parts[1:2]==('Volumes',) and len(root.parts)>2 and not Path(*root.parts[:3]).is_dir():
        raise ValueError('The selected drive is not mounted. Open Google Drive for desktop, then choose its folder in Finder.')
    return root.resolve()


def folder_error(error):
    if isinstance(error,PermissionError):return 'The studio cannot write to this folder. Choose a folder you can edit, and check its sharing permissions in Google Drive for desktop.'
    if isinstance(error,(FileExistsError,NotADirectoryError)):return 'This path points to a file or contains a file where a folder is needed. Choose a dedicated Tarot exchange folder.'
    if isinstance(error,FileNotFoundError):return 'The folder or drive is unavailable. Open Google Drive for desktop, sign in, and choose its local folder after it appears in File Explorer or Finder.'
    if getattr(error,'winerror',None)==123:return 'Windows could not use this folder path. Use Browse folders to choose a local folder instead of pasting a website link.'
    return 'The exchange folder could not be prepared. Check that the drive is connected and the folder is available locally and writable, then try again.'
