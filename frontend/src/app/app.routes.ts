import { Routes } from '@angular/router';
import { LandingComponent } from './pages/landing/landing';
import { BrowsePropertiesComponent } from './pages/properties/browse/browse';
import { PropertyDetailComponent } from './pages/properties/detail/detail';
import { LoginComponent } from './pages/auth/login/login';
import { RegisterComponent } from './pages/auth/register/register';
import { RoleSelectComponent } from './pages/auth/role-select/role-select';
import { ProfileComponent } from './pages/profile/profile';
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

export const routes: Routes = [
  { path: '', component: LandingComponent, pathMatch: 'full' },
  { path: 'browse', component: BrowsePropertiesComponent },
  { path: 'properties/:id', component: PropertyDetailComponent },
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'role-select', component: RoleSelectComponent },
  { path: 'profile', component: ProfileComponent },

  // Renter
  { path: 'renter', component: RenterDashboardComponent },
  { path: 'rent', component: RenterDashboardComponent },
  { path: 'bookings', component: RenterBookingsComponent },
  { path: 'rent/bookings', component: RenterBookingsComponent },
  { path: 'bookings/:id', component: BookingDetailComponent },
  { path: 'rent/bookings/:id', component: BookingDetailComponent },
  { path: 'favorites', component: RenterFavoritesComponent },
  { path: 'payments', component: RenterPaymentsComponent },

  // Owner
  { path: 'owner', component: OwnerDashboardComponent },
  { path: 'owner/properties', component: OwnerPropertiesComponent },
  { path: 'owner/properties/new', component: OwnerPropertyFormComponent },
  { path: 'owner/properties/:id/edit', component: OwnerPropertyFormComponent },
  { path: 'owner/bookings', component: OwnerBookingsComponent },
  { path: 'owner/bookings/:id', component: BookingDetailComponent },
  { path: 'owner/payments', component: OwnerPaymentsComponent },

  // Notifications & Console
  { path: 'notifications', component: NotificationsComponent },
  { path: 'console', component: ConsoleDashboardComponent },
  { path: 'console/users', component: ConsoleUsersComponent },
  { path: 'console/users/new', component: ConsoleUserFormComponent },
  { path: 'console/users/:id/edit', component: ConsoleUserFormComponent },
  { path: 'console/properties', component: ConsolePropertiesComponent },
  { path: 'console/bookings', component: ConsoleBookingsComponent },
  { path: 'console/payments', component: ConsolePaymentsComponent },

  { path: '**', redirectTo: '' },
];
