/**
 * Lazily load Leaflet from a CDN in the browser only.
 *
 * The map tiles come from OpenStreetMap (the same source as the Flutter app's
 * flutter_map), so no API key is required. Loading happens at runtime to keep
 * SSR and the build free of any `window`/`document` access.
 */

export const LEAFLET_VERSION = '1.9.4';
const CSS_URL = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;
const JS_URL = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;

declare global {
  interface Window {
    L?: any;
    __renteasyLeaflet?: Promise<any>;
  }
}

export function loadLeaflet(): Promise<any> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return Promise.reject(new Error('leaflet_unavailable'));
  }
  if (window.L) return Promise.resolve(window.L);
  if (window.__renteasyLeaflet) return window.__renteasyLeaflet;

  window.__renteasyLeaflet = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${CSS_URL}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = CSS_URL;
      document.head.appendChild(link);
    }
    const script = document.createElement('script');
    script.src = JS_URL;
    script.async = true;
    script.onload = () => (window.L ? resolve(window.L) : reject(new Error('leaflet_missing')));
    script.onerror = () => reject(new Error('leaflet_load_failed'));
    document.head.appendChild(script);
  });

  return window.__renteasyLeaflet;
}

export const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
export const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
export const PHNOM_PENH: [number, number] = [11.5564, 104.9282];
