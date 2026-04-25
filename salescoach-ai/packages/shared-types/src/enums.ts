export enum UserRole {
  ADMIN = 'admin',
  ROP = 'rop',
  MANAGER = 'manager',
}

export enum CallDirection {
  INBOUND = 'inbound',
  OUTBOUND = 'outbound',
}

export enum CallLanguage {
  UZ = 'uz',
  RU = 'ru',
  MIXED = 'mixed',
}

export enum CallStatus {
  QUEUED = 'queued',
  TRANSCRIBING = 'transcribing',
  TRANSCRIBED = 'transcribed',
  SCORING = 'scoring',
  DONE = 'done',
  FAILED = 'failed',
}

export enum Speaker {
  MANAGER = 'manager',
  CUSTOMER = 'customer',
  UNKNOWN = 'unknown',
}

export enum SubscriptionPlan {
  FREE = 'free',
  STARTER = 'starter',
  PRO = 'pro',
  ENTERPRISE = 'enterprise',
}
