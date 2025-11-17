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
import uuid
import hashlib

# Generate XOR key based on hardware ID
# To lock user login data per-device
hw = str(uuid.getnode()).encode()
XOR_KEY = hashlib.sha256(hw).hexdigest()[:12]

storage_path = os.path.join(os.path.join(os.path.expanduser("~"), "Documents"), 'LexaloffleLauncher')
if not os.path.isdir(storage_path):
    os.makedirs(storage_path)

if getattr(sys, 'frozen', False):
    APP_BASE_DIR = os.path.dirname(sys.executable)
else:
    APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = storage_path

def encode_data(data_dict):
    if not data_dict:
        return ""
    data_json = json.dumps(data_dict).encode('utf-8')
    xored = bytes([b ^ ord(XOR_KEY[i % len(XOR_KEY)]) for i, b in enumerate(data_json)])
    return base64.b64encode(xored).decode('utf-8')

def decode_data(encoded_str):
    if not encoded_str:
        return None
    try:
        xored = base64.b64decode(encoded_str)
        decoded_bytes = bytes([b ^ ord(XOR_KEY[i % len(XOR_KEY)]) for i, b in enumerate(xored)])
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        return None


def get_app_data_path(app_name, get_dir=False):
    base = os.getenv('APPDATA')
    key = re.split(r'[-\s]', app_name)[0].lower()
    try:
        found_dir = next(
            (os.path.join(base, name) for name in os.listdir(base)
             if re.split(r'[-\s]', name)[0].lower() == key),
            None
        )
    except (FileNotFoundError, TypeError):
        found_dir = None

    final_dir = found_dir if found_dir else os.path.join(base, key)
    return final_dir if get_dir else os.path.join(final_dir, 'config.txt')


