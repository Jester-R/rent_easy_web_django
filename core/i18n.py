"""
RentEasy Web translation catalogue.

Mirrors the Flutter app's ``AppText`` helper: every string carries an English
and a Khmer variant, mirroring ``AppText.text(english, khmer)``.
"""

from __future__ import annotations

LANGUAGES = {
    "en": {
        "code": "en",
        "label": "English",
        "native_label": "English",
        "flag": "EN",
    },
    "km": {
        "code": "km",
        "label": "Khmer",
        "native_label": "ខ្មែរ",
        "flag": "ខ្មែរ",
    },
}

DEFAULT_LANGUAGE = "en"

SUPPORTED_LANGUAGE_CODES = tuple(LANGUAGES.keys())

# ---------------------------------------------------------------------------
# Keyed catalogue: key -> (english, khmer)
# ---------------------------------------------------------------------------

CATALOG: dict[str, tuple[str, str]] = {
    # Brand / marketing
    "app_name": ("Rent Easy", "រើន អ៊ីសី"),
    "slogan": (
        "Find Your Perfect Home, Easily.",
        "ស្វែងរកផ្ទះដែលស័ក្តិសមសម្រាប់អ្នកបានយ៉ាងងាយស្រួល។",
    ),
    "platform_tag": ("Web Platform", "វេទិកា វែប"),
    "web_hero_title": (
        "Rent smarter across the web",
        "ជួលផ្ទះដែលភ្លាម្បងនៅលើវេទិកាវែប",
    ),
    "web_hero_sub": (
        "The complete RentEasy experience — listings, booking requests, payments and refunds — rebuilt for the browser with the same features as the mobile app.",
        "បទពិសោធន៍ RentEasy ពេញលេញ — ការបង្ហាញផ្ទះ សំណើកក់ ការទូទាត់ និងសងវិញទឹកប្រាក់ — បានសាកសង់ឡើងវិញសម្រាប់កម្មវិធីរុករកដោយមានមុខងារដដែលខុសគ្នានឹងកម្មវិធីស្លាប់។",
    ),
    "web_feature_listings": (
        "Smart listing filters",
        "ការច្រោះតម្រងផ្ទះដែលឆ្រាញ់",
    ),
    "web_feature_booking": (
        "End-to-end booking requests",
        "សំណើកក់ពេញលេញពីដើមដល់ចុង",
    ),
    "web_feature_payments": (
        "Mock checkout with refunds",
        "ការទូទាត់ម៉ុក និងការសងវិញទឹកប្រាក់",
    ),
    "web_feature_admin": (
        "Full superadmin console",
        "ផ្ទាំងគ្រប់គ្រងអ្នកគ្រប់គ្រងពេញលេញ",
    ),
    "cta_browse": ("Browse Properties", "រកមើលអចលនទ្រព្យ"),
    "cta_create_account": ("Create account", "បង្កើតគណនី"),
    "cta_sign_in": ("Sign in", "ចូលគណនី"),
    "demo_hint": (
        "Demo logins",
        "គណនីសាកល្បង",
    ),

    # Generic actions
    "login": ("Login", "ចូលគណនី"),
    "register": ("Register", "ចុះឈ្មោះ"),
    "logout": ("Logout", "ចាកចេញ"),
    "password": ("Password", "ពាក្យសម្ងាត់"),
    "email": ("Email", "អ៊ីមែល"),
    "full_name": ("Full Name", "ឈ្មោះពេញ"),
    "username": ("Username", "ឈ្មោះអធីប្រវត្តិ"),
    "create": ("Create", "បង្កើត"),
    "save": ("Save", "រក្សាទុក"),
    "save_changes": ("Save Changes", "រក្សាទុកការកែប្រែ"),
    "cancel": ("Cancel", "បោះបង់"),
    "close": ("Close", "បិទ"),
    "back": ("Back", "ត្រឡប់ក្រោយ"),
    "edit": ("Edit", "កែប្រែ"),
    "delete": ("Delete", "លុប"),
    "details": ("Details", "ព័ត៌មានលម្អិត"),
    "confirm": ("Confirm", "បញ្ជាក់"),
    "apply": ("Apply", "អនុវត្ត"),
    "reset": ("Reset", "កំណត់ឡើងវិញ"),
    "clear_all": ("Clear all", "សម្អាតទាំងអស់"),
    "select_all": ("Select all", "ជ្រើសទាំងអស់"),
    "search": ("Search", "ស្វែងរក"),
    "filter": ("Filter", "តម្រង"),
    "loading": ("Loading…", "កំពុងផ្ទុក…"),
    "no_results": ("No results", "មិនមានលទ្ធផល"),
    "actions": ("Actions", "សកម្មភាព"),
    "optional": ("optional", "មិនចាំបាច់"),

    # Navigation / sections
    "home": ("Home", "ដើម"),
    "dashboard": ("Dashboard", "ផ្ទាំងគ្រប់គ្រង"),
    "properties": ("Properties", "អចលនទ្រព្យ"),
    "my_properties": ("My Properties", "អចលនទ្រព្យរបស់ខ្ញុំ"),
    "favorites": ("Favorites", "ចំណូលចិត្ត"),
    "bookings": ("Bookings", "ការកក់"),
    "my_bookings": ("My Bookings", "ការកក់របស់ខ្ញុំ"),
    "payments": ("Payments", "ការទូទាត់"),
    "profile": ("Profile", "ប្រវត្តិរូប"),
    "users": ("Users", "អ្នកប្រើ"),
    "more": ("More", "ផ្សេងៗ"),
    "manage": ("Manage", "គ្រប់គ្រង"),
    "superadmin_dashboard": ("Superadmin Dashboard", "ផ្ទាំងគ្រប់គ្រងអ្នកគ្រប់គ្រងជាន់ខ្ពស់"),
    "owner_workspace": ("Owner Workspace", "កន្លែងការងាររបស់ម្ចាស់"),
    "renter_dashboard": ("Renter Dashboard", "ផ្ទាំងគ្រប់គ្រងអ្នកជួល"),
    "demo_accounts": ("Demo accounts", "គណនីសាកល្បង"),

    # Roles
    "role": ("Role", "តួនាទី"),
    "renter": ("Renter", "អ្នកជួល"),
    "owner": ("Owner", "ម្ចាស់"),
    "property_owner": ("Property Owner", "ម្ចាស់អចលនទ្រព្យ"),
    "super_admin": ("Super Admin", "អ្នកគ្រប់គ្រងជាន់ខ្ពស់"),
    "unknown": ("Unknown", "មិនស្គាល់"),
    "email_user_id": ("Email / User ID", "អ៊ីមែល / លេខសម្គាល់អ្នកប្រើ"),
    "select_role": ("Select Role", "ជ្រើសតួនាទី"),
    "select_role_hint": (
        "Choose your role to complete registration.",
        "ជ្រើសតួនាទីរបស់អ្នកដើម្បីបញ្ចប់ការចុះឈ្មោះ។",
    ),
    "renter_role_hint": (
        "Browse and request properties",
        "រកមើល និង ស្នើសុំអចលនទ្រព្យ",
    ),
    "owner_role_hint": (
        "Create and manage property listings",
        "បង្កើត និង គ្រប់គ្រងបញ្ជីអចលនទ្រព្យ",
    ),

    # Preferences
    "preferences": ("Preferences", "ចំណូលចិត្ត"),
    "appearance": ("Appearance", "រូបរាង"),
    "theme": ("Theme", "រចនាប័ទ្ម"),
    "change_theme": ("Change theme", "ប្តូររចនាប័ទ្ម"),
    "light_mode": ("Light mode", "របៀបពន្លឺ"),
    "dark_mode": ("Dark mode", "របៀបងងឹត"),
    "theme_hint": (
        "Choose light or dark mode",
        "ជ្រើសរើសរវាងរបៀបពន្លឺ និង របៀបងងឹត",
    ),
    "language": ("Language", "ភាសា"),
    "change_language": ("Change language", "ប្តូរភាសា"),
    "language_hint": (
        "Choose between Khmer and English",
        "ជ្រើសរើសរវាងភាសាខ្មែរ និង អង់គ្លេស",
    ),
    "english": ("English", "អង់គ្លេស"),
    "khmer": ("Khmer", "ខ្មែរ"),

    # Property fields
    "add_property": ("Add Property", "បន្ថែមអចលនទ្រព្យ"),
    "edit_property": ("Edit Property", "កែប្រែអចលនទ្រព្យ"),
    "description": ("Description", "ការពិពណ៌នា"),
    "title_label": ("Title", "ចំណងជើង"),
    "location": ("Location", "ទីតាំង"),
    "price_per_month": ("Price Per Month", "តម្លៃក្នុងមួយខែ"),
    "bedrooms": ("Bedrooms", "បន្ទប់គេង"),
    "bathrooms": ("Bathrooms", "បន្ទប់ទឹក"),
    "month": ("month", "ខែ"),
    "months": ("months", "ខែ"),
    "property_detail": ("Property Detail", "ព័ត៌មានលម្អិតអចលនទ្រព្យ"),
    "property_id": ("Property ID", "លេខសម្គាល់អចលនទ្រព្យ"),
    "owner_id": ("Owner ID", "លេខសម្គាល់ម្ចាស់"),
    "city_access": ("City Access", "ងាយស្រួលទៅកាន់ទីក្រុង"),
    "wifi_ready": ("Wi-Fi Ready", "មាន Wi-Fi រួចជាស្រេច"),
    "favorite": ("Favorite", "ចំណូលចិត្ត"),
    "request_booking": ("Request Booking", "ស្នើសុំការកក់"),
    "already_booked": ("Already Booked", "បានកក់រួចហើយ"),
    "remove_favorite": ("Remove from favorites", "ដកចេញពីចំណូលចិត្ត"),

    # Property list / filters
    "filter_properties": ("Filter Properties", "តម្រងអចលនទ្រព្យ"),
    "all_locations": ("All Locations", "ទីតាំងទាំងអស់"),
    "select_location": ("Select location", "ជ្រើសទីតាំង"),
    "sort_by": ("Sort by", "តម្រៀបតាម"),
    "sort_recommended": ("Recommended", "ណែនាំ"),
    "sort_price_low": ("Price: Low to High", "តម្លៃ៖ ទាបទៅខ្ពស់"),
    "sort_price_high": ("Price: High to Low", "តម្លៃ៖ ខ្ពស់ទៅទាប"),
    "sort_bedrooms": ("Bedrooms", "បន្ទប់គេង"),
    "any": ("Any", "ណាមួយ"),
    "max_price": ("Max price", "តម្លៃអតិបរមា"),
    "apply_filters": ("Apply Filters", "អនុវត្តតម្រង"),
    "bedrooms_min": ("{n}+ Bedrooms", "{n}+ បន្ទប់គេង"),
    "max_price_chip": ("Max ${amount}", "អតិបរមា ${amount}"),
    "search_placeholder": (
        "Search by title, area, or neighborhood",
        "ស្វែងរកតាមចំណងជើង តំបន់ ឬ សង្កាត់",
    ),
    "properties_found": ("{n} properties found", "រកឃើញអចលនទ្រព្យ {n}"),
    "average_price": ("Average price {amount}/month", "តម្លៃមធ្យម {amount}/ខែ"),
    "no_properties_match": (
        "No properties match your filters. Try widening your search.",
        "មិនមានអចលនទ្រព្យដែលត្រូវនឹងលក្ខខណ្ឌតម្រងរបស់អ្នកទេ។ សូមពិនិត្យការស្វែងរករបស់អ្នក។",
    ),
    "no_properties_yet": ("No properties yet", "មិនទាន់មានអចលនទ្រព្យទេ"),
    "no_properties_owner_hint": (
        "No properties yet. Add your first listing.",
        "មិនទាន់មានអចលនទ្រព្យទេ។ បន្ថែមបញ្ជីដំបូងរបស់អ្នក។",
    ),
    "no_favorites_yet": (
        "No favorite properties yet",
        "មិនទាន់មានអចលនទ្រព្យចំណូលចិត្តទេ",
    ),
    "save_property": ("Save Property", "រក្សាទុកអចលនទ្រព្យ"),
    "confirm_delete_property": (
        "Delete this property listing? This cannot be undone.",
        "លុបបញ្ជីអចលនទ្រព្យនេះ? សកម្មភាពនេះមិនអាចត្រឡប់វិញបានទេ។",
    ),

    # Booking
    "booking_request": ("Booking Request", "សំណើកក់"),
    "booking_details": ("Booking Details", "ព័ត៌មានលម្អិតការកក់"),
    "booking_id": ("Booking ID", "លេខសម្គាល់ការកក់"),
    "renter_id": ("Renter ID", "លេខសម្គាល់អ្នកជួល"),
    "monthly_rent": ("Monthly Rent", "ថ្លៃជួលប្រចាំខែ"),
    "lease_duration": ("Lease Duration", "រយៈពេលជួល"),
    "lease_months": ("Lease Months", "ចំនួនខែជួល"),
    "move_in_date": ("Move-in Date", "កាលបរិច្ឆេទចូលនៅ"),
    "preferred_move_in": (
        "Preferred Move-in Date",
        "កាលបរិច្ឆេទចូលនៅដែលចង់បាន",
    ),
    "requested_at": ("Requested At", "បានស្នើនៅ"),
    "linked_payment": ("Linked Payment", "ការទូទាត់ដែលភ្ជាប់"),
    "note": ("Note", "កំណត់ចំណាំ"),
    "renter_message": ("Renter Message", "សាររបស់អ្នកជួល"),
    "message_to_owner": ("Message to owner", "សារទៅម្ចាស់"),
    "message_placeholder": (
        "Tell the owner when you plan to move in…",
        "ប្រាប់ម្ចាស់ថាអ្នកគ្រោះត្រៀមចូលនៅពេលណា…",
    ),
    "lease_term": ("Lease Term (months)", "រយៈពេលជួល (ខែ)"),
    "not_specified": ("Not specified", "មិនបានបញ្ជាក់"),
    "not_selected": ("Not selected", "មិនបានជ្រើសរើស"),
    "not_set": ("Not set", "មិនបានកំណត់"),
    "select": ("Select", "ជ្រើស"),
    "send_booking_request": ("Send Booking Request", "ផ្ញើសំណើកក់"),
    "request_title": (
        "Request {title} ({amount}/month)",
        "ស្នើសុំ {title} ({amount}/ខែ)",
    ),
    "no_bookings_yet": ("No bookings yet", "មិនទាន់មានការកក់ទេ"),
    "no_bookings_found": ("No bookings found", "មិនមានការកក់ត្រូវបានរកឃើញទេ"),
    "no_booking_requests": ("No booking requests yet", "មិនទាន់មានសំណើកក់ទេ"),
    "booking_sent": (
        "Booking request sent. Pay after owner approval.",
        "សំណើកក់ត្រូវបានផ្ញើ។ ទូទាត់បន្ទាប់ពីម្ចាស់អនុម័ត។",
    ),
    "active_booking_exists": (
        "You already have a pending or approved booking for this property",
        "អ្នកមានសំណើកក់ដែលកំពុងរង់ចាំ ឬត្រូវបានអនុម័តសម្រាប់អចលនទ្រព្យនេះរួចហើយ",
    ),
    "cancel_request": ("Cancel Request", "បោះបង់សំណើ"),
    "confirm_cancel_booking": (
        "Cancel Booking Request?",
        "បោះបង់សំណើកក់?",
    ),
    "confirm_cancel_body": (
        "This will withdraw your request for {title}. The owner will no longer see it as pending.",
        "វានឹងដកសំណើរបស់អ្នកសម្រាប់ {title}។ ម្ចាស់នឹងមិនទាន់ឃើញវាជាសំណើកំពុងរង់ចាំទេ។",
    ),
    "keep_request": ("Keep Request", "រក្សាសំណើទុក"),
    "approve": ("Approve", "អនុម័ត"),
    "reject": ("Reject", "បដិសេធ"),
    "confirm_approve_title": ("Approve Booking Request?", "អនុម័តសំណើកក់?"),
    "confirm_approve_body": (
        "Approve the booking from {renter} for {title} at {amount}/month for {months} months.",
        "អនុម័តការកក់ពី {renter} សម្រាប់ {title} តម្លៃ {amount}/ខែ សម្រាប់ {months} ខែ។",
    ),
    "confirm_reject_title": ("Reject Booking Request?", "បដិសេធសំណើកក់?"),
    "confirm_reject_body": (
        "Reject the booking from {renter} for {title}? The renter will not be able to pay.",
        "បដិសេធការកក់ពី {renter} សម្រាប់ {title}? អ្នកជួលនឹងមិនអាចទូទាត់បានទេ។",
    ),
    "recent_booking_activity": ("Recent Booking Activity", "សកម្មភាពកក់ថ្មីៗ"),
    "no_booking_activity": ("No booking activity yet.", "មិនទាន់មានសកម្មភាពកក់ទេ។"),
    "invalid_transition": (
        "This booking can no longer be changed.",
        "ការកក់នេះមិនអាចកែប្រែបានទេ។",
    ),
    "not_authorized": (
        "You are not allowed to perform this action.",
        "អ្នកមិនមានសិទ្ធិធ្វើសកម្មភាពនេះទេ។",
    ),

    # Payments
    "payment_details": ("Payment Details", "ព័ត៌មានលម្អិតការទូទាត់"),
    "payment_id": ("Payment ID", "លេខសម្គាល់ការទូទាត់"),
    "user_id": ("User ID", "លេខសម្គាល់អ្នកប្រើ"),
    "amount": ("Amount", "ចំនួនទឹកប្រាក់"),
    "method": ("Method", "វិធីសាស្ត្រ"),
    "payment_method": ("Payment Method", "វិធីសាស្ត្រទូទាត់"),
    "status": ("Status", "ស្ថានភាព"),
    "created_at": ("Created At", "បានបង្កើតនៅ"),
    "refund_status": ("Refund Status", "ស្ថានភាពសងប្រាក់វិញ"),
    "refunded_amount": ("Refunded Amount", "ចំនួនទឹកប្រាក់ដែលបានសងវិញ"),
    "refunded_at": ("Refunded At", "បានសងវិញនៅ"),
    "refunds": ("Refunds", "ការសងវិញទឹកប្រាក់"),
    "process_refund": ("Process Refund", "ដំណើរការសងវិញទឹកប្រាក់"),
    "pay_now": ("Pay Now", "ទូទាត់ឥឡូវ"),
    "pay_approved_booking": ("Pay Approved Booking", "ទូទាត់ការកក់ដែលបានអនុម័ត"),
    "pay_booking_body": (
        "Settle {amount} for {title} using one of the supported mock methods.",
        "បង់ប្រាក់ {amount} សម្រាប់ {title} ដោយប្រើវិធីទូទាត់ម៉ុកដែលមាន។",
    ),
    "paying": ("Processing…", "កំពុងដំណើរការ…"),
    "payment_success": ("Payment Success", "ការទូទាត់បានជោគជ័យ"),
    "payment_failed": (
        "Payment failed. Try again.",
        "ការទូទាត់បរាជ័យ។ សូមព្យាយាមម្តងទៀត។",
    ),
    "payment_recorded": ("Payment recorded", "ការទូទាត់ត្រូវបានកត់ត្រា"),
    "no_payments_yet": ("No payments yet", "មិនទាន់មានការទូទាត់ទេ"),
    "no_payment_history": ("No payment history yet", "មិនទាន់មានប្រវត្តិការទូទាត់ទេ"),
    "method_aba": ("ABA Pay (Mock)", "ABA Pay (ម៉ុក)"),
    "method_wing": ("Wing (Mock)", "Wing (ម៉ុក)"),
    "method_card": ("Credit Card (Mock)", "កាតឥណ្ឌង (ម៉ុក)"),
    "pay": ("Pay", "ទូទាត់"),

    # Status labels
    "status_pending": ("Pending", "កំពុងរង់ចាំ"),
    "status_approved": ("Approved", "បានអនុម័ត"),
    "status_rejected": ("Rejected", "បានបដិសេធ"),
    "status_cancelled": ("Cancelled", "បានបោះបង់"),
    "status_success": ("Success", "ជោគជ័យ"),
    "status_failed": ("Failed", "បរាជ័យ"),
    "status_none": ("None", "គ្មាន"),
    "status_processed": ("Processed", "បានដំណើរការ"),
    "status_refunded": ("Refunded", "បានសងវិញ"),
    "status_active": ("Active", "សកម្ម"),
    "all": ("All", "ទាំងអស់"),

    # Notifications
    "notifications": ("Notifications", "ការជូនដំណឹង"),
    "mark_all_read": ("Mark all as read", "សម្គាល់ថាបានអានទាំងអស់"),
    "no_notifications": ("You're all caught up", "អ្នកបានអានអី្យយម្រុងរួចហើយ"),
    "no_notifications_body": (
        "New booking requests and payment activity will show up here.",
        "សំណើកក់ថ្មី និងសកម្មភាពទូទាត់នឹងបង្ហាញនៅទីនេះ។",
    ),
    "notif_new_request": ("New booking request", "សំណើកក់ថ្មី"),
    "notif_new_request_body": (
        "{renter} requested {title}",
        "{renter} បានស្នើសុំ {title}",
    ),
    "notif_booking_update": ("Booking updated", "ការកក់ត្រូវបានធ្វើបច្ចុប្បន្នភាព"),
    "notif_booking_update_body": (
        "Your booking for {title} is now {status}",
        "ការកក់របស់អ្នកសម្រាប់ {title} ឥឡូវនេះជា {status}",
    ),
    "notif_payment_received": ("Payment received", "ទទួលបានការទូទាត់"),
    "notif_payment_received_body": (
        "{renter} paid {amount} for {title}",
        "{renter} បានបង់ {amount} សម្រាប់ {title}",
    ),
    "notif_booking_approved": ("Booking approved", "ការកក់ត្រូវបានអនុម័ត"),
    "notif_booking_approved_body": (
        "Your booking for {title} was approved. Complete payment now.",
        "ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានអនុម័ត។ បង់ការទូទាត់ឥឡូវនេះ។",
    ),
    "notif_booking_approved_paid": (
        "Your booking for {title} was approved and payment confirmed.",
        "ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានអនុម័ត និងការទូទាត់ត្រូវបានបញ្ជាក់។",
    ),
    "notif_booking_cancelled": ("Booking cancelled", "ការកក់ត្រូវបានបោះបង់"),
    "notif_booking_cancelled_body": (
        "The booking for {title} was cancelled and eligible for refund.",
        "ការកក់សម្រាប់ {title} ត្រូវបានបោះបង់ និងមានសិទ្ធិសងវិញទឹកប្រាក់។",
    ),
    "notif_booking_rejected": ("Booking rejected", "ការកក់ត្រូវបានបដិសេធ"),
    "notif_booking_rejected_body": (
        "Your booking for {title} was rejected.",
        "ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានបដិសេធ។",
    ),
    "notif_refund_processed": ("Refund processed", "សងវិញទឹកប្រាក់ត្រូវបានដំណើរការ"),
    "notif_refund_processed_body": (
        "{amount} was refunded for {title}",
        "{amount} ត្រូវបានសងវិញសម្រាប់ {title}",
    ),

    # Owner dashboard stats
    "stat_active_listings": ("Active Listings", "បញ្ជីសកម្ម"),
    "stat_pending_requests": ("Pending Requests", "សំណើកំពុងរង់ចាំ"),
    "stat_approved_deals": ("Approved Deals", "ការកក់ដែលបានអនុម័ត"),
    "stat_monthly_potential": ("Monthly Potential", "ចំណេញប្រចាំខែ"),
    "pending_requests_line": (
        "You have {n} request(s) waiting for action…",
        "អ្នកមានសំណើ {n} ដែលកំពុងរង់ចាំការដំណើរការ…",
    ),
    "no_pending_requests_line": (
        "No pending requests right now…",
        "មិនមានសំណើកំពុងរង់ចាំឡើយទេ…",
    ),

    # Superadmin
    "stat_users": ("Users", "អ្នកប្រើ"),
    "stat_bookings": ("Bookings", "ការកក់"),
    "stat_payments": ("Payments", "ការទូទាត់"),
    "stat_revenue": ("Revenue", "ចំណេញ"),
    "revenue_note": ("Successful payments only", "គិតតែការទូទាត់ដែលជោគជ័យ"),
    "new_user": ("New user", "អ្នកប្រើថ្មី"),
    "new_property": ("New property", "អចលនទ្រព្យថ្មី"),
    "new_booking": ("New booking", "ការកក់ថ្មី"),
    "new_payment": ("New payment", "ការទូទាត់ថ្មី"),
    "no_users_found": ("No users found", "មិនមានអ្នកប្រើទេ"),
    "selected_count": ("{n} selected", "បានជ្រើសរើស {n}"),
    "confirm_bulk_delete": (
        "Delete {n} selected record(s)? This cannot be undone.",
        "លុបកំណត់ត្រា {n} ដែលបានជ្រើសរើស? សកម្មភាពនេះមិនអាចត្រឡប់វិញបានទេ។",
    ),
    "search_users": ("Search by name, email or username", "ស្វែងរកតាមឈ្មោះ អ៊ីមែល ឬឈ្មោះអធីប្រវត្តិ"),
    "admin_only": ("Superadmin access required", "ត្រូវការសិទ្ធិអ្នកគ្រប់គ្រងជាន់ខ្ពស៍"),
    "server_error": ("Something went wrong on our side", "មានបញ្ហាបច្ចេកទេសនៅទូទាត់យើង"),
    "error_generic": ("An unexpected error occurred", "ការកំហុសមិនបានរំពឹងទុកបានកើតឡើង"),
    "account_created": ("Account created successfully", "គណនីត្រូវបានបង្កើតដោយជោគជ័យ"),
    "account_updated": ("Account updated successfully", "គណនីត្រូវបានធ្វើបច្ចុប្បន្នភាពដោយជោគជ័យ"),
    "leave_blank_password": (
        "Leave blank to keep current password",
        "ទុកទទេដើម្បីរក្សាពាក្យសម្ងាត់បច្ចុប្បន្ន",
    ),
    "email_taken": ("Email or username already in use", "អ៊ីមែល ឬ ឈ្មោះអធីប្រវត្តិនេះកំពុងត្រូវបានប្រើរួចហើយ"),
    "email_not_found": ("Username not found. Please register first.", "រកមិនឃើញឈ្មោះអ្នកប្រើទេ។ សូមចុះឈ្មោះជាមុនសិន។"),
    "invalid_credentials": ("Invalid credentials", "ព័ត៌មានចូលគណនីមិនត្រឹមត្រូវ"),
    "account_incomplete": (
        "Account setup incomplete. Please register again.",
        "ការរៀបចំគណនីមិនទាន់ពេញលេញ។ សូមចុះឈ្មោះម្តងទៀត។",
    ),
    "registration_complete": (
        "Registration complete. Please login.",
        "ការចុះឈ្មោះបានបញ្ចប់។ សូមចូលគណនី។",
    ),
    "field_required": ("{field} is required", "ត្រូវការបំពេញ {field}"),
    "email_required": ("Email is required", "ត្រូវការបំពេញអ៊ីមែល"),
    "valid_email": ("Enter a valid email", "សូមបញ្ចូលអ៊ីមែលត្រឹមត្រូវ"),
    "username_required": ("Username is required", "ត្រូវការបំពេញឈ្មោះអធីប្រវត្តិ"),
    "username_rule": (
        "Use 3-30 chars: letters, numbers, ., _, -",
        "ប្រើ 3-30 តួអក្សរ៖ អក្សរ លេខ ., _, -",
    ),
    "email_or_username_required": (
        "Email or username is required",
        "ត្រូវការបំពេញអ៊ីមែល ឬ ឈ្មោះអធីប្រវត្តិ",
    ),
    "login_identifier_label": ("Email or Username", "អ៊ីមែល ឬ ឈ្មោះអធីប្រវត្តិ"),
    "login_identifier_placeholder": (
        "Enter email or username",
        "បញ្ចូលអ៊ីមែល ឬ ឈ្មោះអធីប្រវត្តិ",
    ),
    "password_confirm": ("Confirm Password", "បញ្ជាក់ពាក្យសម្ងាត់"),
    "passwords_dont_match": ("Passwords do not match", "ពាក្យសម្ងាត់មិនត្រូវគ្នា"),
    "price_required": ("Enter a valid price", "បញ្ចូលតម្លៃត្រឹមត្រូវ"),
    "invalid_number": ("Enter a valid number", "បញ្ចូលលេខត្រឹមត្រូវ"),
    "owner_required": ("Select an owner", "ជ្រើសម្ចាស់"),
    "renter_required": ("Select a renter", "ជ្រើសអ្នកជួល"),
    "property_required": ("Select a property", "ជ្រើសអចលនទ្រព្យ"),
    "signup_headline": ("Create your RentEasy account", "បង្កើតគណនី RentEasy របស់អ្នក"),
    "login_headline": ("Welcome back to RentEasy", "សូមស្វាគមន៍ត្រឡប់មក RentEasy"),
    "login_subtitle": (
        "Sign in with your email or username to continue.",
        "ចូលគណនីដោយអ៊ីមែល ឬឈ្មោះអធីប្រវត្តិ ដើម្បីបន្ត។",
    ),
    "footer_note": (
        "RentEasy Web — web platform edition of the RentEasy mobile app.",
        "RentEasy Web — វេទិកាវែបនៃកម្មវិធីស្លាប់ RentEasy។",
    ),
    "audit": ("Audit Log", "កំណត់ត្តមនៃការកែសម្រួល"),
    "create_account": ("Create an account", "បង្កើតគណនី"),
    "featured_properties": ("Featured Properties", "ផ្ទះសំណង់ពេញនិយម"),
    "move_in_past": ("Move-in date cannot be in the past", "កាលបរិច្ឆេទផ្លូវការចូលស្នាក់មិនអាចជាពេលមុនឡើយទេ"),
    "password_too_short": (
        "Password must be at least 6 characters.",
        "ពាក្យសម្ងាត់ត្រូវមានយ៉ាងតិច ៦ តួអក្សរ។",
    ),
    "records_deleted": (
        "Selected records will be permanently deleted. This cannot be undone.",
        "កំណត់ត្តមដែលបានជ្រើសរើសនឹងត្រូវលុបចោលដោយរាលាទាំងស្មារ។ មិនអាចត្រឡប់វិញបានទេ។",
    ),
    # Superadmin console
    "amenities": ("Amenities", "មុខសម្យំ"),
    "area": ("Area (m²)", "ទំហំ (ម៉ែត្រការ៉េ)"),
    "booking_ref": ("Booking Ref", "លេខការជួល"),
    "confirm_delete_booking": (
        "Delete this record? This cannot be undone.",
        "លុបកំណត់ត្តមនេះ? មិនអាចត្រឡប់វិញបានទេ។",
    ),
    "deposit": ("Deposit", "ប្រាក់បង្កើត"),
    "image_url": ("Image URL", "អាសយដ្ឋានរូបភាព"),
    "issue_refund": ("Issue Refund", "ចោលសំណតវិញប្រាក់"),
    "mock_payment_note": (
        "Mock payments — no real money moves.",
        "ការបង្គន់ជាមួយការសាកល្បង — មិនមានលុយពិតចូលចិត្តទេ។",
    ),
    "no_payments_found": ("No payments found", "រកមិនឃើញការបង់ប្រាក់ទេ"),
    "no_properties_found": ("No properties found", "រកមិនឃើញផ្ទះសំណង់ទេ"),
    "no_refunds_yet": ("No refunds yet", "មិនទាន់មានការសងវិញប្រាក់ទេ"),
    "notes": ("Notes", "សម្គាល់"),
    "payment_ref": ("Payment Ref", "លេខការបង់ប្រាក់"),
    "property": ("Property", "អចលនទ្រព្យ"),
    "reason": ("Reason", "មូលហេតុ"),
    "refund_status_pending": ("Pending Refunds", "ការសងវិញប្រាក់កំពុងរង់ចាំ"),
    "rent": ("Rent", "ថ្លៃជួល"),
    "search_bookings": (
        "Search by reference, property or renter",
        "ស្វែងរកតាមលេខការជួល អចលនទ្រព្យ ឬអ្នកជួល",
    ),
    "search_payments": (
        "Search by reference, property or email",
        "ស្វែងរកតាមលេខ អចលនទ្រព្យ ឬអ៊ីមែល",
    ),
    "search_properties": (
        "Search by title, location or owner",
        "ស្វែងរកតាមចំណងជើង ទីតាំង ឬម្មានការ",
    ),
    "select_owner": ("Select an owner", "ជ្រើសរើសម្មានការ"),
    "select_property": ("Select a property", "ជ្រើសរើសអចលនទ្រព្យ"),
    "select_renter": ("Select a renter", "ជ្រើសរើសអ្នកជួល"),
    "stat_properties": ("Properties", "ផ្ទះសំណង់"),
    "status_available": ("Available", "ទំនេរ"),
    "status_rented": ("Rented", "បានជួល"),
    "title": ("Title", "ចំណងជើង"),
    "transaction_id": ("Transaction ID", "លេខប្រតិបត្តិប្រតិបត្តិការ"),
    "user": ("User", "អ្នកប្រើប្រាក់"),
    "view": ("View", "មើល"),
    "renters": ("Renters", "អ្នកជួល"),
    "favorites_saved": ("Saved to favorites", "បានរក្សាទុកក្នុងចូលចិត្ត"),
    "pending_approvals": ("Awaiting approval", "កំពុងរង់ចាំការអនុម័ត"),
    "reason_cancelled_by_renter": ("Cancelled by renter", "បានលុបដោយអ្នកជួល"),
    "reason_rejected_by_owner": ("Rejected by owner", "បានបដិសេធដោយម្មានការ"),
    "reason_other": ("Other", "ផ្សេងទៀត"),
    "auto": ("auto-selected from the property", "ជ្រើសរើសដោយស្វ័យពីអចលនទ្រព្យ"),
}

