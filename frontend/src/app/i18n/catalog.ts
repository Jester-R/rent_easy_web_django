import { app } from './pages/app';
import { bookingDetail } from './pages/booking-detail';
import { browse } from './pages/browse';
import { consoleBookings } from './pages/console-bookings';
import { consoleDashboard } from './pages/console-dashboard';
import { consolePayments } from './pages/console-payments';
import { consoleProperties } from './pages/console-properties';
import { consoleSettings } from './pages/console-settings';
import { consoleUserForm } from './pages/console-user-form';
import { consoleUsers } from './pages/console-users';
import { favorites } from './pages/favorites';
import { footer } from './pages/footer';
import { landing } from './pages/landing';
import { login } from './pages/login';
import { messages } from './pages/messages';
import { navbar } from './pages/navbar';
import { notifications } from './pages/notifications';
import { ownerBookings } from './pages/owner-bookings';
import { ownerDashboard } from './pages/owner-dashboard';
import { ownerForm } from './pages/owner-form';
import { ownerList } from './pages/owner-list';
import { ownerPayments } from './pages/owner-payments';
import { profile } from './pages/profile';
import { propertyDetail } from './pages/property-detail';
import { register } from './pages/register';
import { renterBookings } from './pages/renter-bookings';
import { renterDashboard } from './pages/renter-dashboard';
import { renterPayments } from './pages/renter-payments';
import { settings } from './pages/settings';
import { thread } from './pages/thread';

import type { Catalog, PageCatalog, TranslationEntry } from './types';

function expand(page: string, entries: PageCatalog): Record<string, TranslationEntry> {
  const out: Record<string, TranslationEntry> = {};
  for (const key of Object.keys(entries)) out[`${page}.${key}`] = entries[key];
  return out;
}

export const CATALOG: Catalog = {
  ...expand('app', app),
  ...expand('bookingDetail', bookingDetail),
  ...expand('browse', browse),
  ...expand('consoleBookings', consoleBookings),
  ...expand('consoleDashboard', consoleDashboard),
  ...expand('consolePayments', consolePayments),
  ...expand('consoleProperties', consoleProperties),
  ...expand('consoleSettings', consoleSettings),
  ...expand('consoleUserForm', consoleUserForm),
  ...expand('consoleUsers', consoleUsers),
  ...expand('favorites', favorites),
  ...expand('footer', footer),
  ...expand('landing', landing),
  ...expand('login', login),
  ...expand('messages', messages),
  ...expand('navbar', navbar),
  ...expand('notifications', notifications),
  ...expand('ownerBookings', ownerBookings),
  ...expand('ownerDashboard', ownerDashboard),
  ...expand('ownerForm', ownerForm),
  ...expand('ownerList', ownerList),
  ...expand('ownerPayments', ownerPayments),
  ...expand('profile', profile),
  ...expand('propertyDetail', propertyDetail),
  ...expand('register', register),
  ...expand('renterBookings', renterBookings),
  ...expand('renterDashboard', renterDashboard),
  ...expand('renterPayments', renterPayments),
  ...expand('settings', settings),
  ...expand('thread', thread),
};