class Api:
    def save_form_data(self, form_data):
        encoded_data = encode_data(form_data)
        path = os.path.join(BASE_DIR, 'dat.bin')
        with open(path, 'w') as f:
            f.write(encoded_data)

    def load_form_data(self):
        path = os.path.join(BASE_DIR, 'dat.bin')
        if os.path.exists(path):
            with open(path, 'r') as f:
                return decode_data(f.read())
        return None

    def delete_credentials(self):
        path = os.path.join(BASE_DIR, 'dat.bin')
        if os.path.exists(path):
            os.remove(path)

    def launch_app(self, app_name):
        app_folder_name = re.split(r'[-\s]', app_name)[0].lower()
        app_dir = os.path.join(BASE_DIR, 'apps', app_folder_name)

        def on_fail():
            # if 'pico-8' in app_name.lower():
            #     self.open_in_browser('https://www.pico-8-edu.com/')
            return False

        if not os.path.isdir(app_dir):
            return on_fail()

        exe_file = next((f for f in os.listdir(app_dir) if f.endswith('.exe')), None)
        if exe_file:
            subprocess.Popen([os.path.join(app_dir, exe_file)], cwd=app_dir)
            return True
        return on_fail()

    def check_for_configs(self, app_names):
        return [name for name in app_names if os.path.exists(get_app_data_path(name))]

    def read_config_file(self, app_name):
        path = get_app_data_path(app_name)
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: Could not find config file for {app_name}."

    def save_config_file(self, app_name, content):
        path = get_app_data_path(app_name)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return True
        except Exception:
            return False

    def open_config_editor(self, app_name):
        html = os.path.join(APP_BASE_DIR, 'editor.html')
        w = webview.create_window(f'{app_name} - Config Editor', url=html, width=700, height=500, js_api=self)

        def on_loaded():
            w.evaluate_js(f'window.currentApp = "{app_name}"; loadContent();')

        w.events.loaded += on_loaded

    def reset_config_file(self, app_name):
        path = get_app_data_path(app_name)
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            return False

    def open_user_data_folder(self, app_name):
        folder = get_app_data_path(app_name, get_dir=True)
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception as e:
            print(f"Error opening user data folder for {app_name}: {e}")

    def open_in_browser(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Failed to open URL in browser: {e}")


def process_downloads_page(html_content, main_window):
    if not isinstance(html_content, str) or not html_content:
        return

    versions_file = os.path.join(BASE_DIR, 'versions.json')
    apps_dir = os.path.join(BASE_DIR, 'apps')

    apps_data = []
    updates = []

    try:
        local_versions = json.load(open(versions_file, 'r')) if os.path.exists(versions_file) else {}

        blocks = html_content.split('<div style="display:table; width:100%; margin-bottom:40px">')
        for block in blocks[1:]:
            name_ver = re.search(r'<b>(.*?) .*? v([\d\w\.]+)</b>', block)
            img = re.search(r'<img src="([^"]+)"', block)
            link = re.search(r'<div style="float:left.*?<a href="([^"]+)"', block, re.DOTALL)
            zip_link = re.search(r'href="([^"]+_windows\.zip)"', block)

            if name_ver and img and link and zip_link:
                full_name, remote_version = name_ver.groups()
                img_src = f"https://www.lexaloffle.com/{img.group(1).strip()}"
                page_url = f"https://www.lexaloffle.com/{link.group(1).strip()}"
                zip_url = f"https://www.lexaloffle.com{zip_link.group(1).strip()}"

                folder = re.split(r'[-\s]', full_name)[0].lower()
                apps_data.append({
                    'name': full_name,
                    'img_src': img_src,
                    'page_url': page_url
                })

                local_version = local_versions.get(folder, '0.0.0')
                if LooseVersion(remote_version) > LooseVersion(local_version):
                    updates.append({
                        'url': zip_url,
                        'folder': folder,
                        'version': remote_version,
                        'name': full_name
                    })

        if apps_data:
            main_window.evaluate_js(f'appCardHandlerThingy({json.dumps(apps_data)})')

        for app in updates:
            resp = requests.get(app['url'])
            resp.raise_for_status()

            temp = os.path.join(apps_dir, '_temp_unzip')
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                z.extractall(temp)

            src = os.path.join(temp, os.listdir(temp)[0])
            dst = os.path.join(apps_dir, app['folder'])

            if os.path.isdir(dst):
                shutil.rmtree(dst)

            shutil.move(src, dst)
            shutil.rmtree(temp)

            local_versions[app['folder']] = app['version']
            with open(versions_file, 'w') as f:
                json.dump(local_versions, f, indent=4)

    except Exception as e:
        print(f"[Updater] An error occurred: {e}")


process_complete_event = threading.Event()

def run_update_check_in_background(main_window):
    global updater_login_attempted
    updater_login_attempted = False

    path = os.path.join(BASE_DIR, 'dat.bin')
    if not os.path.exists(path):
        return

    with open(path, 'r') as f:
        saved = decode_data(f.read())

    if not saved:
        return

    try:
        try:
            main_window.evaluate_js('showSpinner()')
        except Exception:
            pass

        def loaded(win):
            global updater_login_attempted

            if not updater_login_attempted:
                updater_login_attempted = True

                js = f"""
                (function() {{
                    const form = document.querySelector('#account_pulldown_inner > div > form');
                    const data = {json.dumps(saved)};
                    const url = 'https://www.lexaloffle.com/games.php?page=updates';
                    if (form && data) {{
                        for (const k in data) {{
                            if (form.elements[k]) form.elements[k].value = data[k];
                        }}
                        const go = form.querySelector('input[name="go"]');
                        if (go) go.value = url;
                        form.submit();
                    }}
                }})();
                """

                win.evaluate_js(js)
            else:
                time.sleep(2)
                html = win.evaluate_js('document.documentElement.outerHTML')
                process_downloads_page(html, main_window)
                win.destroy()
                process_complete_event.set()

        url = 'https://www.lexaloffle.com/games.php?page=updates'
        w = webview.create_window('Updater', url=url, hidden=True)
        w.events.loaded += lambda: loaded(w)

        process_complete_event.wait()

    finally:
        try:
            main_window.evaluate_js('hideSpinner()')
        except Exception:
            pass
        try:
            main_window.evaluate_js('window.location.reload()')
        except Exception:
            pass


api = Api()

os.makedirs(storage_path, exist_ok=True)

window = webview.create_window(
    'Lexaloffle Launcher',
    url='https://www.lexaloffle.com',
    width=1280,
    height=800,
    js_api=api
)


def on_loaded():
    script = os.path.join(APP_BASE_DIR, 'script.js')
    try:
        with open(script, 'r', encoding='utf-8') as f:
            window.evaluate_js(f.read())
    except FileNotFoundError:
        print(f"CRITICAL ERROR: script.js not found at {script}")


window.events.loaded += on_loaded

threading.Timer(
    2.0,
    lambda: threading.Thread(
        target=run_update_check_in_background,
        args=(window,),
        daemon=True
    ).start()
).start()

webview.start(debug=False, gui='edgechromium')
