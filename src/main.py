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

storage_path = os.path.join(os.path.join(os.path.expanduser("~"), "Documents"), 'LexaloffleLauncher')
if not os.path.isdir(storage_path):
    os.makedirs(storage_path)

if getattr(sys, 'frozen', False):
    APP_BASE_DIR = os.path.dirname(sys.executable)
else:
    APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = storage_path

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
        pass

    def load_form_data(self):
        return None

    def delete_credentials(self):
        pass

    def get_local_apps(self):
        apps_dir = os.path.join(BASE_DIR, 'apps')
        local_apps = []
        if not os.path.isdir(apps_dir):
            return []

        for folder_name in os.listdir(apps_dir):
            app_path = os.path.join(apps_dir, folder_name)
            if os.path.isdir(app_path):
                has_exe = any(f.endswith('.exe') for f in os.listdir(app_path))
                if not has_exe:
                    continue

                icon_data_uri = None
                for root, _, files in os.walk(app_path):
                    png_files = [f for f in files if f.endswith('.png')]
                    if png_files:
                        try:
                            with open(os.path.join(root, png_files[0]), 'rb') as img_file:
                                encoded = base64.b64encode(img_file.read()).decode('utf-8')
                                icon_data_uri = f"data:image/png;base64,{encoded}"
                            break
                        except Exception:
                            pass

                display_name = folder_name.replace('-', ' ').replace('_', ' ').title()
                real_name = [f[:-4] for f in os.listdir(app_path) if f.lower().endswith('.exe')]
                local_apps.append({'name': display_name, 'icon': icon_data_uri, 'display': real_name})
        return local_apps

    def launch_app(self, app_name):
        app_folder_name = re.split(r'[-\s]', app_name)[0].lower()
        app_dir = os.path.join(BASE_DIR, 'apps', app_folder_name)

        if not os.path.isdir(app_dir):
            return False

        exe_file = next((f for f in os.listdir(app_dir) if f.endswith('.exe')), None)
        if exe_file:
            subprocess.Popen([os.path.join(app_dir, exe_file)], cwd=app_dir)
            return True
        return False

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
    try:
        main_window.evaluate_js('showSpinner()')
    except Exception:
        pass

    try:
        def loaded(win):
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
            main_window.evaluate_js('window.location.reload()')
        except Exception:
            pass

def check_connectivity(url="https://www.lexaloffle.com", timeout=5):
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

api = Api()
is_online = check_connectivity()
start_url = 'https://www.lexaloffle.com' if is_online else 'offline.html'

window = webview.create_window(
    'Lexaloffle Launcher',
    url=start_url,
    width=1280,
    height=800,
    js_api=api
)

def on_loaded():
    if not is_online:
        return
    script = os.path.join(APP_BASE_DIR, 'script.js')
    try:
        with open(script, 'r', encoding='utf-8') as f:
            window.evaluate_js(f.read())
    except FileNotFoundError:
        print(f"CRITICAL ERROR: script.js not found at {script}")

window.events.loaded += on_loaded

if is_online:
    threading.Timer(
        2.0,
        lambda: threading.Thread(
            target=run_update_check_in_background,
            args=(window,),
            daemon=True
        ).start()
    ).start()

webview.start(debug=False, gui='edgechromium', storage_path=storage_path, private_mode=False)
