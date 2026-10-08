import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Property, LandingData } from '../models';

export interface PropertyBrowseResponse {
  properties: Property[];
  meta: {
    locations: string[];
    avg_price: number;
    price_floor: number;
    price_ceiling: number;
    all_locations_token: string;
  };
  filters: {
    q: string;
    location: string;
    min_bedrooms: number;
    max_price: string;
    sort: string;
  };
}

@Injectable({
  providedIn: 'root',
})
export class PropertyService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api';

  getLandingData(): Observable<LandingData> {
    return this.http.get<LandingData>(`${this.baseUrl}/core/landing/`, {
      withCredentials: true,
    });
  }

  browse(filters?: {
    q?: string;
    location?: string;
    min_bedrooms?: number;
    max_price?: number;
    sort?: string;
  }): Observable<PropertyBrowseResponse> {
    let params = new HttpParams();
    if (filters?.q) params = params.set('q', filters.q);
    if (filters?.location && filters.location !== '__all__')
      params = params.set('location', filters.location);
    if (filters?.min_bedrooms)
      params = params.set('min_bedrooms', filters.min_bedrooms.toString());
    if (filters?.max_price)
      params = params.set('max_price', filters.max_price.toString());
    if (filters?.sort) params = params.set('sort', filters.sort);

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

  getFavorites(): Observable<{ favorites: Property[]; count: number }> {
    return this.http.get<{ favorites: Property[]; count: number }>(
      `${this.baseUrl}/rent/favorites/`,
      { withCredentials: true }
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
    data: { move_in_date?: string; lease_months?: number; note?: string }
  ): Observable<{ booking_id: number; reference: string }> {
    return this.http.post<{ booking_id: number; reference: string }>(
      `${this.baseUrl}/rent/property/${id}/request/`,
      data,
      { withCredentials: true }
    );
  }

  getOwnerProperties(): Observable<{ properties: Property[] }> {
    return this.http.get<{ properties: Property[] }>(
      `${this.baseUrl}/owner/properties/`,
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

  deleteProperty(id: number): Observable<{ ok: boolean; deleted: number }> {
    return this.http.post<{ ok: boolean; deleted: number }>(
      `${this.baseUrl}/owner/properties/${id}/delete/`,
      {},
      { withCredentials: true }
    );
  }
}
