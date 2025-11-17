import webview
import os
import subprocess
import sys
import base64
import json
import threading
import requests
import re
import io
import zipfile
import time
import shutil
import webbrowser
from distutils.version import LooseVersion

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

XOR_KEY = 'a9b8c7d6e5f4'
def encode_data(data_dict):
    if not data_dict: return ""
    data_json = json.dumps(data_dict).encode('utf-8')
    xored = bytes([b ^ ord(XOR_KEY[i % len(XOR_KEY)]) for i, b in enumerate(data_json)])
    return base64.b64encode(xored).decode('utf-8')
def decode_data(encoded_str):
    if not encoded_str: return None
    try:
        xored = base64.b64decode(encoded_str)
        decoded_bytes = bytes([b ^ ord(XOR_KEY[i % len(XOR_KEY)]) for i, b in enumerate(xored)])
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception: return None

def get_app_data_path(app_name, get_dir=False):
    base = os.getenv('APPDATA')
    key = re.split(r'[-\s]', app_name)[0].lower()
    try:
        for name in os.listdir(base):
            if re.split(r'[-\s]', name)[0].lower() == key:
                found_dir = os.path.join(base, name)
                break
        else: found_dir = None
    except (FileNotFoundError, TypeError): found_dir = None
    final_dir = found_dir if found_dir else os.path.join(base, key)
    return final_dir if get_dir else os.path.join(final_dir, 'config.txt')

needs_restart = False

class Api:
    def __init__(self, window, is_first_run=False):
        self.window = window
        self.is_first_run = is_first_run
    
    # --- NEW FUNCTION TO HANDLE FIRST LOGIN RESTART ---
    def handle_first_login(self):
        if self.is_first_run:
            global needs_restart
            needs_restart = True
            print("First login detected on a fresh run. Triggering application restart...")
            self.window.destroy()

    def save_form_data(self, form_data):
        encoded_data = encode_data(form_data)
        creds_path = os.path.join(BASE_DIR, 'dat.bin')
        with open(creds_path, 'w') as f: f.write(encoded_data)
    def load_form_data(self):
        creds_path = os.path.join(BASE_DIR, 'dat.bin')
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f: encoded_data = f.read()
            return decode_data(encoded_data)
        return None
    def delete_credentials(self):
        creds_path = os.path.join(BASE_DIR, 'dat.bin')
        if os.path.exists(creds_path): os.remove(creds_path)
    def launch_app(self, app_name):
        app_folder_name = re.split(r'[-\s]', app_name)[0].lower()
        app_dir = os.path.join(BASE_DIR, 'apps', app_folder_name)
        if not os.path.isdir(app_dir): return
        exe_file = next((f for f in os.listdir(app_dir) if f.endswith(".exe")), None)
        if exe_file: subprocess.Popen([os.path.join(app_dir, exe_file)], cwd=app_dir)
    def check_for_configs(self, app_names):
        apps_with_configs = []
        for name in app_names:
            if os.path.exists(get_app_data_path(name)):
                apps_with_configs.append(name)
        return apps_with_configs
    def read_config_file(self, app_name):
        config_path = get_app_data_path(app_name)
        try:
            with open(config_path, 'r') as f: return f.read()
        except FileNotFoundError: return f"Error: Could not find config file for {app_name}."
    def save_config_file(self, app_name, content):
        config_path = get_app_data_path(app_name)
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f: f.write(content)
            return True
        except Exception: return False
    def open_config_editor(self, app_name):
        editor_html_path = os.path.join(BASE_DIR, 'editor.html')
        editor_window = webview.create_window(f'{app_name} - Config Editor', url=editor_html_path, width=700, height=500, js_api=self)
        def on_loaded(): editor_window.evaluate_js(f'window.currentApp = "{app_name}"; loadContent();')
        editor_window.events.loaded += on_loaded
    def reset_config_file(self, app_name):
        config_path = get_app_data_path(app_name)
        try:
            if os.path.exists(config_path): os.remove(config_path)
            return True
        except Exception: return False
    def open_user_data_folder(self, app_name):
        folder_path = get_app_data_path(app_name, get_dir=True)
        try:
            os.makedirs(folder_path, exist_ok=True)
            if sys.platform == 'win32': os.startfile(folder_path)
            elif sys.platform == 'darwin': subprocess.call(['open', folder_path])
            else: subprocess.call(['xdg-open', folder_path])
        except Exception as e: print(f"Error opening user data folder: {e}")
    def open_in_browser(self, url):
        try: webbrowser.open(url)
        except Exception as e: print(f"Failed to open URL in browser: {e}")

