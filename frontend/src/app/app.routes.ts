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
import { OwnerPaymentsComponent } from './pages/payments/owner-payments/owner-payments';
import { NotificationsComponent } from './pages/notifications/notifications';
import { ConsoleDashboardComponent } from './pages/console/console-dashboard';

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
  { path: 'favorites', component: RenterFavoritesComponent },
  { path: 'payments', component: RenterPaymentsComponent },

  // Owner
  { path: 'owner', component: OwnerDashboardComponent },
  { path: 'owner/properties', component: OwnerPropertiesComponent },
  { path: 'owner/properties/new', component: OwnerPropertyFormComponent },
  { path: 'owner/properties/:id/edit', component: OwnerPropertyFormComponent },
  { path: 'owner/bookings', component: OwnerBookingsComponent },
  { path: 'owner/payments', component: OwnerPaymentsComponent },

  // Notifications & Console
  { path: 'notifications', component: NotificationsComponent },
  { path: 'console', component: ConsoleDashboardComponent },

  { path: '**', redirectTo: '' },
];
