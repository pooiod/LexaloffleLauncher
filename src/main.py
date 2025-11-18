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

script = """
(function() {
    'use strict';

    window.showSpinner = function() {
        let overlay = document.getElementById('update-spinner-overlay');

        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'update-spinner-overlay';

            overlay.innerHTML = `
                <div class="spinner"></div>
                <p>Checking for updates...</p>
            `;

            document.body.appendChild(overlay);
        }

        overlay.querySelector('p').textContent = 'Checking for updates...';
        overlay.style.display = 'flex';

        setTimeout(() => {
            if (overlay && overlay.querySelector('p')) {
                overlay.querySelector('p').textContent = 'Downloading updates...';
            }
        }, 4000);
    };

    if (window.lexaloffleCustomizerInitialized) {
        runAllLogic();
        return;
    }

    window.lexaloffleCustomizerInitialized = true;

    const STYLE_ID = 'lexaloffle-custom-styles';
    const LOGGED_IN_FORM_SELECTOR = '#account_pulldown_inner > form';

    function saveWithExpiry(key, value, days) {
        const item = {
            value: value,
            expiry: new Date().getTime() + days * 86400000
        };
        localStorage.setItem(key, JSON.stringify(item));
    }

    function loadWithExpiry(key) {
        const itemStr = localStorage.getItem(key);
        if (!itemStr) return null;
        const item = JSON.parse(itemStr);
        if (new Date().getTime() > item.expiry) {
            localStorage.removeItem(key);
            return null;
        }
        return item.value;
    }

    function loadCachedData() {
        try {
            const cachedApps = loadWithExpiry('cachedAppsData');
            const cachedConfigs = loadWithExpiry('appsWithConfigs');

            if (cachedApps) appCardHandlerThingy(cachedApps);
            if (cachedConfigs) addConfigButtons(cachedConfigs);
        } catch (e) {
            localStorage.clear();
        }
    }

    function createPopup() {
        if (document.getElementById('relaunch-popup-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'relaunch-popup-overlay';

        overlay.innerHTML = `
            <div class="popup-box">
                <h2>Updates Required</h2>
                <p>Please restart the launcher to allow pending updates to complete.</p>
                <button id="popup-close-btn" class="custom-btn primary">OK</button>
            </div>
        `;

        document.body.appendChild(overlay);

        document
            .getElementById('popup-close-btn')
            .addEventListener('click', hideRelaunchPopup);
    }

    function runAllLogic() {
        if (window.location.href.includes('games.php?page=updates')) {
            window.location.href = '/';
            return;
        }

        injectGlobalStyles();
        createPopup();
        loadCachedData();
        handleHumbleIframes();
        interceptDownloadLinks();

        const loggedInForm = document.querySelector(LOGGED_IN_FORM_SELECTOR);

        if (loggedInForm) {
            injectAppButtons();
            const logoutButton = loggedInForm.querySelector('input.logininput2');
            if (logoutButton && !logoutButton.dataset.logoutListenerAdded) {
                logoutButton.addEventListener('click', () => {
                    localStorage.clear();
                });
                logoutButton.dataset.logoutListenerAdded = 'true';
            }
            if (!loadWithExpiry('appsWithConfigs')) checkForConfigs();
        }
    }

    function handleHumbleIframes() {
        document.querySelectorAll('iframe[src*="humblebundle.com"]').forEach(iframe => {
            if (iframe.dataset.humbleProcessed) return;

            iframe.dataset.humbleProcessed = 'true';
            iframe.style.display = 'none';

            const button = document.createElement('button');
            button.className = 'custom-btn humble-button';
            button.textContent = 'Buy on Humble Bundle';
            button.onclick = () => pywebview.api.open_in_browser(iframe.src);

            iframe.parentNode.insertBefore(button, iframe);
        });
    }

    function interceptDownloadLinks() {
        document.body.addEventListener(
            'click',
            e => {
                const link = e.target.closest('a');
                if (!link || !link.href) return;

                const url = link.href.toLowerCase();

                if (
                    url.endsWith('.zip') ||
                    url.endsWith('.exe') ||
                    url.endsWith('.msi') ||
                    url.endsWith('.png')
                ) {
                    e.preventDefault();
                    pywebview.api.open_in_browser(link.href);
                }
            },
            true
        );
    }

    function injectGlobalStyles() {
        if (document.getElementById(STYLE_ID)) return;

        const isIndex = window.location.pathname === '/';
        const banner = document.getElementById('banner');

        let layoutStyles = `
            .topmenu_div#m {
                background: #202020 !important;
            }
            a[href="/games.php?page=updates"] {
                display: none !important;
            }
        `;

        if (banner && banner.style.height == '25vh') {
            layoutStyles += `
                #banner {
                    height: 48px !important;
                }

                .topmenu_div#m {
                    transform: translate(0, 48px) !important;
                }
            `;
        }

        const desktopDivStyles = isIndex
            ? `
                .desktop_div > div {
                    display: flex !important;
                    justify-content: center !important;
                    align-items: flex-start !important;
                    flex-wrap: wrap !important;
                    gap: 25px !important;
                    width: 100% !important;
                    margin: 0 !important;
                }

                .desktop_div > div > div {
                    float: none !important;
                    width: 300px !important;
                    margin: 0 !important;
                    position: relative !important;
                    overflow: hidden !important;
                }
            `
            : '';

        const style = document.createElement('style');
        style.id = STYLE_ID;

        style.textContent = `
            ::-webkit-scrollbar {
                width: 12px !important;
                height: 12px !important;
            }

            ::-webkit-scrollbar-track {
                background: #202020 !important;
            }

            ::-webkit-scrollbar-thumb {
                background-color: #555 !important;
                border-radius: 6px !important;
                border: 3px solid #202020 !important;
            }

            ${layoutStyles}
            ${desktopDivStyles}

            .custom-button-container {
                position: absolute !important;
                bottom: 0;
                left: 0;
                right: 0;
                background: linear-gradient(
                    to top,
                    rgba(0, 0, 0, 0.8),
                    rgba(0, 0, 0, 0.5),
                    transparent
                ) !important;
                padding: 15px !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 10px !important;
                align-items: center !important;
                opacity: 0 !important;
                visibility: hidden !important;
                transform: translateY(20px) !important;
                transition:
                    opacity 0.2s ease,
                    visibility 0.2s ease,
                    transform 0.2s ease !important;
            }

            .desktop_div > div > div:hover .custom-button-container {
                opacity: 1 !important;
                visibility: visible !important;
                transform: translateY(0) !important;
            }

            .custom-btn {
                width: 80%;
                font-family: 'Source Sans Pro', sans-serif !important;
                font-weight: bold !important;
                font-size: 16px !important;
                color: #fff !important;
                background-color: #4a4a58 !important;
                border: none !important;
                padding: 10px 20px !important;
                cursor: pointer !important;
                text-transform: uppercase !important;
            }

            .custom-btn.primary {
                background-color: #ff004d !important;
            }

            .humble-button {
                width: auto !important;
                margin: 20px auto !important;
                display: block !important;
            }

            #update-spinner-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: #1D1D22;
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                color: white;
                flex-direction: column;
            }

            #update-spinner-overlay .spinner {
                border: 8px solid #555;
                border-top: 8px solid #ff004d;
                border-radius: 50%;
                width: 60px;
                height: 60px;
                animation: spin 1s linear infinite;
            }

            #update-spinner-overlay p {
                font-family: 'Source Sans Pro', sans-serif;
                font-size: 1.2em;
                margin-top: 20px;
            }

            @keyframes spin {
                0% {
                    transform: rotate(0deg);
                }

                100% {
                    transform: rotate(360deg);
                }
            }

            .card-launching {
                animation: launch-press 0.3s ease-out forwards !important;
            }

            @keyframes launch-press {
                0% {
                    transform: scale(1);
                }

                50% {
                    transform: scale(0.97);
                }

                100% {
                    transform: scale(1);
                }
            }

            #relaunch-popup-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.7);
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.2s ease;
            }

            #relaunch-popup-overlay.visible {
                display: flex;
                opacity: 1;
            }

            .popup-box {
                background-color: #2a2a34;
                color: #d8d8d8;
                padding: 25px 35px;
                border-radius: 5px;
                text-align: center;
                max-width: 400px;
                border-top: 3px solid #ff004d;
            }

            .popup-box h2 {
                margin: 0 0 10px 0;
            }

            .popup-box p {
                margin: 0 0 20px 0;
                line-height: 1.5;
                color: #bbb;
            }
        `;

        document.head.appendChild(style);
    }

    window.showRelaunchPopup = function() {
        document
            .getElementById('relaunch-popup-overlay')
            .classList.add('visible');
    };

    window.hideRelaunchPopup = function() {
        document
            .getElementById('relaunch-popup-overlay')
            .classList.remove('visible');
    };

    window.launchAnimationAndApp = async function(button, appName) {
        const card = button.closest('.desktop_div > div > div');

        if (card) card.classList.add('card-launching');

        const success = await pywebview.api.launch_app(appName);

        if (!success) showRelaunchPopup();

        if (card) {
            setTimeout(() => {
                card.classList.remove('card-launching');
            }, 400);
        }
    };

    function injectAppButtons() {
        if (window.location.pathname !== '/') return;

        document.querySelectorAll('.desktop_div > div > div').forEach(card => {
            if (card.querySelector('.custom-button-container')) return;

            const title = card.querySelector('h1');
            const productLink = card.querySelector('a');

            if (!title || !productLink) return;

            const name = title.textContent.trim();

            const container = document.createElement('div');
            container.className = 'custom-button-container';

            container.innerHTML = `
                <button class="custom-btn primary"
                    onclick="launchAnimationAndApp(this, '${name}')">
                    Launch
                </button>

                <button class="custom-btn"
                    onclick="window.location.href='${productLink.getAttribute(
                        'href'
                    )}'">
                    View Page
                </button>
            `;

            card.appendChild(container);
        });
    }

    async function checkForConfigs() {
        if (window.location.pathname !== '/') return;

        const appNames = Array.from(
            document.querySelectorAll('.desktop_div > div > div h1')
        ).map(h1 => h1.textContent.trim());

        if (appNames.length > 0) {
            const appsWithConfigs = await pywebview.api.check_for_configs(
                appNames
            );

            saveWithExpiry('appsWithConfigs', appsWithConfigs, 3);
            addConfigButtons(appsWithConfigs);
        }
    }

    function addConfigButtons(appsWithConfigs) {
        if (window.location.pathname !== '/') return;

        document.querySelectorAll('.desktop_div > div > div').forEach(card => {
            const title = card.querySelector('h1');
            if (!title) return;

            const name = title.textContent.trim();

            if (appsWithConfigs.includes(name)) {
                const container = card.querySelector('.custom-button-container');

                if (container && !container.querySelector('.config-btn')) {
                    const btn = document.createElement('button');
                    btn.className = 'custom-btn config-btn';
                    btn.textContent = 'Config';
                    btn.onclick = () =>
                        pywebview.api.open_config_editor(name);

                    container.appendChild(btn);
                }
            }
        });
    }

    window.appCardHandlerThingy = function(appsData) {
        if (window.location.pathname !== '/') return;

        saveWithExpiry('cachedAppsData', appsData, 3);

        const container = document.querySelector('.desktop_div > div');
        if (!container) return;

        const existingTitles = new Set(
            Array.from(container.querySelectorAll('h1')).map(h => h.textContent.trim())
        );

        appsData.forEach(app => {
            if (existingTitles.has(app.name)) return;

            const card = document.createElement('div');

            card.innerHTML = `
                <h1>${app.name}</h1>
                <a href="${app.page_url}">
                    <img src="${app.img_src}" style="width:100%">
                </a>
            `;

            container.appendChild(card);
        });

        injectAppButtons();
    };

    window.hideSpinner = function() {
        const overlay = document.getElementById('update-spinner-overlay');
        if (overlay) overlay.style.display = 'none';
    };

    runAllLogic();

    const observer = new MutationObserver(runAllLogic);
    observer.observe(document.body, { childList: true, subtree: true });
})();
"""

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
    # script = os.path.join(APP_BASE_DIR, 'script.js')
    try:
        # with open(script, 'r', encoding='utf-8') as f:
        #     window.evaluate_js(f.read())
        window.evaluate_js(script)
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
