import type { PageCatalog } from '../types';

export const consoleSettings: PageCatalog = {
  platformSettings: ['Platform Settings', 'ការកំណត់វេទិកា'],
  platformWideSwitchesControlledBySystemAdmins: ['Platform-wide switches controlled by system admins', 'ការកំណត់ទូទាំងវេទិកា គ្រប់គ្រងដោយអ្នកគ្រប់គ្រងប្រព័ន្ធ'],
  autoApprovePropertyOwners: ['Auto-approve property owners', 'អនុម័តម្ចាស់អចលនទ្រព្យដោយស្វ័យប្រវត្តិ'],
  whenEnabledNewOwnerRegistrationsAreActivated: ['When enabled, new owner registrations are activated immediately. When disabled, an admin must approve each owner request before they can sign in.', 'នៅពេលបើក ការចុះឈ្មោះម្ចាស់ថ្មីត្រូវបានអនុម័តភ្លាមៗ។ នៅពេលបិទ អ្នកគ្រប់គ្រងត្រូវអនុម័តសំណើម្ចាស់នីមួយៗ មុនពេលពួកគេអាចចូលគណនីបាន។'],
  ownerRegistrationsAreApprovedAutomatically: ['Owner registrations are approved automatically.', 'ការចុះឈ្មោះម្ចាស់ត្រូវបានអនុម័តដោយស្វ័យប្រវត្តិ។'],
  ownerRegistrationsRequireAdminApproval: ['Owner registrations require admin approval.', 'ការចុះឈ្មោះម្ចាស់ត្រូវការការអនុម័តពីអ្នកគ្រប់គ្រង។'],
  failedToLoadSettings: ['Failed to load settings.', 'មិនអាចផ្ទុកការកំណត់បានទេ។'],
  failedToSaveSettings: ['Failed to save settings.', 'មិនអាចរក្សាទុកការកំណត់បានទេ។'],
};
