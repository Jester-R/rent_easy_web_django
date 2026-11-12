import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, catchError, forkJoin, map, of, shareReplay, switchMap, throwError } from 'rxjs';
import { Property, LandingData, PropertyCategorySetting } from '../models';

export interface PropertyBrowseResponse {
  properties: Property[];
  meta: {
    provinces: string[];
    locations: string[];
    communes: string[];
    villages: string[];
    avg_price: number;
    price_floor: number;
    price_ceiling: number;
    all_locations_token: string;
    categories: PropertyCategorySetting[];
    all_categories_token: string;
    total: number;
    page: number;
    page_size: number;
  };
  filters: {
    q: string;
    province: string;
    location: string;
    commune: string;
    village: string;
    category: string;
    min_bedrooms: number;
    max_price: string;
    sort: string;
  };
}

export interface CambodiaProvince {
  code: string;
  name_en: string;
  name_km: string;
}

export interface CambodiaDistrict {
  code: string;
  province_code: string;
  name_en: string;
  name_km: string;
}

export interface CambodiaCommune {
  code: string;
  district_code: string;
  province_code: string;
  name_en: string;
  name_km: string;
}

export interface CambodiaVillage {
  code: string;
  commune_code: string;
  district_code: string;
  province_code: string;
  name_en: string;
  name_km: string;
}

