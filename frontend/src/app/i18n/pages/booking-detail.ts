import type { PageCatalog } from '../types';

export const bookingDetail: PageCatalog = {
  paid: ['Paid', 'បានទូទាត់'],
  unpaid: ['Unpaid', 'មិនទាន់ទូទាត់'],
  propertyDetails: ['Property details', 'ព័ត៌មានអចលនទ្រព្យ'],
  propertyType: ['Property type', 'ប្រភេទអចលនទ្រព្យ'],
  bedrooms: ['Bedrooms', 'បន្ទប់គេង'],
  bathrooms: ['Bathrooms', 'បន្ទប់ទឹក'],
  description: ['Description', 'ការពិពណ៌នា'],
  viewListing: ['View listing', 'មើលការចុះផ្សាយ'],
  previousPhoto: ['Previous photo', 'រូបថតមុន'],
  nextPhoto: ['Next photo', 'រូបថតបន្ទាប់'],
  refundMessagePrompt: ['Add a message for the admin about this refund request (required):', 'បន្ថែមសារសម្រាប់អ្នកគ្រប់គ្រងអំពីការស្នើសុំសងប្រាក់វិញ (ត្រូវតែបញ្ចូល):'],
  refundMessageRequired: ['Please add a message for the admin before sending the request.', 'សូមបញ្ចូលសារសម្រាប់អ្នកគ្រប់គ្រងមុនពេលផ្ញើសំណើ។'],
  paymentMethod: ['Payment method', 'វិធីសាស្ត្រទូទាត់'],
  openRefundChat: ['Chat admin', 'ជជែកជាមួយអ្នកគ្រប់គ្រង'],
  search: ['Search...', 'ស្វែងរក...'],
  paymentWindowRemaining: ['Pay within', 'ត្រូវបង់ក្នុងរយៈពេល'],
  paymentDeadline: ['Payment deadline', 'កាលកំណត់ទូទាត់'],
  payWithin: ['Time left to pay', 'ពេលវេលានៅសល់ដើម្បីបង់ប្រាក់'],
  lessThanHour: ['Less than 1 hour', 'តិចជាង ១ ម៉ោង'],
  expiredInfo: ['This booking request expired because payment was not completed within 5 hours.', 'សំណើកក់នេះបានផុតកំណត់ ព្រោះមិនបានបញ្ចប់ការទូទាត់ប្រាក់ក្នុងរយៈពេល ៥ ម៉ោង។'],
};
