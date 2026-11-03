import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-google-callback',
  imports: [CommonModule, RouterLink],
  template: `
    <div class="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-10 sm:px-6">
      <div class="w-full max-w-[26rem]">
        <div class="app-card p-6 sm:p-8 text-center">
          @if (errorMessage()) {
            <span class="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-danger/10 text-danger">
              <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </span>
            <h1 class="text-lg font-extrabold text-ink mb-2">Authentication Failed</h1>
            <p class="text-[13px] text-ink-3 mb-6">{{ errorMessage() }}</p>
            <a routerLink="/login" class="btn btn-primary w-full">Return to Sign In</a>
          } @else {
            <div class="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-3 border-primary border-t-transparent"></div>
            <h1 class="text-lg font-extrabold text-ink mb-1">Signing you in</h1>
            <p class="text-[13px] text-ink-3">Completing Google authentication...</p>
          }
        </div>
      </div>
    </div>
  `,
})
export class GoogleCallbackComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  readonly language = inject(LanguageService);

  errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    const error = this.route.snapshot.queryParamMap.get('error');
    if (error) {
      this.router.navigate(['/login'], { queryParams: { error: 'oauth_cancelled' } });
      return;
    }

    const code = this.route.snapshot.queryParamMap.get('code');
    const state = this.route.snapshot.queryParamMap.get('state') || '';

    if (!code) {
      this.errorMessage.set('Missing authorization code from Google.');
      return;
    }

    this.auth.handleGoogleCallback(code, state).subscribe({
      next: (res) => {
        if (res.status === 'select_role' || res.redirect?.includes('/role-select')) {
          this.router.navigate(['/role-select']);
          return;
        }

        if (res.status === 'pending_approval' || res.redirect?.includes('pending=1')) {
          this.router.navigate(['/register'], { queryParams: { pending: '1' } });
          return;
        }

        const rawDest = res.redirect || res.home_url || '';
        const dest = rawDest.length > 1 && rawDest.endsWith('/') ? rawDest.replace(/\/+$/, '') : rawDest;
        if (dest && dest.startsWith('/') && !dest.startsWith('/login')) {
          this.router.navigateByUrl(dest);
        } else if (res.user?.role === 'owner') {
          this.router.navigate(['/owner']);
        } else if (res.user?.role === 'renter') {
          this.router.navigate(['/rent']);
        } else if (res.user?.is_superadmin_role) {
          this.router.navigate(['/console']);
        } else {
          this.router.navigate(['/']);
        }
      },
      error: (err) => {
        const detail = err.error?.detail || '';
        if (detail === 'approval_pending') {
          this.router.navigate(['/register'], { queryParams: { pending: '1' } });
        } else if (detail === 'registration_rejected') {
          this.router.navigate(['/login'], { queryParams: { error: 'registration_rejected' } });
        } else if (detail === 'not_authorized') {
          this.router.navigate(['/login'], { queryParams: { error: 'not_authorized' } });
        } else {
          this.errorMessage.set('Failed to verify Google sign-in credentials. Please try again.');
        }
      },
    });
  }
}
