import { Routes } from '@angular/router';
import { LandingComponent } from './pages/landing/landing';
import { BrowsePropertiesComponent } from './pages/properties/browse/browse';
import { PropertyDetailComponent } from './pages/properties/detail/detail';
import { LoginComponent } from './pages/auth/login/login';
import { RegisterComponent } from './pages/auth/register/register';
import { RoleSelectComponent } from './pages/auth/role-select/role-select';
import { ProfileComponent } from './pages/profile/profile';
import { SettingsComponent } from './pages/settings/settings';
import { MessagesComponent } from './pages/messages/messages';
import { ChatThreadComponent } from './pages/messages/thread';
import { RenterDashboardComponent } from './pages/dashboards/renter/renter-dashboard';
import { RenterBookingsComponent } from './pages/bookings/renter-bookings/renter-bookings';
import { RenterFavoritesComponent } from './pages/favorites/favorites';
import { RenterPaymentsComponent } from './pages/payments/renter-payments/renter-payments';
import { OwnerDashboardComponent } from './pages/dashboards/owner/owner-dashboard';
import { OwnerPropertiesComponent } from './pages/properties/owner-list/owner-list';
import { OwnerPropertyFormComponent } from './pages/properties/owner-form/owner-form';
import { OwnerBookingsComponent } from './pages/bookings/owner-bookings/owner-bookings';
import { BookingDetailComponent } from './pages/bookings/detail/booking-detail';
import { OwnerPaymentsComponent } from './pages/payments/owner-payments/owner-payments';
import { NotificationsComponent } from './pages/notifications/notifications';
import { ConsoleDashboardComponent } from './pages/console/console-dashboard';
import { ConsoleUsersComponent } from './pages/console/users/console-users';
import { ConsoleUserFormComponent } from './pages/console/user-form/console-user-form';
import { ConsolePropertiesComponent } from './pages/console/properties/console-properties';
import { ConsoleBookingsComponent } from './pages/console/bookings/console-bookings';
import { ConsolePaymentsComponent } from './pages/console/payments/console-payments';
import { ConsoleSettingsComponent } from './pages/console/settings/console-settings';
import { PaymentDetailComponent } from './pages/payments/detail/payment-detail';
import { DeniedComponent } from './pages/auth/denied/denied';
import { NotFoundComponent } from './pages/errors/not-found/not-found';
import {
  adminGuard,
  authGuard,
  guestGuard,
  ownerGuard,
  renterGuard,
} from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent, pathMatch: 'full' },
  { path: 'browse', component: BrowsePropertiesComponent },
  { path: 'properties/:id', component: PropertyDetailComponent },
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },
  { path: 'role-select', component: RoleSelectComponent, canActivate: [guestGuard] },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [authGuard] },
  { path: 'messages', component: MessagesComponent, canActivate: [authGuard] },
  { path: 'messages/:id', component: ChatThreadComponent, canActivate: [authGuard] },
  { path: 'denied', component: DeniedComponent },
  { path: 'not-found', component: NotFoundComponent },

  // Renter
  { path: 'renter', component: RenterDashboardComponent, canActivate: [renterGuard] },
  { path: 'rent', component: RenterDashboardComponent, canActivate: [renterGuard] },
  { path: 'bookings', component: RenterBookingsComponent, canActivate: [renterGuard] },
  { path: 'rent/bookings', component: RenterBookingsComponent, canActivate: [renterGuard] },
  { path: 'bookings/:id', component: BookingDetailComponent, canActivate: [renterGuard] },
  { path: 'rent/bookings/:id', component: BookingDetailComponent, canActivate: [renterGuard] },
  { path: 'favorites', component: RenterFavoritesComponent, canActivate: [renterGuard] },
  { path: 'payments', component: RenterPaymentsComponent, canActivate: [renterGuard] },

  // Owner
  { path: 'owner', component: OwnerDashboardComponent, canActivate: [ownerGuard] },
  { path: 'owner/properties', component: OwnerPropertiesComponent, canActivate: [ownerGuard] },
  { path: 'owner/properties/new', component: OwnerPropertyFormComponent, canActivate: [ownerGuard] },
  { path: 'owner/properties/:id/edit', component: OwnerPropertyFormComponent, canActivate: [ownerGuard] },
  { path: 'owner/bookings', component: OwnerBookingsComponent, canActivate: [ownerGuard] },
  { path: 'owner/bookings/:id', component: BookingDetailComponent, canActivate: [ownerGuard] },
  { path: 'owner/payments', component: OwnerPaymentsComponent, canActivate: [ownerGuard] },

  // Shared payment detail (renter or owner audience)
  { path: 'payments/:id', component: PaymentDetailComponent, canActivate: [authGuard] },

  // Notifications & Console
  { path: 'notifications', component: NotificationsComponent, canActivate: [authGuard] },
  { path: 'console', component: ConsoleDashboardComponent, canActivate: [adminGuard] },
  { path: 'console/users', component: ConsoleUsersComponent, canActivate: [adminGuard] },
  { path: 'console/users/new', component: ConsoleUserFormComponent, canActivate: [adminGuard] },
  { path: 'console/users/:id/edit', component: ConsoleUserFormComponent, canActivate: [adminGuard] },
  { path: 'console/properties', component: ConsolePropertiesComponent, canActivate: [adminGuard] },
  { path: 'console/bookings', component: ConsoleBookingsComponent, canActivate: [adminGuard] },
  { path: 'console/payments', component: ConsolePaymentsComponent, canActivate: [adminGuard] },
  { path: 'console/settings', component: ConsoleSettingsComponent, canActivate: [adminGuard] },

  { path: '**', component: NotFoundComponent },
];
