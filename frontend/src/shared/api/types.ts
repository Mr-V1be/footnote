import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeOut"];
export type Membership = Schemas["MembershipOut"];
export type Organization = Schemas["OrganizationOut"];
export type Workspace = Schemas["WorkspaceOut"];
export type Catalog = Schemas["CatalogOut"];
export type DocumentKind = Schemas["DocumentKindOut"];
export type DocumentListItem = Schemas["DocumentListItemOut"];
export type DocumentPage = Schemas["DocumentPageOut"];
export type DocumentDetails = Schemas["DocumentOut"];
export type DocumentVersion = Schemas["VersionOut"];
export type DocumentStructure = Schemas["StructureOut"];
export type Block = Schemas["BlockOut"];
export type Requisite = Schemas["RequisiteOut"];
export type OutlineEntry = Schemas["OutlineEntryOut"];
export type PageSetup = Schemas["PageSetupOut"];
export type ParseStatus = Schemas["ParseStatus"];
export type ParseFailureCode = Schemas["ParseFailureCode"];
export type ExtractionMethod = Schemas["ExtractionMethod"];
export type RequisiteKind = Schemas["RequisiteKind"];
export type Permission = Schemas["Permission"];
export type UploadResult = Schemas["UploadOut"];
export type Problem = Schemas["Problem"];
export type CheckReport = Schemas["CheckReportOut"];
export type CheckRun = Schemas["RunOut"];
export type CheckResult = Schemas["ResultOut"];
export type CheckDefinition = Schemas["CheckOut"];
export type CheckCatalog = Schemas["CheckCatalogOut"];
export type Finding = Schemas["FindingOut"];
export type FindingLocation = Schemas["LocationOut"];
export type Severity = Schemas["Severity"];
export type ReviewStatus = Schemas["ReviewStatus"];
export type RunStatus = Schemas["RunStatus"];
export type RunSummary = Schemas["RunSummaryOut"];
export type Quality = Schemas["QualityOut"];
export type QualityMetrics = Schemas["MetricsOut"];
export type DocumentTiming = Schemas["DocumentTimingOut"];
export type RunFailureCode = Schemas["RunFailureCode"];
export type VersionOrigin = Schemas["VersionOrigin"];

// Administration of an organization.
export type AdministrationCatalog = Schemas["AdministrationCatalogOut"];
export type Role = Schemas["RoleOut"];
export type Member = Schemas["MemberOut"];
export type Invite = Schemas["InviteIn"];
export type WorkspaceMember = Schemas["WorkspaceMemberOut"];
export type WorkspaceInput = Schemas["WorkspaceIn"];
export type WorkspacePatch = Schemas["WorkspacePatchIn"];
export type AuditPage = Schemas["AuditPageOut"];
export type AuditEvent = Schemas["AuditEventOut"];
export type AuditAction = Schemas["AuditAction"];
export type ActorKind = Schemas["ActorKind"];

// Integrations.
export type ApiKey = Schemas["ApiKeyOut"];
export type ApiScope = Schemas["ApiScope"];
export type IssuedKey = Schemas["IssuedKeyOut"];
export type Webhook = Schemas["WebhookOut"];
export type WebhookInput = Schemas["WebhookIn"];
export type WebhookWithSecret = Schemas["WebhookWithSecretOut"];
export type WebhookEvent = Schemas["WebhookEvent"];
export type Delivery = Schemas["DeliveryOut"];
export type DeliveryPage = Schemas["DeliveryPageOut"];
export type DeliveryStatus = Schemas["DeliveryStatus"];

// Plans, usage and payments.
export type Billing = Schemas["BillingOut"];
export type Plan = Schemas["PlanOut"];
export type Usage = Schemas["UsageOut"];
export type UsageMetric = Schemas["UsageMetric"];
export type Invoice = Schemas["InvoiceOut"];
export type LedgerEntry = Schemas["LedgerEntryOut"];
export type LedgerPage = Schemas["LedgerPageOut"];
export type PlanChangeResult = Schemas["PlanChangeOut"];
export type TestPayment = Schemas["TestPaymentOut"];

// Automatic correction of formatting.
export type AutofixPreview = Schemas["AutofixPreviewOut"];
export type AutofixResult = Schemas["AutofixOut"];
export type VersionChange = Schemas["ChangeOut"];
export type SkipReason = Schemas["SkipReason"];

// Questions to the corpus.
export type AskStatus = Schemas["AskStatusOut"];
export type ConversationSummary = Schemas["ConversationSummaryOut"];
export type Conversation = Schemas["ConversationOut"];
export type ConversationTurn = Schemas["TurnOut"];
export type Citation = Schemas["CitationOut"];

// The platform console.
export type OrganizationRow = Schemas["OrganizationRowOut"];
export type SystemStatus = Schemas["SystemOut"];
export type PlansOffer = Schemas["PlansOut"];
export type ModelTrial = Schemas["ModelTrialOut"];
