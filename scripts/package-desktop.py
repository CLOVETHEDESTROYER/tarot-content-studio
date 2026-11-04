"""Archive only the app, with checksums; never include studio data or secrets."""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from studio.updates import APP,package_name,validate_archive

folder=ROOT/'desktop-dist';archive=folder/package_name()
if sys.platform=='darwin':
    subprocess.run(['/usr/bin/ditto','-c','-k','--norsrc','--keepParent',str(folder/(APP+'.app')),str(archive)],check=True)
else:
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for file in sorted((folder/APP).rglob('*')):
            if file.is_file():output.write(file,file.relative_to(folder))
validate_archive(archive)
digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='utf-8')
print(archive.name,archive.stat().st_size,digest)
