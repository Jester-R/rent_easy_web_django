import { HttpInterceptorFn } from '@angular/common/http';
import { Injector, PLATFORM_ID, inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const AUTH_ENDPOINTS = ['/auth/login/', '/auth/register/'];

export const authErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const injector = inject(Injector);
  const platformId = inject(PLATFORM_ID);

  return next(req).pipe(
    catchError((error) => {
      const isAuthCall = AUTH_ENDPOINTS.some((path) => req.url.includes(path));
      if (
        error.status === 401 &&
        req.url.includes('/api/') &&
        !isAuthCall &&
        isPlatformBrowser(platformId)
      ) {
        injector.get(AuthService).currentUser.set(null);
        void router.navigate(['/login'], { queryParams: { next: router.url } });
      }
      return throwError(() => error);
    })
  );
};