@Injectable({
  providedIn: 'root',
})
export class PropertyService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';
  private readonly csvCache = new Map<string, Observable<string[][]>>();
  private districtsCache?: Observable<CambodiaDistrict[]>;
  private readonly datasetBaseUrl =
    'https://data.mef.gov.kh/api/v1/public-datasets';

  getCambodiaDistricts(): Observable<CambodiaDistrict[]> {
    if (this.districtsCache) return this.districtsCache;
    const pageSize = 200;
    const fetchPage = (page: number) => {
      const params = new HttpParams()
        .set('page', String(page))
        .set('page_size', String(pageSize));
      return this.http.get<unknown>(
        `${this.datasetBaseUrl}/pd_66a8603800604c000123e145/json`,
        { params },
      );
    };

    this.districtsCache = fetchPage(1).pipe(
      switchMap((firstPage) => {
        const totalPages = this.parseTotalPages(firstPage);
        if (totalPages <= 1) return of(this.parseCambodiaDistricts(firstPage));
        const remainingPages = Array.from(
          { length: totalPages - 1 },
          (_, index) => fetchPage(index + 2),
        );
        return forkJoin(remainingPages).pipe(
          map((pages) => [firstPage, ...pages].flatMap((page) => this.parseCambodiaDistricts(page))),
        );
      }),
      map((districts) => districts.filter(
        (district, index, all) => all.findIndex((candidate) => candidate.code === district.code) === index,
      ).sort((a, b) => a.name_en.localeCompare(b.name_en))),
      catchError((error) => {
        this.districtsCache = undefined;
        return throwError(() => error);
      }),
      shareReplay(1),
    );
    return this.districtsCache;
  }

  getCambodiaProvinces(): Observable<CambodiaProvince[]> {
    return this.fetchLocationCsv('pd_66a8603700604c000123e144').pipe(
      map((rows) =>
        this.csvRecords(rows)
          .map((record) => ({
            code: record['province_code'] || '',
            name_en: record['province_en'] || '',
            name_km: record['province_kh'] || '',
          }))
          .filter((item) => item.code && item.name_en && item.name_km),
      ),
    );
  }

  getCambodiaCommunes(): Observable<CambodiaCommune[]> {
    return this.fetchLocationCsv('pd_66a8603900604c000123e146').pipe(
      map((rows) =>
        this.csvRecords(rows)
          .map((record) => ({
            code: record['commune_code'] || '',
            district_code: record['district_code'] || '',
            province_code: record['province_code'] || '',
            name_en: record['commune_en'] || '',
            name_km: record['commune_kh'] || '',
          }))
          .filter((item) => item.code && item.name_en && item.name_km),
      ),
    );
  }

  getCambodiaVillages(): Observable<CambodiaVillage[]> {
    return this.fetchLocationCsv('pd_66a8603a00604c000123e147').pipe(
      map((rows) =>
        this.csvRecords(rows)
          .map((record) => ({
            code: record['village_code'] || '',
            commune_code: this.normalizeCommuneCode(record['commune_code'] || ''),
            district_code: record['district_code'] || '',
            province_code: record['province_code'] || '',
            name_en: record['village_en'] || '',
            name_km: record['village_kh'] || '',
          }))
          .filter((item) => item.code && item.name_en && item.name_km),
      ),
    );
  }

  private normalizeCommuneCode(code: string): string {
    return code === '120913' ? '120912' : code;
  }

  private fetchLocationCsv(datasetId: string): Observable<string[][]> {
    const cached = this.csvCache.get(datasetId);
    if (cached) return cached;
    const request = this.http
      .get(`${this.datasetBaseUrl}/${datasetId}/file`, { responseType: 'text' })
      .pipe(
        map((csv) => this.parseCsv(csv as string)),
        shareReplay(1),
      );
    this.csvCache.set(datasetId, request);
    return request;
  }

  private parseCsv(text: string): string[][] {
    const rows: string[][] = [];
    let row: string[] = [];
    let field = '';
    let quoted = false;
    for (let index = 0; index < text.length; index++) {
      const char = text[index];
      if (quoted) {
        if (char === '"') {
          if (text[index + 1] === '"') {
            field += '"';
            index++;
          } else {
            quoted = false;
          }
        } else {
          field += char;
        }
      } else if (char === '"') {
        quoted = true;
      } else if (char === ',') {
        row.push(field);
        field = '';
      } else if (char === '\n') {
        row.push(field);
        rows.push(row);
        row = [];
        field = '';
      } else if (char !== '\r') {
        field += char;
      }
    }
    if (field.length || row.length) {
      row.push(field);
      rows.push(row);
    }
    return rows;
  }

  private csvRecords(rows: string[][]): Record<string, string>[] {
    if (!rows.length) return [];
    const headers = rows[0].map((header) => header.trim());
    return rows.slice(1).map((values) =>
      headers.reduce<Record<string, string>>((record, header, index) => {
        record[header] = (values[index] || '').trim();
        return record;
      }, {}),
    );
  }

  resolveGoogleMapsUrl(url: string): Observable<{ latitude: number; longitude: number }> {
    return this.http.post<{ latitude: number; longitude: number }>(
      `${this.baseUrl}/maps/resolve/`,
      { url },
      { withCredentials: true },
    );
  }

  private parseTotalPages(response: unknown): number {
    if (!response || typeof response !== 'object') return 1;
    const payload = response as Record<string, unknown>;
    const totalPages = Number(payload['total_pages']);
    return Number.isInteger(totalPages) && totalPages > 0 ? totalPages : 1;
  }

  private parseCambodiaDistricts(response: unknown): CambodiaDistrict[] {
    const payload = response as Record<string, unknown> | null;
    const records = Array.isArray(response)
      ? response
      : Array.isArray(payload?.['data'])
        ? payload['data']
        : Array.isArray(payload?.['results'])
          ? payload['results']
          : Array.isArray(payload?.['items'])
            ? payload['items']
            : [];
    return records
      .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
      .map((item) => ({
        code: String(item['district_code'] || '').trim(),
        province_code: String(item['province_code'] || '').trim(),
        name_en: String(item['district_en'] || '').trim(),
        name_km: String(item['district_kh'] || '').trim(),
      }))
      .filter((item) => item.code && item.name_en && item.name_km);
  }

  getLandingData(): Observable<LandingData> {
    return this.http.get<LandingData>(`${this.baseUrl}/core/landing/`, {
      withCredentials: true,
    });
  }

  getCategories(): Observable<{ categories: PropertyCategorySetting[] }> {
    const params = new HttpParams().set('_refresh', String(Date.now()));
    return this.http.get<{ categories: PropertyCategorySetting[] }>(
      `${this.baseUrl}/property-categories/`,
      { withCredentials: true, params },
    );
  }

  browse(filters?: {
    q?: string;
    province?: string;
    location?: string;
    commune?: string;
    village?: string;
    category?: string;
    min_bedrooms?: number;
    max_price?: number;
    sort?: string;
    page?: number;
    page_size?: number;
  }): Observable<PropertyBrowseResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.province && filters.province !== '__all__')
      params = params.set('province', filters.province);
    if (filters?.location && filters.location !== '__all__')
      params = params.set('location', filters.location);
    if (filters?.commune && filters.commune !== '__all__')
      params = params.set('commune', filters.commune);
    if (filters?.village && filters.village !== '__all__')
      params = params.set('village', filters.village);
    if (filters?.category && filters.category !== '__all__')
      params = params.set('category', filters.category);
    if (filters?.min_bedrooms)
      params = params.set('min_bedrooms', filters.min_bedrooms.toString());
    if (filters?.max_price)
      params = params.set('max_price', filters.max_price.toString());
    if (filters?.sort) params = params.set('sort', filters.sort);
    if (filters?.page) params = params.set('page', String(filters.page));
    if (filters?.page_size) params = params.set('page_size', String(filters.page_size));

    return this.http.get<PropertyBrowseResponse>(`${this.baseUrl}/rent/properties/`, {
      params,
      withCredentials: true,
    });
  }

  getRenterProperty(
    id: number
  ): Observable<{ property: Property; active_booking_id: number | null }> {
    return this.http.get<{ property: Property; active_booking_id: number | null }>(
      `${this.baseUrl}/rent/property/${id}/`,
      { withCredentials: true }
    );
  }

  getPublicProperty(
    id: number
  ): Observable<{ property: Property; is_favorite: boolean; viewer_is_owner: boolean }> {
    return this.http.get<{
      property: Property;
      is_favorite: boolean;
      viewer_is_owner: boolean;
    }>(`${this.baseUrl}/property/${id}/`, { withCredentials: true });
  }

  getFavorites(page = 1, pageSize = 25): Observable<{ favorites: Property[]; count: number; total: number; page: number; page_size: number }> {
    const params = new HttpParams().set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<{ favorites: Property[]; count: number; total: number; page: number; page_size: number }>(
      `${this.baseUrl}/rent/favorites/`,
      { params,
        withCredentials: true }
    );
  }

  toggleFavorite(id: number): Observable<{ favorited: boolean; count: number }> {
    return this.http.post<{ favorited: boolean; count: number }>(
      `${this.baseUrl}/rent/property/${id}/favorite/`,
      {},
      { withCredentials: true }
    );
  }

  requestBooking(
    id: number,
    data: { move_in_date?: string; end_date?: string; lease_months?: number; note?: string }
  ): Observable<{ booking_id: number; reference: string }> {
    return this.http.post<{ booking_id: number; reference: string }>(
      `${this.baseUrl}/rent/property/${id}/request/`,
      data,
      { withCredentials: true }
    );
  }

  getOwnerProperties(page = 1, pageSize = 25): Observable<{ properties: Property[]; total: number; page: number; page_size: number }> {
    const params = new HttpParams().set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<{ properties: Property[]; total: number; page: number; page_size: number }>(
      `${this.baseUrl}/owner/properties/`,
      { params,
        withCredentials: true }
    );
  }

  generateDescription(data: {
    prompt?: string;
    locations?: string[];
    categories?: string[];
    title?: string;
    title_km?: string;
    location?: string;
    category?: string;
    price_per_month?: number;
    bedrooms?: number;
    bathrooms?: number;
    notes?: string;
  }): Observable<{ title?: string; title_km?: string; location?: string; province?: string; commune?: string; village?: string; price_per_month?: number | null; category?: string; bedrooms?: number | null; bathrooms?: number | null; description: string; description_km: string; model?: string; provider?: string }> {
    return this.http.post<{ title?: string; title_km?: string; location?: string; province?: string; commune?: string; village?: string; price_per_month?: number | null; category?: string; bedrooms?: number | null; bathrooms?: number | null; description: string; description_km: string; model?: string; provider?: string }>(
      `${this.baseUrl}/ai/property-description/`,
      data,
      { withCredentials: true }
    );
  }

  uploadPropertyImages(files: File[]): Observable<{ urls: string[] }> {
    const form = new FormData();
    for (const file of files) {
      form.append('images', file, file.name);
    }
    return this.http.post<{ urls: string[] }>(
      `${this.baseUrl}/uploads/property-images/`,
      form,
      { withCredentials: true }
    );
  }

  createProperty(data: Partial<Property>): Observable<{ property: Property }> {
    return this.http.post<{ property: Property }>(
      `${this.baseUrl}/owner/properties/new/`,
      data,
      { withCredentials: true }
    );
  }

  updateProperty(id: number, data: Partial<Property>): Observable<{ property: Property }> {
    return this.http.post<{ property: Property }>(
      `${this.baseUrl}/owner/properties/${id}/edit/`,
      data,
      { withCredentials: true }
    );
  }

  deleteProperty(id: number): Observable<{ ok: boolean; deleted: number; refunds_requested: number }> {
    return this.http.post<{ ok: boolean; deleted: number; refunds_requested: number }>(
      `${this.baseUrl}/owner/properties/${id}/delete/`,
      {},
      { withCredentials: true }
    );
  }
}
