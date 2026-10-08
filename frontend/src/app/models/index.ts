export interface UserBrief {
  id: number;
  email: string;
  username: string;
  full_name: string;
  display_name: string;
  role: 'renter' | 'owner' | 'superadmin' | string;
}

export interface User extends UserBrief {
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  is_renter: boolean;
  is_owner: boolean;
  is_superadmin_role: boolean;
  home_url: string;
  avatar_hue: number;
  date_joined?: string;
  last_login_at?: string | null;
}

export interface Property {
  id: number;
  is_active: boolean;
  title: string;
  location: string;
  price_per_month: number;
  price_display: string;
  location_label: string;
  bedrooms: number;
  bathrooms: number;
  description: string;
  owner: UserBrief;
  owner_id: number;
  created_at: string;
  updated_at: string;
  is_favorite?: boolean;
  has_active_booking?: boolean;
  approved_bookings?: number;
  booking_count?: number;
  favorite_count?: number;
}

export interface Booking {
  id: number;
  reference: string;
  status: 'Pending' | 'Approved' | 'Confirmed' | 'Rejected' | 'Cancelled' | string;
  monthly_rent: number;
  rent_display: string;
  move_in_date?: string | null;
  lease_months: number;
  note: string;
  is_paid: boolean;
  property: Property;
  property_id: number;
  renter: UserBrief;
  renter_id: number;
  owner: UserBrief;
  owner_id: number;
  payment_id?: number | null;
  created_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  cancelled_at?: string | null;
}

export interface Payment {
  id: number;
  reference: string;
  amount: number;
  amount_display: string;
  refunded_amount: number;
  refunded_display: string;
  method: string;
  status: 'Pending' | 'Success' | 'Failed' | 'Refunded' | string;
  refund_status: 'None' | 'Pending' | 'Processed' | string;
  is_refunded: boolean;
  is_successful: boolean;
  property?: Property | null;
  property_id?: number | null;
  property_title: string;
  booking_id?: number | null;
  user: UserBrief;
  user_id: number;
  created_at: string;
  refunded_at?: string | null;
}

export interface Refund {
  id: number;
  reference: string;
  amount: number;
  amount_display: string;
  reason: string;
  status: string;
  note: string;
  payment_id: number;
  booking_id: number;
  payment?: Payment;
  created_at: string;
  processed_at?: string | null;
}

export interface AppNotification {
  id: number;
  kind: string;
  title_key: string;
  body_key: string;
  params: Record<string, any>;
  link?: string;
  action?: string;
  read: boolean;
  created_at: string;
}

export interface RenterDashboardData {
  stats: {
    available: number;
    bookings: number;
    active: number;
    pending: number;
    approved: number;
    favorites: number;
    payments: number;
    spend: number;
    refunded: number;
  };
  featured: Property[];
  suggested: Property[];
  recent_bookings: Booking[];
  recent_payments: Payment[];
  favorite_ids: number[];
}

export interface OwnerDashboardData {
  stats: {
    listings: number;
    pending: number;
    approved: number;
    rejected: number;
    cancelled: number;
    potential: number;
    revenue: number;
    favorites: number;
    bookings: number;
    payments: number;
  };
  properties: Property[];
  recent_bookings: Booking[];
  recent_payments: Payment[];
}

export interface LandingData {
  stats: {
    properties: number;
    owners: number;
    bookings: number;
    cities: number;
    avg_price: number;
    revenue: number;
  };
  featured: Property[];
  has_data: boolean;
  pending_bookings: number;
}

/* ----------------------------- Console (superadmin) ----------------------------- */

export interface Audit {
  id: number;
  action: string;
  entity: string;
  entity_id: string;
  summary: string;
  actor: UserBrief | null;
  created_at: string;
}

export interface ConsoleDashboardData {
  stats: {
    users: number;
    owners: number;
    renters: number;
    properties: number;
    bookings: number;
    payments: number;
    favorites: number;
    refunds: number;
    pending_refunds: number;
    revenue: number;
    refunded: number;
    avg_rent: number;
  };
  status_counts: Record<string, number>;
  monthly_rows: { month: string | null; total: number; n: number }[];
  top_properties: (Property & {
    revenue: number;
    booking_count: number;
    favorite_count: number;
  })[];
  role_breakdown: { role: string; n: number }[];
  recent_bookings: Booking[];
  recent_users: User[];
  audit_logs: Audit[];
}

export type RoleOption = { value: string; label: string };

export interface ConsoleUserItem extends User {
  property_count: number;
  booking_count: number;
}

export interface ConsoleUsersResponse {
  users: ConsoleUserItem[];
  query: string;
  role: string;
  roles: RoleOption[];
  total: number;
}

export type ConsolePropertyItem = Property & {
  favorite_count: number;
  booking_count: number;
};

export interface ConsolePropertiesResponse {
  properties: ConsolePropertyItem[];
  query: string;
  owner: string;
  owners: User[];
  total: number;
}

export interface ConsoleBookingsResponse {
  bookings: Booking[];
  query: string;
  status: string;
  status_counts: Record<string, number>;
  total: number;
}

export interface ConsolePaymentsResponse {
  payments: Payment[];
  refunds: Refund[];
  query: string;
  status: string;
  status_counts: Record<string, number>;
  total: number;
  revenue: number;
}
