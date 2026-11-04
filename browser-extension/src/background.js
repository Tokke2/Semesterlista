/**
 * Bakgrundstjänst (service worker).
 *
 * Ansvar:
 *  – skapa PDF:er av fliken via DevTools-protokollet (Page.printToPDF)
 *  – avgöra om en URL tillhör en vald webbplats
 *  – registrera den flytande knappen på beviljade webbplatser
 *  – snabbkommando, högerklicksmeny, badge och historik
 */

import { getSettings, addHistory } from './lib/settings.js';
import { matchesUrl, originPatternFor, isPrintableUrl } from './lib/sites.js';
import { buildFilename } from './lib/filename.js';
import { resolveLang, t } from './lib/i18n.js';

const CONTENT_SCRIPT_ID = 'site-pdf-button';
const CONTENT_FILES = ['src/content.js'];
const MENU_ID = 'page-to-pdf-save';
const BADGE_BUSY = '…';
const BADGE_OK = '✓';
const BADGE_FAIL = '!';

/** Flikar som just nu skriver ut – förhindrar dubbelklick. */
const inFlight = new Map();

class PdfError extends Error {
  constructor(code, detail) {
    super(code);
    this.code = code;
    this.detail = detail;
  }
}

function currentLang(settings) {
  return resolveLang(settings.language, chrome.i18n.getUILanguage());
}

function errorText(lang, code) {
  const known = [
    'restricted',
    'devtools',
    'attach',
    'print',
    'download',
    'notAllowed',
    'noTab',
    'busy',
    'canceled',
    'unexpected'
  ];
  return t(lang, `errors.${known.includes(code) ? code : 'unexpected'}`);
}

function isAllowedUrl(url, settings) {
  if (!isPrintableUrl(url)) return false;
  if (settings.allowAll) return true;
  return settings.sites.some((site) => site.enabled && matchesUrl(url, site.pattern));
}

/* ------------------------------------------------------------------ */
/* Badge och toast                                                     */
/* ------------------------------------------------------------------ */

async function setBadge(tabId, text, color) {
  try {
    await chrome.action.setBadgeText({ tabId, text });
    if (color) await chrome.action.setBadgeBackgroundColor({ tabId, color });
  } catch {
    /* fliken kan ha stängts */
  }
}

function clearBadgeLater(tabId, delay = 2500) {
  setTimeout(() => {
    void setBadge(tabId, '');
  }, delay);
}

async function sendToast(tabId, payload) {
  if (typeof tabId !== 'number') return;
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'TOAST', ...payload });
  } catch {
    /* ingen innehållsskript i fliken – inget att visa */
  }
}

/* ------------------------------------------------------------------ */
/* PDF-generering                                                      */
/* ------------------------------------------------------------------ */

const PAPER_SIZES = {
  A4: [8.27, 11.69],
  Letter: [8.5, 11],
  Legal: [8.5, 14],
  A3: [11.69, 16.54]
};

function printParams(settings) {
  const pdf = settings.pdf;
  const mmToInch = (mm) => Number((mm / 25.4).toFixed(4));
  const margin = mmToInch(pdf.marginMm);
  const [width, height] = PAPER_SIZES[pdf.format] || PAPER_SIZES.A4;

  const params = {
    landscape: false,
    displayHeaderFooter: pdf.headerFooter,
    printBackground: pdf.printBackground,
    scale: pdf.scale,
    marginTop: margin,
    marginBottom: margin,
    marginLeft: margin,
    marginRight: margin,
    preferCSSPageSize: pdf.preferCssPageSize,
    transferMode: 'ReturnAsBase64'
  };

  if (!pdf.preferCssPageSize) {
    params.paperWidth = width;
    params.paperHeight = height;
  }

  if (pdf.headerFooter) {
    params.headerTemplate = '<span></span>';
    params.footerTemplate = `
      <div style="width:100%; padding:0 10mm; font-family:system-ui, sans-serif;
                  font-size:9px; color:#666; text-align:right;">
        <span class="pageNumber"></span> / <span class="totalPages"></span>
      </div>`;
  }

  return params;
}

