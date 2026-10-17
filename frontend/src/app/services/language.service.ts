import { DOCUMENT, isPlatformBrowser } from '@angular/common';
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { CATALOG } from '../i18n/catalog';
import { MONTHS_EN, MONTHS_KM, VALUE_KM } from '../i18n/labels';
import type { SiteLanguage } from '../i18n/types';

export type { SiteLanguage } from '../i18n/types';

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly document = inject(DOCUMENT);
  private readonly platformId = inject(PLATFORM_ID);
  readonly current = signal<SiteLanguage>('en');

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      const saved = window.localStorage.getItem('rent-easy-language');
      if (saved === 'km' || saved === 'en') this.current.set(saved);
    }
    this.applyLanguage();
  }

  toggle(): void {
    this.set(this.current() === 'en' ? 'km' : 'en');
  }

  set(language: SiteLanguage): void {
    this.current.set(language);
    if (isPlatformBrowser(this.platformId)) {
      window.localStorage.setItem('rent-easy-language', language);
    }
    this.applyLanguage();
  }

  t(key: string, params?: Record<string, string | number>): string {
    return this.tIn(this.current(), key, params);
  }

  /** Translate `key` explicitly in `target` (ignores the active language). */
  tIn(target: SiteLanguage, key: string, params?: Record<string, string | number>): string {
    const entry = CATALOG[key];
    if (!entry) return key;
    const value = target === 'km' ? entry[1] : entry[0];
    if (!params) return value;
    return value.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in params ? String(params[name]) : match,
    );
  }

  /** The language code that isn't currently active. */
  other(): SiteLanguage {
    return this.current() === 'en' ? 'km' : 'en';
  }

  /** Translate a raw backend label (status / role / refund…); English is the raw value. */
  valueLabel(value: string): string {
    if (this.current() !== 'km') return value;
    return VALUE_KM[value] ?? value;
  }

  /** Month name for an index (0-11). */
  monthName(monthIndex: number): string {
    const months = this.current() === 'km' ? MONTHS_KM : MONTHS_EN;
    return months[monthIndex] ?? '';
  }

  private applyLanguage(): void {
    this.document.documentElement.lang = this.current();
  }
}
