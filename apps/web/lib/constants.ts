export const COURT_OPTIONS = [
  { value: "supremecourt", label: "Supreme Court of India" },
  { value: "delhi", label: "Delhi High Court" },
  { value: "bombay", label: "Bombay High Court" },
  { value: "chennai", label: "Madras High Court" },
  { value: "kolkata", label: "Kolkata High Court" },
  { value: "karnataka", label: "Karnataka High Court" },
  { value: "allahabad", label: "Allahabad High Court" },
  { value: "punjab", label: "Punjab & Haryana High Court" },
  { value: "kerala", label: "Kerala High Court" },
  { value: "telangana", label: "Telangana High Court" },
  { value: "andhra", label: "Andhra Pradesh High Court" },
  { value: "gujarat", label: "Gujarat High Court" },
  { value: "madhyapradesh", label: "Madhya Pradesh High Court" },
  { value: "patna", label: "Patna High Court" },
  { value: "rajasthan", label: "Rajasthan High Court" },
  { value: "orissa", label: "Orissa High Court" },
  { value: "jharkhand", label: "Jharkhand High Court" },
  { value: "chattisgarh", label: "Chhattisgarh High Court" },
  { value: "uttaranchal", label: "Uttarakhand High Court" },
  { value: "himachal_pradesh", label: "Himachal Pradesh High Court" },
  { value: "jammu", label: "Jammu & Kashmir High Court" },
  { value: "gauhati", label: "Gauhati High Court" },
  { value: "meghalaya", label: "Meghalaya High Court" },
  { value: "manipur", label: "Manipur High Court" },
  { value: "sikkim", label: "Sikkim High Court" },
  { value: "tripura", label: "Tripura High Court" },
] as const

export const POLLING_INTERVAL_OPTIONS = [
  { value: 120, label: "Every 2 hours" },
  { value: 240, label: "Every 4 hours" },
  { value: 360, label: "Every 6 hours" },
  { value: 720, label: "Every 12 hours" },
  { value: 1440, label: "Every 24 hours" },
] as const

export const WATCH_TYPE_STYLES = {
  entity: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  topic: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  act: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
} as const

export const NOTIFICATION_STATUS_STYLES = {
  sent: "bg-green-500/20 text-green-400 border-green-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
  retrying: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  pending: "bg-muted text-muted-foreground",
} as const

export const NOTIFICATION_CHANNEL_STYLES = {
  email: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  slack: "bg-purple-500/20 text-purple-400 border-purple-500/30",
} as const
