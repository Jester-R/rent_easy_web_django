import { Injectable, computed, inject, signal, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of } from 'rxjs';
import { User, RenterDashboardData, OwnerDashboardData } from '../models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly baseUrl = '';

  readonly currentUser = signal<User | null>(null);
  readonly isLoading = signal<boolean>(true);

  readonly isAuthenticated = computed(() => !!this.currentUser());
  readonly isRenter = computed(() => this.currentUser()?.role === 'renter');
  readonly isOwner = computed(() => this.currentUser()?.role === 'owner');
  readonly isAdmin = computed(() => this.currentUser()?.is_superadmin_role || this.currentUser()?.is_staff);

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.checkAuth().subscribe();
    } else {
      this.isLoading.set(false);
    }
  }

  checkAuth(): Observable<{ authenticated: boolean; user?: User }> {
    return this.http
      .get<{ authenticated: boolean; user?: User }>(`${this.baseUrl}/auth/login/`, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => {
          this.isLoading.set(false);
          if (res.authenticated && res.user) {
            this.currentUser.set(res.user);
          } else {
            this.currentUser.set(null);
          }
        }),
        catchError(() => {
          this.isLoading.set(false);
          this.currentUser.set(null);
          return of({ authenticated: false });
        })
      );
  }

  login(credentials: { identifier?: string; email?: string; password?: string; next?: string }): Observable<{ user: User; home_url: string; redirect: string }> {
    return this.http
      .post<{ user: User; home_url: string; redirect: string }>(
        `${this.baseUrl}/auth/login/`,
        credentials,
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          this.currentUser.set(res.user);
        })
      );
  }

  register(data: { full_name?: string; username: string; email: string; password?: string; password_confirm?: string }): Observable<{ user_id: number; redirect: string }> {
    return this.http.post<{ user_id: number; redirect: string }>(
      `${this.baseUrl}/auth/register/`,
      data,
      { withCredentials: true }
    );
  }

  selectRole(role: 'renter' | 'owner'): Observable<{ ok: boolean; role: string; home_url: string; redirect: string }> {
    return this.http
      .post<{ ok: boolean; role: string; home_url: string; redirect: string }>(
        `${this.baseUrl}/auth/role/`,
        { role },
        { withCredentials: true }
      )
      .pipe(
        tap(() => {
          this.checkAuth().subscribe();
        })
      );
  }

  logout(): Observable<{ ok: boolean; redirect: string }> {
    return this.http
      .post<{ ok: boolean; redirect: string }>(
        `${this.baseUrl}/auth/logout/`,
        {},
        { withCredentials: true }
      )
      .pipe(
        tap(() => {
          this.currentUser.set(null);
        })
      );
  }

  getPreferences(): Observable<{ user: User }> {
    return this.http.get<{ user: User }>(`${this.baseUrl}/auth/preferences/`, {
      withCredentials: true,
    });
  }

  updatePreferences(data: { full_name?: string; email?: string; username?: string }): Observable<{ user: User }> {
    return this.http
      .post<{ user: User }>(`${this.baseUrl}/auth/preferences/`, data, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => {
          this.currentUser.set(res.user);
        })
      );
  }

  getRenterDashboard(): Observable<RenterDashboardData> {
    return this.http.get<RenterDashboardData>(`${this.baseUrl}/api/rent/`, {
      withCredentials: true,
    });
  }

  getOwnerDashboard(): Observable<OwnerDashboardData> {
    return this.http.get<OwnerDashboardData>(`${this.baseUrl}/api/owner/`, {
      withCredentials: true,
    });
  }
}
