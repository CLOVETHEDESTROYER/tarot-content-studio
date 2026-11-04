import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if getattr(sys,'frozen',False):ROOT=Path(sys._MEIPASS)
load_dotenv(ROOT / '.env')
USER_ROOT=Path(os.getenv('LOCALAPPDATA',str(Path.home()/'Library/Application Support')))/'StarPower Content Studio' if getattr(sys,'frozen',False) else ROOT
load_dotenv(USER_ROOT/'.env')
DATA = Path(os.getenv('STUDIO_DATA_DIR', str(USER_ROOT / 'data')))
EXPORTS = Path(os.getenv('STUDIO_EXPORT_DIR', str(USER_ROOT / 'exports')))
ASSETS = ROOT / 'assets'


def api_client():
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError('OpenAI is not configured. Choose built-in writing or the local system voice.')
    from openai import OpenAI
    return OpenAI(timeout=90, max_retries=1)
