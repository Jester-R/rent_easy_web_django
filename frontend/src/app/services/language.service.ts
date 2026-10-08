import { DOCUMENT, isPlatformBrowser } from '@angular/common';
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';

export type SiteLanguage = 'en' | 'km';

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

  t(english: string, khmer: string): string {
    return this.current() === 'km' ? khmer : english;
  }

  private applyLanguage(): void {
    this.document.documentElement.lang = this.current();
  }
}
