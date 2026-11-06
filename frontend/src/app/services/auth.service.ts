import { Injectable, computed, inject, signal, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of } from 'rxjs';
import { User, RenterDashboardData, OwnerDashboardData, PayoutAccountDetails } from '../models';

export interface RegisterResult {
  status: 'active' | 'pending_approval' | 'otp_required';
  role?: 'renter' | 'owner';
  user?: User;
  email?: string;
  home_url?: string;
  message?: string;
  redirect?: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly baseUrl = '/api';

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

  register(data: {
    full_name?: string;
    username: string;
    email: string;
    password?: string;
    password_confirm?: string;
    role?: 'renter' | 'owner';
  }): Observable<RegisterResult> {
    return this.http
      .post<RegisterResult>(`${this.baseUrl}/auth/register/`, data, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => {
          if (res.status === 'active' && res.user) {
            this.currentUser.set(res.user);
          }
        })
      );
  }

  verifyRegisterOtp(
    email: string,
    code: string
  ): Observable<RegisterResult> {
    return this.http
      .post<RegisterResult>(
        `${this.baseUrl}/auth/register/verify-otp/`,
        { email, code },
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          if (res.status === 'active' && res.user) {
            this.currentUser.set(res.user);
          }
        })
      );
  }

  resendRegisterOtp(
    email: string
  ): Observable<{ ok: boolean; message: string }> {
    return this.http.post<{ ok: boolean; message: string }>(
      `${this.baseUrl}/auth/register/resend-otp/`,
      { email },
      { withCredentials: true }
    );
  }

  selectRole(role: 'renter' | 'owner'): Observable<{
    ok: boolean;
    status: 'active' | 'pending_approval';
    role: string;
    user?: User;
    home_url: string;
    redirect: string;
  }> {
    return this.http
      .post<{
        ok: boolean;
        status: 'active' | 'pending_approval';
        role: string;
        user?: User;
        home_url: string;
        redirect: string;
      }>(
        `${this.baseUrl}/auth/role/`,
        { role },
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          if (res.status === 'active' && res.user) {
            this.currentUser.set(res.user);
          }
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

  getGoogleOAuthConfig(): Observable<{ enabled: boolean; client_id: string }> {
    return this.http.get<{ enabled: boolean; client_id: string }>(
      `${this.baseUrl}/auth/google/config/`,
      { withCredentials: true }
    );
  }

  getGoogleAuthUrl(
    role: string = '',
    nextUrl: string = ''
  ): Observable<{ enabled: boolean; url: string }> {
    const params: string[] = [];
    if (role) params.push(`role=${encodeURIComponent(role)}`);
    if (nextUrl) params.push(`next=${encodeURIComponent(nextUrl)}`);
    const query = params.length ? `?${params.join('&')}` : '';
    return this.http.get<{ enabled: boolean; url: string }>(
      `${this.baseUrl}/auth/google/url/${query}`,
      { withCredentials: true }
    );
  }

  loginWithGoogle(
    role: string = '',
    nextUrl: string = ''
  ): void {
    if (!isPlatformBrowser(this.platformId)) return;
    const params = new URLSearchParams();
    if (role) params.set('role', role);
    if (nextUrl) params.set('next', nextUrl);
    const qs = params.toString();
    window.location.href = `${this.baseUrl}/auth/google/login/${qs ? '?' + qs : ''}`;
  }

  handleGoogleCallback(
    code: string,
    state?: string,
    redirectUri?: string
  ): Observable<{
    ok: boolean;
    status: 'active' | 'pending_approval' | 'select_role';
    role?: string;
    user?: User;
    home_url?: string;
    redirect: string;
  }> {
    return this.http
      .post<{
        ok: boolean;
        status: 'active' | 'pending_approval' | 'select_role';
        role?: string;
        user?: User;
        home_url?: string;
        redirect: string;
      }>(
        `${this.baseUrl}/auth/google/callback/`,
        { code, state, redirect_uri: redirectUri },
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          if (res.status === 'active' && res.user) {
            this.currentUser.set(res.user);
          }
        })
      );
  }

  getPreferences(): Observable<{ user: User }> {
    return this.http.get<{ user: User }>(`${this.baseUrl}/auth/preferences/`, {
      withCredentials: true,
    });
  }

  updatePreferences(data: {
    full_name?: string;
    email?: string;
    username?: string;
    avatar_url?: string;
    payment_account_name?: string;
    payment_account_number?: string;
    payment_phone?: string;
    payout_method?: string;
    payout_account_name?: string;
    payout_account_number?: string;
    payout_bank_name?: string;
    payout_phone?: string;
    payout_note?: string;
    payout_accounts?: Record<string, PayoutAccountDetails>;
  }): Observable<{ user: User }> {
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

  getTelegramLoginConfig(): Observable<{
    enabled: boolean;
    bot_username: string;
    bot_id: string;
    auth_url: string;
  }> {
    return this.http.get<{
      enabled: boolean;
      bot_username: string;
      bot_id: string;
      auth_url: string;
    }>(`${this.baseUrl}/auth/telegram/config/`, { withCredentials: true });
  }

  startTelegramLogin(role?: 'renter' | 'owner' | ''): Observable<{
    token: string;
    url: string;
    expires_in: number;
  }> {
    return this.http.post<{ token: string; url: string; expires_in: number }>(
      `${this.baseUrl}/auth/telegram/login/start/`,
      { role: role || '' },
      { withCredentials: true }
    );
  }

  verifyTelegramLogin(
    token: string,
    code: string
  ): Observable<{
    ok: boolean;
    status: 'active' | 'select_role' | 'pending_approval';
    user?: User;
    home_url?: string;
    redirect?: string;
  }> {
    return this.http
      .post<{
        ok: boolean;
        status: 'active' | 'select_role' | 'pending_approval';
        user?: User;
        home_url?: string;
        redirect?: string;
      }>(
        `${this.baseUrl}/auth/telegram/login/verify/`,
        { token, code },
        { withCredentials: true }
      )
      .pipe(
        tap((res) => {
          if (res.status === 'active' && res.user) {
            this.currentUser.set(res.user);
          }
        })
      );
  }

  createTelegramLink(): Observable<{ url: string }> {
    return this.http.post<{ url: string }>(`${this.baseUrl}/auth/telegram/link/`, {}, { withCredentials: true });
  }

  unlinkTelegram(): Observable<{ user: User }> {
    return this.http.post<{ user: User }>(`${this.baseUrl}/auth/telegram/unlink/`, {}, { withCredentials: true }).pipe(
      tap((res) => this.currentUser.set(res.user)),
    );
  }

  getRenterDashboard(): Observable<RenterDashboardData> {
    return this.http.get<RenterDashboardData>(`${this.baseUrl}/rent/`, {
      withCredentials: true,
    });
  }

  getOwnerDashboard(): Observable<OwnerDashboardData> {
    return this.http.get<OwnerDashboardData>(`${this.baseUrl}/owner/`, {
      withCredentials: true,
    });
  }
}