process_complete_event = threading.Event()
# ... (All updater functions are unchanged from the previous version)
def process_downloads_page(html_content, main_window):
    if not isinstance(html_content, str) or not html_content: return
    versions_file = os.path.join(BASE_DIR, 'versions.json')
    apps_dir = os.path.join(BASE_DIR, 'apps')
    apps_data_for_js, apps_to_update = [], []
    try:
        local_versions = json.load(open(versions_file, 'r')) if os.path.exists(versions_file) else {}
        product_blocks = html_content.split('<div style="display:table; width:100%; margin-bottom:40px">')
        for block in product_blocks[1:]:
            name_ver_match = re.search(r'<b>(.*?) .*? v([\d\w\.]+)</b>', block)
            img_match = re.search(r'<img src="([^"]+)"', block)
            page_url_match = re.search(r'<div style="float:left.*?<a href="([^"]+)"', block, re.DOTALL)
            zip_link_match = re.search(r'href="([^"]+_windows\.zip)"', block)
            if name_ver_match and img_match and page_url_match and zip_link_match:
                full_name, remote_version = name_ver_match.groups()
                img_src = f"https://www.lexaloffle.com/{img_match.group(1).strip()}"
                page_url = f"https://www.lexaloffle.com/{page_url_match.group(1).strip()}"
                zip_link = f"https://www.lexaloffle.com{zip_link_match.group(1).strip()}"
                app_folder_name = re.split(r'[-\s]', full_name)[0].lower()
                apps_data_for_js.append({'name': full_name, 'img_src': img_src, 'page_url': page_url})
                local_version = local_versions.get(app_folder_name, '0.0.0')
                if LooseVersion(remote_version) > LooseVersion(local_version):
                    apps_to_update.append({'url': zip_link, 'folder': app_folder_name, 'version': remote_version, 'name': full_name})
        try:
            if apps_data_for_js: main_window.evaluate_js(f'ensureAppCards({json.dumps(apps_data_for_js)})')
        except Exception: pass
        if apps_to_update:
            for app in apps_to_update:
                zip_response = requests.get(app['url'])
                zip_response.raise_for_status()
                temp_unzip_dir = os.path.join(apps_dir, '_temp_unzip')
                with zipfile.ZipFile(io.BytesIO(zip_response.content)) as z: z.extractall(temp_unzip_dir)
                source_path = os.path.join(temp_unzip_dir, os.listdir(temp_unzip_dir)[0])
                dest_path = os.path.join(apps_dir, app['folder'])
                if os.path.isdir(dest_path): shutil.rmtree(dest_path)
                shutil.move(source_path, dest_path)
                shutil.rmtree(temp_unzip_dir)
                local_versions[app['folder']] = app['version']
                with open(versions_file, 'w') as f: json.dump(local_versions, f, indent=4)
    except Exception as e: print(f"[Updater] An error occurred: {e}")
def run_update_check_in_background(main_window):
    global updater_login_attempted; updater_login_attempted = False
    creds_path = os.path.join(BASE_DIR, 'dat.bin')
    if not os.path.exists(creds_path): return
    with open(creds_path, 'r') as f: encoded_data = f.read()
    login_credentials = decode_data(encoded_data)
    if not login_credentials: return
    try:
        try: main_window.evaluate_js('showSpinner()')
        except Exception: pass
        def on_updater_loaded(updater_window):
            global updater_login_attempted
            if not updater_login_attempted:
                updater_login_attempted = True
                login_js = f"""(function() {{ const form = document.querySelector('#account_pulldown_inner > div > form'); const savedData = {json.dumps(login_credentials)}; const updatesUrl = 'https://www.lexaloffle.com/games.php?page=updates'; if (form && savedData) {{ for (const key in savedData) {{ if (form.elements[key]) form.elements[key].value = savedData[key]; }} const goInput = form.querySelector('input[name="go"]'); if (goInput) {{ goInput.value = updatesUrl; }} form.submit(); }} }})();"""
                updater_window.evaluate_js(login_js)
            else:
                time.sleep(2)
                html_content = updater_window.evaluate_js('document.documentElement.outerHTML')
                process_downloads_page(html_content, main_window)
                updater_window.destroy()
                process_complete_event.set()
        updates_url = 'https://www.lexaloffle.com/games.php?page=updates'
        updater_window = webview.create_window('Updater', url=updates_url, hidden=True)
        updater_window.events.loaded += lambda: on_updater_loaded(updater_window)
        process_complete_event.wait()
    finally:
        try: main_window.evaluate_js('hideSpinner()')
        except Exception: pass
        try: main_window.evaluate_js('window.location.reload()')
        except Exception: pass

def create_app():
    creds_path = os.path.join(BASE_DIR, 'dat.bin')
    is_first_run = not os.path.exists(creds_path) or os.path.getsize(creds_path) == 0

    start_url = 'https://www.lexaloffle.com'
    storage_path = os.path.join(os.getenv('APPDATA'), 'LexaloffleLauncher')
    os.makedirs(storage_path, exist_ok=True)
    
    window = webview.create_window('Lexaloffle', url=start_url, width=1280, height=800)
    api = Api(window=window, is_first_run=is_first_run)
    window.js_api = api

    def on_loaded():
        script_path = os.path.join(BASE_DIR, 'script.js')
        try:
            with open(script_path, 'r', encoding='utf-8') as f: window.evaluate_js(f.read())
        except FileNotFoundError: print(f"CRITICAL ERROR: script.js not found at {script_path}")
    
    window.events.loaded += on_loaded
    if not is_first_run:
        threading.Timer(2.0, lambda: threading.Thread(target=run_update_check_in_background, args=(window,), daemon=True).start()).start()
    
    webview.start(debug=False, storage_path=storage_path, gui='edgechromium')
    
    if needs_restart:
        os.execv(sys.executable, ['python'] + sys.argv)

if __name__ == '__main__':
    create_app()
