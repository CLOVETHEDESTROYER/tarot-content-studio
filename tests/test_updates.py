import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from studio import operations
from studio.updates import REPO,APP,DesktopUpdates,DesktopBridge,package_name,select_release,validate_archive,filesystem_path
from studio.update_install import validate_plan


def release(v='2.4.0',host='darwin'):
    tag='desktop-v'+v;name=package_name(host)
    return dict(tag_name=tag,html_url=f'https://github.com/{REPO}/releases/tag/{tag}',
        assets=[dict(name=name,state='uploaded',size=50,id=123,digest='sha256:'+'a'*64,
            browser_download_url=f'https://github.com/{REPO}/releases/download/{tag}/{name}')])


class UpdateTests(unittest.TestCase):
    @unittest.skipUnless(__import__('sys').platform=='win32','Windows extended paths')
    def test_update_extraction_supports_paths_over_260_characters(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/('a'*100)/('b'*100)/('c'*40)
            archive=Path(tmp)/'app.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('package/deep/file.txt','verified')
            self.assertGreater(len(str(root/'package/deep/file.txt')),260)
            try:
                with zipfile.ZipFile(archive) as z:z.extractall(filesystem_path(root))
                self.assertEqual(Path(filesystem_path(root/'package/deep/file.txt')).read_text(),'verified')
            finally:shutil.rmtree(filesystem_path(Path(tmp)/('a'*100)))

    def test_only_newer_matching_platform_release(self):
        self.assertEqual(select_release([release('2.4.0'),release('2.5.0')],'2.3.0','darwin')['version'],'2.5.0')
        for v in ('2.2.0','2.3.0'):
            self.assertIsNone(select_release([release(v)],'2.3.0','darwin'))
        self.assertIsNone(select_release([release()],'2.3.0','win32'))

    def test_repository_digest_and_publication_are_required(self):
        for key,value in [('draft',True),('prerelease',True),('html_url','https://example.org/release')]:
            r=release();r[key]=value;self.assertIsNone(select_release([r],'2.3.0','darwin'))
        for key,value in [('digest',None),('digest','sha256:bad'),('id',-1),('size',2_000_000_000),('browser_download_url','https://example.org/app.zip')]:
            r=release();r['assets'][0][key]=value
            self.assertIsNone(select_release([r],'2.3.0','darwin'))

    def archive(self,name,link=None,host='darwin'):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'app.zip'
            with zipfile.ZipFile(archive,'w') as z:
                if link:
                    info=zipfile.ZipInfo(name);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
                    z.writestr(info,link)
                else:
                    info=zipfile.ZipInfo();info.filename=name
                    z.writestr(info,'test')
            return validate_archive(archive,host)

    def test_archive_confines_every_file(self):
        top=APP+'.app'
        self.assertEqual(self.archive(top+'/Contents/file'),top)
        for name in ('../file',top+'/../file','/absolute',top+'/Contents/../../file',top+'/file\\evil',top+'/file:stream'):
            with self.assertRaises(ValueError):self.archive(name)

    def test_mac_framework_links_stay_inside_app(self):
        top=APP+'.app'
        self.archive(top+'/Contents/Frameworks/Python.framework/Versions/Current','3.12')
        self.archive(top+'/Contents/Frameworks/Python.framework/Python','Versions/Current/Python')
        for link in ('../../../../outside','/etc/passwd'):
            with self.assertRaises(ValueError):self.archive(top+'/Contents/link',link)
        with self.assertRaises(ValueError):self.archive(APP+'/link','safe','win32')

    def test_installer_paths_do_not_enter_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/APP
            plan=dict(target=str(target),staged=str(root/'.starpower-incoming-1'),previous=str(root/'.starpower-previous-1'),
                data=str(root/'data'),exports=str(root/'exports'),health=str(root/'recovery/health'),recovery=str(root/'recovery'),pid=123,host='win32')
            validate_plan(plan)
            for key,value in [('staged',root.parent/'.starpower-incoming-1'),('data',target/'data'),('previous',root/'unrelated')]:
                with self.assertRaises(ValueError):validate_plan({**plan,key:str(value)})

    def test_generation_gate_blocks_only_when_installing(self):
        calls=[]
        @operations.generation_action
        def submit():calls.append(1)
        submit()
        with patch.object(operations,'installing',True):
            with self.assertRaises(ValueError):submit()
        self.assertEqual(calls,[1])

    def test_bridge_exposes_no_history_or_secrets(self):
        bridge=DesktopBridge(object())
        public={n for n in dir(bridge) if not n.startswith('_')}
        self.assertEqual(public,{'update_state','check_update','download_update','cancel_update','install_update','restore_previous','save_update_token','choose_exchange_folder'})

    def test_folder_picker_returns_only_selection_and_supports_cancel(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        window=Mock();bridge=DesktopBridge(SimpleNamespace(window=window))
        with patch.dict('sys.modules',{'webview':SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=20))}):
            window.create_file_dialog.return_value=('C:/My Drive/Tarot',)
            self.assertEqual(bridge.choose_exchange_folder(),'C:/My Drive/Tarot')
            window.create_file_dialog.return_value=None
            self.assertIsNone(bridge.choose_exchange_folder())

    def test_download_checksum_failure_never_extracts(self):
        import httpx
        with tempfile.TemporaryDirectory() as tmp,patch('studio.updates.DATA',Path(tmp)/'data'):
            updater=DesktopUpdates(None);updater.available=dict(version='2.4.0',asset=dict(id=123,size=3,digest='sha256:'+'0'*64))
            client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'bad')))
            with patch.object(updater,'_client',return_value=client),patch('studio.updates.validate_archive') as extract:
                state=updater.download_update()
                self.assertEqual(state['status'],'error');self.assertIn('checksum',state['message']);extract.assert_not_called()
            self.assertIsNone(updater.prepared)

    def test_private_auth_failure_does_not_expose_credentials(self):
        import httpx
        with tempfile.TemporaryDirectory() as tmp,patch('studio.updates.DATA',Path(tmp)/'data'):
            updater=DesktopUpdates(None)
            client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(401)))
            with patch.object(updater,'_client',return_value=client):
                state=updater.check_update();self.assertIn('read-only token',state['message'])
                self.assertNotIn('Authorization',json.dumps(state))


if __name__=='__main__':unittest.main()
