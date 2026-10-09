import { PLATFORM_ID, inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../services/auth.service';

/** The authenticated user's landing page, falling back to the home page. */
function homeFor(auth: AuthService): string {
  return auth.currentUser()?.home_url || '/';
}

/**
 * Build a guard that requires authentication and (optionally) one of the
 * given roles. Guards are no-ops during SSR because session cookies are not
 * forwarded to the renderer; the browser re-evaluates on hydration.
 */
function roleGuard(roles: string[] | null): CanActivateFn {
  return (_route, state) => {
    const platformId = inject(PLATFORM_ID);
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!isPlatformBrowser(platformId)) return true;

    const decide = () => {
      const user = auth.currentUser();
      if (!user) {
        return router.createUrlTree(['/login'], { queryParams: { next: state.url } });
      }
      if (roles && roles.length > 0 && !roles.includes(user.role)) {
        return router.createUrlTree(['/denied']);
      }
      return true;
    };

    return auth.isLoading() ? auth.checkAuth().pipe(map(decide)) : decide();
  };
}

export const authGuard = roleGuard(null);
export const renterGuard = roleGuard(['renter']);
export const ownerGuard = roleGuard(['owner']);

/** Super-admin area: accepts the `superadmin` role or any staff account. */
export const adminGuard: CanActivateFn = (_route, state) => {
  const platformId = inject(PLATFORM_ID);
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!isPlatformBrowser(platformId)) return true;

  const decide = () => {
    if (!auth.currentUser()) {
      return router.createUrlTree(['/login'], { queryParams: { next: state.url } });
    }
    return auth.isAdmin() ? true : router.createUrlTree(['/denied']);
  };

  return auth.isLoading() ? auth.checkAuth().pipe(map(decide)) : decide();
};

/** Keep authenticated users away from login/register/role-select. */
export const guestGuard: CanActivateFn = () => {
  const platformId = inject(PLATFORM_ID);
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!isPlatformBrowser(platformId)) return true;

  const decide = () =>
    auth.currentUser() ? router.createUrlTree([homeFor(auth)]) : true;

  return auth.isLoading() ? auth.checkAuth().pipe(map(decide)) : decide();
};