/**
 * Väntar på att teckensnitt, bilder och lazy-laddat innehåll ska bli klart.
 * Fel här ska aldrig stoppa utskriften.
 */
async function waitForPageReady(target, waitMs) {
  const delay = Math.max(0, Math.min(5000, Number(waitMs) || 0));
  const expression = `(async () => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    try {
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
    } catch (error) { /* ignoreras */ }
    const pending = Array.from(document.images || []).filter((img) => !img.complete).slice(0, 60);
    await Promise.all(pending.map((img) => new Promise((resolve) => {
      img.addEventListener('load', resolve, { once: true });
      img.addEventListener('error', resolve, { once: true });
      setTimeout(resolve, 5000);
    })));
    await sleep(${delay});
    return true;
  })()`;

  try {
    await Promise.race([
      chrome.debugger.sendCommand(target, 'Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true
      }),
      new Promise((resolve) => setTimeout(resolve, 8000))
    ]);
  } catch {
    /* sidan kan sakna Runtime – då hoppar vi bara över väntan */
  }
}

function mapError(error, stage) {
  const message = String(error?.detail || error?.message || error || '');
  if (/another debugger is already attached/i.test(message)) {
    return new PdfError('devtools', message);
  }
  if (/cancel/i.test(message)) {
    return new PdfError('canceled', message);
  }
  if (/cannot access|chrome:\/\/|extension pages|the tab is not|not supported/i.test(message)) {
    return new PdfError('restricted', message);
  }
  if (/no tab with given id|tab was closed/i.test(message)) {
    return new PdfError('noTab', message);
  }
  if (error instanceof PdfError) return error;
  return new PdfError(stage, message);
}

async function printTabToPdf(tabId, settings) {
  const target = { tabId };
  try {
    await chrome.debugger.attach(target, '1.3');
  } catch (error) {
    throw mapError(error, 'attach');
  }

  try {
    await chrome.debugger.sendCommand(target, 'Page.enable');
    await waitForPageReady(target, settings.pdf.waitMs);
    const result = await chrome.debugger.sendCommand(target, 'Page.printToPDF', printParams(settings));
    if (!result || typeof result.data !== 'string' || !result.data) {
      throw new PdfError('print', 'Tomt svar från Page.printToPDF');
    }
    return result.data;
  } catch (error) {
    throw mapError(error, 'print');
  } finally {
    chrome.debugger.detach(target).catch(() => {});
  }
}

const OFFSCREEN_URL = 'src/offscreen.html';

/** Startar det osynliga hjälpdokumentet som kan skapa blob-URL:er. */
async function ensureOffscreenDocument() {
  if (!chrome.offscreen) return false;
  try {
    if (typeof chrome.offscreen.hasDocument === 'function' && (await chrome.offscreen.hasDocument())) {
      return true;
    }
  } catch {
    /* hasDocument kan saknas – försök skapa ändå */
  }
  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ['BLOBS'],
      justification: 'Skapa blob-URL:er så att stora PDF-filer kan sparas utan att trunkeras.'
    });
    return true;
  } catch (error) {
    return /single offscreen|already/i.test(String(error?.message || ''));
  }
}

async function makeBlobUrl(base64) {
  if (!(await ensureOffscreenDocument())) {
    throw new PdfError('download', 'Offscreen-dokumentet kunde inte skapas');
  }
  const response = await new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { target: 'offscreen', type: 'MAKE_BLOB_URL', base64, mime: 'application/pdf' },
      (result) => {
        const error = chrome.runtime.lastError;
        if (error) reject(new PdfError('download', error.message));
        else resolve(result);
      }
    );
  });
  if (!response || !response.url) {
    throw new PdfError('download', response?.error || 'Ingen blob-URL skapades');
  }
  return response.url;
}

