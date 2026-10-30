import { isPlatformBrowser } from '@angular/common';
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { PropertyCategorySetting } from '../models';

@Injectable({ providedIn: 'root' })
export class PropertyCategoryService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);
  readonly categories = signal<PropertyCategorySetting[]>([]);
  private loading = false;
  private loaded = false;

  setCategories(categories: PropertyCategorySetting[]): void {
    this.categories.set(categories);
    this.loaded = true;
  }

  load(): void {
    if (!isPlatformBrowser(this.platformId) || this.loading || this.loaded) return;
    this.loading = true;
    const params = new HttpParams().set('_refresh', String(Date.now()));
    this.http.get<{ categories: PropertyCategorySetting[] }>('/api/property-categories/', {
      withCredentials: true,
      params,
    }).subscribe({
      next: (res) => {
        this.setCategories(res.categories || []);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  label(value: string | null | undefined, language: 'en' | 'km'): string {
    if (!value) return '';
    this.load();
    const category = this.categories().find((item) => item.value === value);
    return category
      ? (language === 'km' ? category.label_km : category.label_en)
      : value;
  }
}
