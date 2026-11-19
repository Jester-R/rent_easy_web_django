import { Routes } from '@angular/router';
import { LandingComponent } from './pages/landing/landing';
import {
  adminGuard,
  authGuard,
  guestGuard,
  ownerGuard,
  renterGuard,
  superadminGuard,
} from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent, pathMatch: 'full' },
  {
    path: 'browse',
    loadComponent: () => import('./pages/properties/browse/browse').then((m) => m.BrowsePropertiesComponent),
  },
  {
    path: 'properties/:id',
    loadComponent: () => import('./pages/properties/detail/detail').then((m) => m.PropertyDetailComponent),
  },
  {
    path: 'login',
    loadComponent: () => import('./pages/auth/login/login').then((m) => m.LoginComponent),
    canActivate: [guestGuard],
  },
  {
    path: 'register',
    loadComponent: () => import('./pages/auth/register/register').then((m) => m.RegisterComponent),
    canActivate: [guestGuard],
  },
  {
    path: 'role-select',
    loadComponent: () => import('./pages/auth/role-select/role-select').then((m) => m.RoleSelectComponent),
    canActivate: [guestGuard],
  },
  {
    path: 'auth/google/callback',
    loadComponent: () => import('./pages/auth/google-callback/google-callback').then((m) => m.GoogleCallbackComponent),
  },
  {
    path: 'profile',
    loadComponent: () => import('./pages/profile/profile').then((m) => m.ProfileComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    loadComponent: () => import('./pages/settings/settings').then((m) => m.SettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'messages',
    loadComponent: () => import('./pages/messages/messages').then((m) => m.MessagesComponent),
    canActivate: [authGuard],
  },
  {
    path: 'messages/:id',
    loadComponent: () => import('./pages/messages/thread').then((m) => m.ChatThreadComponent),
    canActivate: [authGuard],
  },
  {
    path: 'denied',
    loadComponent: () => import('./pages/auth/denied/denied').then((m) => m.DeniedComponent),
  },
  {
    path: 'not-found',
    loadComponent: () => import('./pages/errors/not-found/not-found').then((m) => m.NotFoundComponent),
  },

  // Renter
  {
    path: 'renter',
    loadComponent: () => import('./pages/dashboards/renter/renter-dashboard').then((m) => m.RenterDashboardComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'rent',
    loadComponent: () => import('./pages/dashboards/renter/renter-dashboard').then((m) => m.RenterDashboardComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'bookings',
    loadComponent: () => import('./pages/bookings/renter-bookings/renter-bookings').then((m) => m.RenterBookingsComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'rent/bookings',
    loadComponent: () => import('./pages/bookings/renter-bookings/renter-bookings').then((m) => m.RenterBookingsComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'bookings/:id',
    loadComponent: () => import('./pages/bookings/detail/booking-detail').then((m) => m.BookingDetailComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'rent/bookings/:id',
    loadComponent: () => import('./pages/bookings/detail/booking-detail').then((m) => m.BookingDetailComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'favorites',
    loadComponent: () => import('./pages/favorites/favorites').then((m) => m.RenterFavoritesComponent),
    canActivate: [renterGuard],
  },
  {
    path: 'payments',
    loadComponent: () => import('./pages/payments/renter-payments/renter-payments').then((m) => m.RenterPaymentsComponent),
    canActivate: [renterGuard],
  },

  // Owner
  {
    path: 'owner',
    loadComponent: () => import('./pages/dashboards/owner/owner-dashboard').then((m) => m.OwnerDashboardComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/properties',
    loadComponent: () => import('./pages/properties/owner-list/owner-list').then((m) => m.OwnerPropertiesComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/properties/new',
    loadComponent: () => import('./pages/properties/owner-form/owner-form').then((m) => m.OwnerPropertyFormComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/properties/:id/edit',
    loadComponent: () => import('./pages/properties/owner-form/owner-form').then((m) => m.OwnerPropertyFormComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/bookings',
    loadComponent: () => import('./pages/bookings/owner-bookings/owner-bookings').then((m) => m.OwnerBookingsComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/bookings/:id',
    loadComponent: () => import('./pages/bookings/detail/booking-detail').then((m) => m.BookingDetailComponent),
    canActivate: [ownerGuard],
  },
  {
    path: 'owner/payments',
    loadComponent: () => import('./pages/payments/owner-payments/owner-payments').then((m) => m.OwnerPaymentsComponent),
    canActivate: [ownerGuard],
  },

  // Shared payment detail (renter or owner audience)
  {
    path: 'payments/:id',
    loadComponent: () => import('./pages/payments/detail/payment-detail').then((m) => m.PaymentDetailComponent),
    canActivate: [authGuard],
  },

  // Notifications & Console
  {
    path: 'notifications',
    loadComponent: () => import('./pages/notifications/notifications').then((m) => m.NotificationsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'console',
    loadComponent: () => import('./pages/console/console-dashboard').then((m) => m.ConsoleDashboardComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/users',
    loadComponent: () => import('./pages/console/users/console-users').then((m) => m.ConsoleUsersComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/users/new',
    loadComponent: () => import('./pages/console/user-form/console-user-form').then((m) => m.ConsoleUserFormComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/properties',
    loadComponent: () => import('./pages/console/properties/console-properties').then((m) => m.ConsolePropertiesComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/bookings',
    loadComponent: () => import('./pages/console/bookings/console-bookings').then((m) => m.ConsoleBookingsComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/payments/payouts',
    loadComponent: () => import('./pages/console/payments/console-payments').then((m) => m.ConsolePaymentsComponent),
    data: { section: 'payouts' },
    canActivate: [adminGuard],
  },
  {
    path: 'console/payments/refunds',
    loadComponent: () => import('./pages/console/payments/console-payments').then((m) => m.ConsolePaymentsComponent),
    data: { section: 'refunds' },
    canActivate: [adminGuard],
  },
  {
    path: 'console/payments/settings',
    loadComponent: () => import('./pages/console/payments/console-payments').then((m) => m.ConsolePaymentsComponent),
    data: { section: 'settings' },
    canActivate: [adminGuard],
  },
  {
    path: 'console/payments',
    loadComponent: () => import('./pages/console/payments/console-payments').then((m) => m.ConsolePaymentsComponent),
    data: { section: 'payments' },
    pathMatch: 'full',
    canActivate: [adminGuard],
  },
  {
    path: 'console/notifications',
    loadComponent: () => import('./pages/console/notifications/console-notifications').then((m) => m.ConsoleNotificationsComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/settings',
    loadComponent: () => import('./pages/console/settings/console-settings').then((m) => m.ConsoleSettingsComponent),
    canActivate: [adminGuard],
  },
  {
    path: 'console/sessions',
    loadComponent: () => import('./pages/console/sessions/console-sessions').then((m) => m.ConsoleSessionsComponent),
    canActivate: [superadminGuard],
  },
  {
    path: 'console/audit-logs',
    loadComponent: () => import('./pages/console/audit/console-audit').then((m) => m.ConsoleAuditComponent),
    canActivate: [superadminGuard],
  },

  {
    path: '**',
    loadComponent: () => import('./pages/errors/not-found/not-found').then((m) => m.NotFoundComponent),
  },
];