function downloadUrl(url, filename, settings) {
  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url,
        filename,
        saveAs: !!settings.file.saveAs,
        conflictAction: 'uniquify'
      },
      (downloadId) => {
        const error = chrome.runtime.lastError;
        if (error || typeof downloadId !== 'number') {
          reject(new PdfError('download', error?.message || 'Inget nedladdnings-id'));
          return;
        }
        resolve(downloadId);
      }
    );
  });
}

async function downloadPdf(base64, filename, settings) {
  try {
    const blobUrl = await makeBlobUrl(base64);
    return await downloadUrl(blobUrl, filename, settings);
  } catch (error) {
    const mapped = mapError(error, 'download');
    // Avbröt användaren spar-dialogen ska vi inte försöka igen.
    if (mapped.code === 'canceled') throw mapped;

    // Reservlösning om offscreen inte fungerar: data-URL, som bara klarar
    // filer under cirka 2 MB (base64).
    if (base64.length < 1400000) {
      try {
        return await downloadUrl(`data:application/pdf;base64,${base64}`, filename, settings);
      } catch (fallbackError) {
        throw mapError(fallbackError, 'download');
      }
    }
    throw mapped;
  }
}

function makeFilename(tab, settings) {
  let site = 'webbplats';
  try {
    site = new URL(tab.url).hostname.replace(/^www\./, '') || 'webbplats';
  } catch {
    /* behåll standardvärdet */
  }
  const title = tab.title || site;
  return buildFilename({
    template: settings.file.template,
    folder: settings.file.folder,
    perSiteFolder: settings.file.perSiteFolder,
    site,
    title,
    date: new Date()
  });
}

/* ------------------------------------------------------------------ */
/* Spara-flödet                                                         */
/* ------------------------------------------------------------------ */

async function runSave(tab) {
  const settings = await getSettings();
  const lang = currentLang(settings);
  const tabId = tab.id;

  if (!isPrintableUrl(tab.url)) {
    const message = errorText(lang, 'restricted');
    await sendToast(tabId, { state: 'error', text: message });
    await setBadge(tabId, BADGE_FAIL, '#b42318');
    clearBadgeLater(tabId, 4000);
    return { ok: false, error: 'restricted', message };
  }

  if (!isAllowedUrl(tab.url, settings)) {
    const message = errorText(lang, 'notAllowed');
    await sendToast(tabId, { state: 'error', text: message });
    await setBadge(tabId, BADGE_FAIL, '#b42318');
    clearBadgeLater(tabId, 4000);
    return { ok: false, error: 'notAllowed', message };
  }

  await setBadge(tabId, BADGE_BUSY, '#6b7280');
  await sendToast(tabId, { state: 'saving', text: t(lang, 'toast.saving') });

  try {
    const base64 = await printTabToPdf(tabId, settings);
    const filename = makeFilename(tab, settings);
    const downloadId = await downloadPdf(base64, filename, settings);

    await addHistory({
      filename,
      url: tab.url,
      title: tab.title || filename,
      downloadId
    });

    await setBadge(tabId, BADGE_OK, '#1f7a44');
    await sendToast(tabId, {
      state: 'saved',
      text: t(lang, 'toast.saved', { file: filename.split('/').pop() })
    });
    clearBadgeLater(tabId);
    return { ok: true, filename, downloadId };
  } catch (error) {
    const mapped = mapError(error, 'unexpected');
    const message = errorText(lang, mapped.code);

    if (mapped.code === 'canceled') {
      // Användaren stängde spar-dialogen – inget fel, bara ingen fil.
      await sendToast(tabId, { state: 'info', text: message });
      clearBadgeLater(tabId, 1500);
      return { ok: false, error: 'canceled', message };
    }

    console.warn('PDF misslyckades:', mapped.code, mapped.detail || '');
    await setBadge(tabId, BADGE_FAIL, '#b42318');
    await sendToast(tabId, { state: 'error', text: message });
    clearBadgeLater(tabId, 5000);
    return { ok: false, error: mapped.code, message };
  }
}

