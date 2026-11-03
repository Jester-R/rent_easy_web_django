import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { UrlSerializer, provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { provideClientHydration } from '@angular/platform-browser';
import { authErrorInterceptor } from './services/auth.interceptor';
import { TrailingSlashUrlSerializer } from './services/url-serializer';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    { provide: UrlSerializer, useClass: TrailingSlashUrlSerializer },
    provideHttpClient(withFetch(), withInterceptors([authErrorInterceptor])),
    provideClientHydration()
  ]
};
