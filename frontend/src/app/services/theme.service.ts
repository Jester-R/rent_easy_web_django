import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { catchError, of } from 'rxjs';

type Theme = 'light' | 'dark';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);
  readonly isDark = signal(false);

  constructor() {
    if (!isPlatformBrowser(this.platformId)) return;

    const stored = localStorage.getItem('renteasy_theme');
    const cookie = document.cookie
      .split('; ')
      .find((entry) => entry.startsWith('renteasy_theme='))
      ?.split('=')[1];
    this.apply(stored === 'dark' || (!stored && cookie === 'dark') ? 'dark' : 'light');
  }

  toggle(): void {
    this.setTheme(this.isDark() ? 'light' : 'dark');
  }

  private setTheme(theme: Theme): void {
    if (!isPlatformBrowser(this.platformId)) return;

    this.apply(theme);
    localStorage.setItem('renteasy_theme', theme);
    document.cookie = `renteasy_theme=${theme}; Path=/; Max-Age=31536000; SameSite=Lax`;
    this.http
      .post('/api/theme/set/', { theme }, { withCredentials: true })
      .pipe(catchError(() => of(null)))
      .subscribe();
  }

  private apply(theme: Theme): void {
    this.isDark.set(theme === 'dark');
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }
}
