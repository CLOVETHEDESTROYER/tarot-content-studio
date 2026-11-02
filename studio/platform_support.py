"""Local capabilities and safe defaults for each supported operating system."""
import sys


def default_voice():
    return {'win32':'windows','darwin':'macos'}.get(sys.platform,'silent')


def voice_capabilities():
    return dict(windows=sys.platform=='win32',macos=sys.platform=='darwin',default_voice=default_voice())
