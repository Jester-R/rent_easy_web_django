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
  approval_status?: 'approved' | 'pending' | 'rejected';
  home_url: string;
  avatar_hue: number;
  avatar_url?: string;
  payout_method?: string;
  payout_account_name?: string;
  payout_account_number?: string;
  payout_bank_name?: string;
  payout_phone?: string;
  payout_note?: string;
  payout_updated_at?: string | null;
  has_payout_details?: boolean;
  date_joined?: string;
  last_login_at?: string | null;
}

export interface CategoryOption {
  value: string;
  label: string;
}

export interface Property {
  id: number;
  is_active: boolean;
  title: string;
  title_km?: string;
  location: string;
  location_km?: string;
  price_per_month: number;
  price_display: string;
  location_label: string;
  bedrooms: number;
  bathrooms: number;
  description: string;
  description_km?: string;
  category?: string;
  latitude?: number | null;
  longitude?: number | null;
  images?: string[];
  cover_image?: string;
  has_coordinates?: boolean;
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
  end_date?: string | null;
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
  payout_status?: string;
  payout_available_at?: string | null;
  created_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  cancelled_at?: string | null;
  can_approve?: boolean;
  can_reject?: boolean;
  can_cancel?: boolean;
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
  provider?: 'mock' | 'aba_payway' | string;
  provider_ref?: string;
  paid_at?: string | null;
  refund_status: 'None' | 'Pending' | 'Processed' | string;
  is_refunded: boolean;
  is_successful: boolean;
  can_refund_locally?: boolean;
  property?: Property | null;
  property_id?: number | null;
  property_title: string;
  booking_id?: number | null;
  user: UserBrief;
  user_id: number;
  created_at: string;
  refunded_at?: string | null;
}

/** Signed form returned by the API for ABA PayWay hosted checkout. */
export interface HostedCheckout {
  provider: string;
  action_url: string;
  method: string;
  fields: Record<string, string>;
}

export interface Refund {
  id: number;
  reference: string;
  amount: number;
  amount_display: string;
  reason: string;
  status: string;
  note: string;
  request_note: string;
  requested_by?: UserBrief | null;
  payment_id: number;
  booking_id: number;
  payment?: Payment;
  created_at: string;
  processed_at?: string | null;
}

export interface PayoutAccount {
  method: string;
  account_name: string;
  account_number: string;
  bank_name: string;
  phone: string;
  note: string;
  ready: boolean;
}

export interface Payout {
  id: number;
  reference: string;
  amount: number;
  amount_display: string;
  status: 'Scheduled' | 'Eligible' | 'Paid' | 'Cancelled' | string;
  available_at: string;
  paid_at?: string | null;
  note: string;
  owner: User;
  owner_id: number;
  payment_id: number;
  payment_reference: string;
  booking_id?: number | null;
  property_title: string;
  payout_method: string;
  payout_account_name: string;
  payout_account_number: string;
  payout_bank_name: string;
  payout_phone: string;
  can_pay: boolean;
  created_at: string;
}

export interface PayoutTotals {
  scheduled: number;
  eligible: number;
  paid: number;
}

export interface ConversationSummary {
  id: number;
  property_id: number;
  property_title: string;
  property_cover: string;
  renter_id: number;
  owner_id: number;
  other_party: UserBrief;
  last_message: string;
  last_message_at: string;
  unread: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender: UserBrief;
  sender_id: number;
  body: string;
  is_read: boolean;
  created_at: string;
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
  home_promotion: HomePromotion;
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

export interface HomePromotion {
  eyebrow_en: string;
  eyebrow_km: string;
  title_en: string;
  title_km: string;
  body_en: string;
  body_km: string;
  image_url: string;
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
    eligible_payouts?: number;
    eligible_payout_amount?: number;
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
  approval: string;
  roles: RoleOption[];
  approvals: RoleOption[];
  pending_count: number;
  total: number;
  page: number;
  page_size: number;
}

export interface ConsoleSettings {
  auto_approve_owners: boolean;
  property_categories: PropertyCategorySetting[];
  notification_messages: NotificationMessageSetting[];
  home_promotion: HomePromotion;
}

export interface PropertyCategorySetting {
  value: string;
  label_en: string;
  label_km: string;
}

export interface NotificationMessageSetting {
  key: string;
  body_key: string;
  label_en: string;
  label_km: string;
  title_en: string;
  title_km: string;
  body_en: string;
  body_km: string;
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
  page: number;
  page_size: number;
}

export interface ConsoleBookingsResponse {
  bookings: Booking[];
  query: string;
  status: string;
  status_counts: Record<string, number>;
  total: number;
  page: number;
  page_size: number;
}

export interface ConsolePaymentsResponse {
  payments: Payment[];
  refunds: Refund[];
  refunds_total: number;
  refund_page: number;
  refund_page_size: number;
  payouts: Payout[];
  payout_status: string;
  payout_counts: Record<string, number>;
  payout_totals: PayoutTotals;
  query: string;
  status: string;
  status_counts: Record<string, number>;
  total: number;
  page: number;
  page_size: number;
  payouts_total: number;
  payout_page: number;
  payout_page_size: number;
  revenue: number;
}
