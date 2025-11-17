(function() {
    'use strict';
    if (window.lexaloffleCustomizerInitialized) {
        runAllLogic();
        return;
    }
    window.lexaloffleCustomizerInitialized = true;

    const STYLE_ID = 'lexaloffle-custom-styles';
    const LOGGED_OUT_FORM_SELECTOR = '#account_pulldown_inner > div > form';
    const LOGGED_IN_FORM_SELECTOR = '#account_pulldown_inner > form';

    let wasPreviouslyLoggedIn = document.querySelector(LOGGED_IN_FORM_SELECTOR) !== null;

    function saveWithExpiry(key, value, days) {
        const now = new Date();
        const item = { value: value, expiry: now.getTime() + (days * 24 * 60 * 60 * 1000) }
        localStorage.setItem(key, JSON.stringify(item));
    }

    function loadWithExpiry(key) {
        const itemStr = localStorage.getItem(key);
        if (!itemStr) return null;
        const item = JSON.parse(itemStr);
        const now = new Date();
        if (now.getTime() > item.expiry) {
            localStorage.removeItem(key);
            return null;
        }
        return item.value;
    }

    function loadCachedData() {
        const cachedApps = loadWithExpiry('cachedAppsData');
        const cachedConfigs = loadWithExpiry('appsWithConfigs');
        try {
            if (cachedApps) ensureAppCards(cachedApps);
            if (cachedConfigs) addConfigButtons(cachedConfigs);
        } catch(e) { localStorage.clear(); }
    }

    function runAllLogic() {
        if (window.location.href.includes('games.php?page=updates')) {
            window.location.href = '/'; return;
        }
        injectGlobalStyles();
        loadCachedData();
        handleHumbleIframes();
        const loggedOutForm = document.querySelector(LOGGED_OUT_FORM_SELECTOR);
        const loggedInForm = document.querySelector(LOGGED_IN_FORM_SELECTOR);
        
        if (loggedInForm) {
            if (!wasPreviouslyLoggedIn) {
                pywebview.api.handle_first_login();
            }
            wasPreviouslyLoggedIn = true;
            injectAppButtons();
            handleLogoutButton(loggedInForm);
            if (!loadWithExpiry('appsWithConfigs')) {
                checkForConfigs();
            }
        } else if (loggedOutForm) {
            wasPreviouslyLoggedIn = false;
            handleLoginForm(loggedOutForm);
        }
    }

    async function handleLoginForm(form) {
        if (window.location.href.includes('account.php?page=login_failed')) {
            setupDataSaving(form); return;
        }
        const savedData = await pywebview.api.load_form_data();
        if (savedData) {
            let formPopulated = false;
            for (const key in savedData) {
                if (form.elements[key]) {
                    form.elements[key].value = savedData[key]; formPopulated = true;
                }
            }
            if (formPopulated) { form.submit(); return; }
        }
        setupDataSaving(form);
    }

    function handleLogoutButton(form) {
        const logoutButton = form.querySelector('input.logininput2');
        if (logoutButton && !logoutButton.dataset.logoutListenerAdded) {
            logoutButton.addEventListener('click', () => {
                localStorage.clear();
                pywebview.api.delete_credentials();
            });
            logoutButton.dataset.logoutListenerAdded = 'true';
        }
    }

    function setupDataSaving(form) {
         form.addEventListener('input', () => {
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            pywebview.api.save_form_data(data);
        });
    }

    function handleHumbleIframes() {
        document.querySelectorAll('iframe[src*="humblebundle.com"]').forEach(iframe => {
            if (iframe.dataset.humbleProcessed) return;
            iframe.dataset.humbleProcessed = 'true';
            iframe.style.display = 'none';
            const button = document.createElement('button');
            button.className = 'custom-btn humble-button';
            button.textContent = 'Open Humble Bundle Content in Browser';
            button.onclick = () => pywebview.api.open_in_browser(iframe.src);
            iframe.parentNode.insertBefore(button, iframe);
        });
    }

    function injectGlobalStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const isIndexPage = window.location.pathname === '/';
        const banner = document.getElementById('banner');
        
        let layoutStyles = `.topmenu_div#m { background: #202020 !important; }`;
        if (banner && banner.style.height == '25vh') {
             layoutStyles += `
                #banner { height: 48px !important; }
                .topmenu_div#m { transform: translate(0, 48px) !important; }
            `;
        }

        const desktopDivStyles = isIndexPage ? `
            .desktop_div > div { display: flex !important; justify-content: center !important; align-items: flex-start !important; flex-wrap: wrap !important; gap: 25px !important; width: 100% !important; margin: 0 !important; }
            .desktop_div > div > div { float: none !important; width: 300px !important; margin: 0 !important; position: relative !important; overflow: hidden !important; }
        ` : '';
        
        const style = document.createElement('style'); style.id = STYLE_ID;
        style.textContent = `
            ::-webkit-scrollbar { width: 12px !important; height: 12px !important; }
            ::-webkit-scrollbar-track { background: #202020 !important; }
            ::-webkit-scrollbar-thumb { background-color: #555 !important; border-radius: 6px !important; border: 3px solid #202020 !important; }
            ${layoutStyles}
            ${desktopDivStyles}
            .custom-button-container {
                position: absolute !important; bottom: 0; left: 0; right: 0;
                background: linear-gradient(to top, rgba(0,0,0,0.8), rgba(0,0,0,0.5), transparent) !important;
                padding: 15px !important; display: flex !important; flex-direction: column !important;
                gap: 10px !important; align-items: center !important;
                opacity: 0 !important; visibility: hidden !important;
                transform: translateY(20px) !important;
                transition: opacity 0.2s ease, visibility 0.2s ease, transform 0.2s ease !important;
            }
            .desktop_div > div > div:hover .custom-button-container {
                opacity: 1 !important; visibility: visible !important; transform: translateY(0) !important;
            }
            .custom-btn { width: 80%; font-family: 'Source Sans Pro', sans-serif !important; font-weight: bold !important; font-size: 16px !important; color: #fff !important; background-color: #4a4a58 !important; border: none !important; padding: 10px 20px !important; cursor: pointer !important; text-transform: uppercase !important; }
            .custom-btn.primary { background-color: #ff004d !important; }
            .humble-button { width: auto !important; margin: 20px auto !important; display: block !important; }
            #update-spinner-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #1D1D22; display: none; justify-content: center; align-items: center; z-index: 9999; color: white; flex-direction: column; }
            #update-spinner-overlay .spinner { border: 8px solid #555; border-top: 8px solid #ff004d; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; }
            #update-spinner-overlay p { font-family: 'Source Sans Pro', sans-serif; font-size: 1.2em; margin-top: 20px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            
            .card-launching { animation: launch-subtle 0.4s ease-out !important; }
            @keyframes launch-subtle {
                0% { transform: scale(1); filter: brightness(1); }
                50% { transform: scale(0.97); filter: brightness(0.8); }
                100% { transform: scale(1); filter: brightness(1); }
            }
        `;
        document.head.appendChild(style);
    }

    window.launchAnimationAndApp = function(button, appName) {
        const card = button.closest('.desktop_div > div > div');
        if (card) {
            card.classList.add('card-launching');
            setTimeout(() => { pywebview.api.launch_app(appName); }, 200);
            setTimeout(() => { card.classList.remove('card-launching'); }, 500);
        } else {
            pywebview.api.launch_app(appName);
        }
    }

    function injectAppButtons() {
        if (window.location.pathname !== '/') return;
        document.querySelectorAll('.desktop_div > div > div').forEach(card => {
            if (card.querySelector('.custom-button-container')) return;
            const h1 = card.querySelector('h1');
            const productLink = card.querySelector('a');
            if (!h1 || !productLink) return;
            const appName = h1.textContent.trim();
            const productPageUrl = productLink.getAttribute('href');
            const container = document.createElement('div');
            container.className = 'custom-button-container';
            container.innerHTML = `
                <button class="custom-btn primary" onclick="launchAnimationAndApp(this, '${appName}')">Launch</button>
                <button class="custom-btn" onclick="window.location.href='${productPageUrl}'">View Page</button>
            `;
            card.appendChild(container);
        });
    }

    async function checkForConfigs() {
        if (window.location.pathname !== '/') return;
        const appNames = Array.from(document.querySelectorAll('.desktop_div > div > div h1')).map(h1 => h1.textContent.trim());
        if (appNames.length > 0) {
            const appsWithConfigs = await pywebview.api.check_for_configs(appNames);
            saveWithExpiry('appsWithConfigs', appsWithConfigs, 3);
            addConfigButtons(appsWithConfigs);
        }
    }

    function addConfigButtons(appsWithConfigs) {
        if (window.location.pathname !== '/') return;
        document.querySelectorAll('.desktop_div > div > div').forEach(card => {
            const h1 = card.querySelector('h1');
            if (h1 && appsWithConfigs.includes(h1.textContent.trim())) {
                const container = card.querySelector('.custom-button-container');
                if (container && !container.querySelector('.config-btn')) {
                    const configBtn = document.createElement('button');
                    configBtn.className = 'custom-btn config-btn';
                    configBtn.textContent = 'Config';
                    configBtn.onclick = () => pywebview.api.open_config_editor(h1.textContent.trim());
                    container.appendChild(configBtn);
                }
            }
        });
    }
    
    window.ensureAppCards = function(appsData) {
        if (window.location.pathname !== '/') return;
        saveWithExpiry('cachedAppsData', appsData, 3);
        const container = document.querySelector('.desktop_div > div');
        if (!container) return;
        const existingTitles = new Set(Array.from(container.querySelectorAll('h1')).map(h1 => h1.textContent.trim()));
        appsData.forEach(app => {
            if (existingTitles.has(app.name)) return;
            const card = document.createElement('div');
            card.style.cssText = 'float: none !important; width: 300px !important; margin: 0 !important; position: relative !important; overflow: hidden !important;';
            card.innerHTML = `<h1>${app.name}</h1><a href="${app.page_url}"><img src="${app.img_src}" style="width:100%"></a>`;
            container.appendChild(card);
        });
        injectAppButtons();
    }

    window.showSpinner = function() {
        let overlay = document.getElementById('update-spinner-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'update-spinner-overlay';
            overlay.innerHTML = `<div class="spinner"></div><p>Checking for Updates...</p>`;
            document.body.appendChild(overlay);
        }
        overlay.querySelector('p').textContent = 'Checking for Updates...';
        overlay.style.display = 'flex';
    }

    window.hideSpinner = function() {
        const overlay = document.getElementById('update-spinner-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    runAllLogic();
    const observer = new MutationObserver(runAllLogic);
    observer.observe(document.body, { childList: true, subtree: true });
})();