async function handleSaveRequest(tab) {
  if (!tab || typeof tab.id !== 'number') {
    return { ok: false, error: 'noTab', message: t('en', 'errors.noTab') };
  }
  if (inFlight.has(tab.id)) {
    const settings = await getSettings();
    return { ok: false, error: 'busy', message: errorText(currentLang(settings), 'busy') };
  }
  const task = runSave(tab).finally(() => inFlight.delete(tab.id));
  inFlight.set(tab.id, task);
  return task;
}

/* ------------------------------------------------------------------ */
/* Innehållsskript för den flytande knappen                            */
/* ------------------------------------------------------------------ */

async function grantedOriginsFor(settings) {
  if (!settings.button.show) return [];
  const origins = new Set();
  for (const site of settings.sites) {
    if (!site.enabled) continue;
    const origin = originPatternFor(site.pattern);
    if (!origin) continue;
    let granted = false;
    try {
      granted = await chrome.permissions.contains({ origins: [origin] });
    } catch {
      granted = false;
    }
    if (granted) origins.add(origin);
  }
  return [...origins];
}

async function injectIntoOpenTabs(origins) {
  if (!origins.length) return;
  let tabs = [];
  try {
    tabs = await chrome.tabs.query({ url: origins });
  } catch {
    return;
  }
  for (const tab of tabs) {
    if (typeof tab.id !== 'number') continue;
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: CONTENT_FILES });
    } catch {
      /* fliken kan vara en intern sida */
    }
  }
}

let syncTask = Promise.resolve();

/** Registrerar knappen på de webbplatser som användaren gett åtkomst till. */
async function getRegisteredScript() {
  try {
    const list = await chrome.scripting.getRegisteredContentScripts({ ids: [CONTENT_SCRIPT_ID] });
    return Array.isArray(list) ? list[0] || null : null;
  } catch {
    return null;
  }
}

function syncContentScripts({ inject = true } = {}) {
  syncTask = syncTask
    .then(async () => {
      const settings = await getSettings();
      const origins = [...(await grantedOriginsFor(settings))].sort();

      const existing = await getRegisteredScript();
      const unchanged =
        existing !== null &&
        Array.isArray(existing.matches) &&
        JSON.stringify([...existing.matches].sort()) === JSON.stringify(origins);

      if (!unchanged) {
        try {
          await chrome.scripting.unregisterContentScripts({ ids: [CONTENT_SCRIPT_ID] });
        } catch {
          /* fanns inte registrerat */
        }

        if (origins.length) {
          try {
            await chrome.scripting.registerContentScripts([
              {
                id: CONTENT_SCRIPT_ID,
                matches: origins,
                js: CONTENT_FILES,
                runAt: 'document_idle',
                allFrames: false,
                persistAcrossSessions: true
              }
            ]);
          } catch (error) {
            console.warn('Kunde inte registrera innehållsskriptet', error);
            return;
          }
        }
      }

      // Flikar som redan är öppna får knappen direkt.
      if (inject && origins.length) await injectIntoOpenTabs(origins);
    })
    .catch((error) => console.warn('syncContentScripts misslyckades', error));
  return syncTask;
}

/* ------------------------------------------------------------------ */
/* Högerklicksmeny                                                     */
/* ------------------------------------------------------------------ */

async function syncContextMenu(settings) {
  const activeSettings = settings || (await getSettings());
  const lang = currentLang(activeSettings);
  try {
    await chrome.contextMenus.removeAll();
    chrome.contextMenus.create({
      id: MENU_ID,
      title: t(lang, 'menu.savePdf'),
      contexts: ['page']
    });
  } catch (error) {
    console.warn('Kunde inte skapa högerklicksmenyn', error);
  }

  try {
    await chrome.action.setTitle({ title: t(lang, 'appName') });
  } catch {
    /* ignoreras */
  }
}

/* ------------------------------------------------------------------ */
/* Sidkontext för innehållsskriptet                                    */
/* ------------------------------------------------------------------ */

