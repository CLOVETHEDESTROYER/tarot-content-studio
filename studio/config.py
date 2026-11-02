import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA = Path(os.getenv('STUDIO_DATA_DIR', str(ROOT / 'data')))
EXPORTS = Path(os.getenv('STUDIO_EXPORT_DIR', str(ROOT / 'exports')))
ASSETS = ROOT / 'assets'


def api_client():
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError('OpenAI is not configured. Choose built-in writing or the local system voice.')
    from openai import OpenAI
    return OpenAI(timeout=90, max_retries=1)
