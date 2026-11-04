import json
from .config import ROOT
BUILD=json.loads((ROOT/'resources/desktop-release.json').read_text(encoding='utf-8'))
VERSION=BUILD['version']