async function buildPageContext(url) {
  const settings = await getSettings();
  const lang = currentLang(settings);
  return {
    allowed: isAllowedUrl(url, settings),
    show: settings.button.show,
    position: settings.button.position,
    lang,
    strings: {
      button: t(lang, 'content.button'),
      buttonShort: t(lang, 'content.buttonShort'),
      saving: t(lang, 'toast.saving'),
      saved: t(lang, 'toast.saved'),
      failed: t(lang, 'errors.unexpected')
    }
  };
}

/* ------------------------------------------------------------------ */
/* Händelser                                                           */
/* ------------------------------------------------------------------ */

chrome.runtime.onInstalled.addListener((details) => {
  void (async () => {
    await syncContentScripts();
    await syncContextMenu();
    if (details.reason === 'install') {
      try {
        await chrome.runtime.openOptionsPage();
      } catch {
        /* ignoreras */
      }
    }
  })();
});

chrome.runtime.onStartup.addListener(() => {
  void syncContentScripts();
  void syncContextMenu();
});

chrome.permissions.onAdded.addListener(() => void syncContentScripts());
chrome.permissions.onRemoved.addListener(() => void syncContentScripts());

function contentSyncNeeded(before, after) {
  const simplify = (value) => {
    if (!value || typeof value !== 'object') return '';
    const sites = Array.isArray(value.sites)
      ? value.sites.map((site) => `${site?.pattern}:${site?.enabled ? 1 : 0}`)
      : [];
    return JSON.stringify({ sites, show: value.button?.show !== false });
  };
  return simplify(before) !== simplify(after);
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.settings) return;
  const { oldValue, newValue } = changes.settings;
  if (contentSyncNeeded(oldValue, newValue)) void syncContentScripts();
  if (oldValue?.language !== newValue?.language) void syncContextMenu();
});

chrome.commands.onCommand.addListener((command) => {
  if (command !== 'save-pdf') return;
  void (async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    const result = await handleSaveRequest(tab);
    if (!result.ok && result.error === 'notAllowed') {
      // Visa panelen så att användaren kan lägga till webbplatsen.
      try {
        await chrome.action.openPopup();
      } catch {
        /* openPopup saknas i äldre versioner */
      }
    }
  })();
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID || !tab) return;
  void handleSaveRequest(tab);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Meddelanden till offscreen-dokumentet ska inte hanteras här.
  if (message?.target === 'offscreen') return undefined;
  handleMessage(message, sender)
    .then((response) => sendResponse(response))
    .catch((error) => {
      console.warn('Meddelande misslyckades', error);
      sendResponse({ ok: false, error: 'unexpected' });
    });
  return true;
});

async function handleMessage(message, sender) {
  if (!message || typeof message !== 'object') return { ok: false, error: 'unexpected' };

  switch (message.type) {
    case 'PAGE_CONTEXT': {
      const url = sender?.tab?.url || message.url || '';
      return { ok: true, context: await buildPageContext(url) };
    }

    case 'SAVE_PDF': {
      let tab = sender?.tab;
      if (!tab && typeof message.tabId === 'number') {
        try {
          tab = await chrome.tabs.get(message.tabId);
        } catch {
          tab = null;
        }
      }
      if (!tab) {
        const settings = await getSettings();
        const lang = currentLang(settings);
        return { ok: false, error: 'noTab', message: errorText(lang, 'noTab') };
      }
      if (!tab.url && typeof message.url === 'string') {
        tab = { ...tab, url: message.url };
      }
      return handleSaveRequest(tab);
    }

    case 'SYNC_CONTENT_SCRIPTS': {
      await syncContentScripts();
      return { ok: true };
    }

    default:
      return { ok: false, error: 'unexpected' };
  }
}

// Se till att standardinställningarna finns och att knappen är registrerad
// redan innan första händelsen kommer in.
void getSettings();
void syncContentScripts({ inject: false });