ROLE_KEYS = {
    "renter": "renter",
    "owner": "property_owner",
    "superadmin": "super_admin",
}

METHOD_KEYS = {
    "ABA Pay (Mock)": "method_aba",
    "Wing (Mock)": "method_wing",
    "Credit Card (Mock)": "method_card",
}

REFUND_KEYS = {
    "None": "status_none",
    "Pending": "status_pending",
    "Processed": "status_processed",
}

REFUND_REASON_KEYS = {
    "cancelled_by_renter": "reason_cancelled_by_renter",
    "rejected_by_owner": "reason_rejected_by_owner",
    "other": "reason_other",
}


class Translator:
    """Callable translation object bound to a language code."""

    __slots__ = ("language", "is_khmer")

    def __init__(self, language: str):
        self.language = language if language in SUPPORTED_LANGUAGE_CODES else DEFAULT_LANGUAGE
        self.is_khmer = self.language == "km"

    def __call__(self, key: str, /, **kwargs) -> str:
        pair = CATALOG.get(key)
        if pair is None:
            return key
        value = pair[1] if self.is_khmer else pair[0]
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return value
        return value

    # -- status helpers -------------------------------------------------
    def booking_status(self, raw: str) -> str:
        return {
            "Pending": self("status_pending"),
            "Approved": self("status_approved"),
            "Rejected": self("status_rejected"),
            "Cancelled": self("status_cancelled"),
        }.get(raw, raw)

    def payment_status(self, raw: str) -> str:
        return {"Success": self("status_success"), "Failed": self("status_failed")}.get(raw, raw)

    def refund_status(self, raw: str) -> str:
        return {
            "None": self("status_none"),
            "Pending": self("status_pending"),
            "Processed": self("status_processed"),
        }.get(raw, raw)

    def method_label(self, raw: str) -> str:
        return self(METHOD_KEYS.get(raw, "method_card"))

    def refund_option(self, raw: str) -> str:
        """Label for a refund filter dropdown entry (``all`` stays literal)."""
        if raw == "all":
            return self("all")
        return self(REFUND_KEYS.get(raw, "status_none"))

    def role_label(self, role: str | None) -> str:
        if not role:
            return self("unknown")
        return self(ROLE_KEYS.get(role, "unknown"))

    def role_short(self, role: str | None) -> str:
        if not role:
            return self("unknown")
        return self("owner") if role == "owner" else self(ROLE_KEYS.get(role, "unknown"))

    def status_pill(self, raw: str) -> tuple[str, str]:
        """Return (label, tailwind class token) for a booking status."""
        return {
            "Pending": (self.booking_status(raw), "pill-pending"),
            "Approved": (self.booking_status(raw), "pill-approved"),
            "Rejected": (self.booking_status(raw), "pill-rejected"),
            "Cancelled": (self.booking_status(raw), "pill-cancelled"),
        }.get(raw, (raw, "pill-neutral"))

    def payment_pill(self, payment) -> tuple[str, str]:
        if getattr(payment, "refund_status", "None") == "Processed":
            return (self("status_refunded"), "pill-refunded")
        if getattr(payment, "status", "") == "Success":
            return (self("status_success"), "pill-approved")
        return (self("status_failed"), "pill-rejected")


def get_translator(language: str) -> Translator:
    return Translator(language)


# Validate catalogue integrity at import time so a malformed entry never
# silently breaks a page render.
for _key, _pair in CATALOG.items():
    if len(_pair) != 2:  # pragma: no cover - developer guard
        raise ValueError(f"Malformed translation entry for key: {_key}")
del _key, _pair
