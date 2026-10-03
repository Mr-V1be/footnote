import type { ApiClient } from "@/shared/api/client";
import { unwrap, unwrapEmpty } from "@/shared/api/errors";
import type {
  ApiKey,
  ApiScope,
  Delivery,
  DeliveryPage,
  DeliveryStatus,
  IssuedKey,
  Webhook,
  WebhookInput,
  WebhookWithSecret,
} from "@/shared/api/types";

/** While a delivery is on its way its state is refreshed this often. */
export const DELIVERY_POLL_MS = 4000;
const IN_FLIGHT: readonly DeliveryStatus[] = ["pending", "retrying"];

export function isInFlight(status: DeliveryStatus): boolean {
  return IN_FLIGHT.includes(status);
}

export const integrationKeys = {
  all: (organization: string) => ["organizations", organization, "integrations"] as const,
  apiKeys: (organization: string) => [...integrationKeys.all(organization), "api-keys"] as const,
  webhooks: (organization: string) => [...integrationKeys.all(organization), "webhooks"] as const,
  deliveries: (organization: string, endpointId: string) =>
    [...integrationKeys.webhooks(organization), endpointId, "deliveries"] as const,
};

const org = (organization: string) => ({ params: { path: { organization } } });
const endpoint = (organization: string, endpointId: string) => ({
  params: { path: { organization, endpoint_id: endpointId } },
});

export async function fetchApiKeys(api: ApiClient, organization: string): Promise<ApiKey[]> {
  return unwrap(await api.GET("/api/v1/organizations/{organization}/api-keys", org(organization)));
}

export async function createApiKey(
  api: ApiClient,
  organization: string,
  name: string,
  scopes: ApiScope[],
): Promise<IssuedKey> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/api-keys", {
      ...org(organization),
      body: { name, scopes },
    }),
  );
}

export async function revokeApiKey(
  api: ApiClient,
  organization: string,
  keyId: string,
): Promise<ApiKey> {
  return unwrap(
    await api.DELETE("/api/v1/organizations/{organization}/api-keys/{key_id}", {
      params: { path: { organization, key_id: keyId } },
    }),
  );
}

export async function fetchWebhooks(api: ApiClient, organization: string): Promise<Webhook[]> {
  return unwrap(await api.GET("/api/v1/organizations/{organization}/webhooks", org(organization)));
}

export async function createWebhook(
  api: ApiClient,
  organization: string,
  input: WebhookInput,
): Promise<WebhookWithSecret> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/webhooks", {
      ...org(organization),
      body: input,
    }),
  );
}

export async function updateWebhook(
  api: ApiClient,
  organization: string,
  endpointId: string,
  input: WebhookInput,
): Promise<Webhook> {
  return unwrap(
    await api.PUT("/api/v1/organizations/{organization}/webhooks/{endpoint_id}", {
      ...endpoint(organization, endpointId),
      body: input,
    }),
  );
}

export async function deleteWebhook(
  api: ApiClient,
  organization: string,
  endpointId: string,
): Promise<void> {
  unwrapEmpty(
    await api.DELETE(
      "/api/v1/organizations/{organization}/webhooks/{endpoint_id}",
      endpoint(organization, endpointId),
    ),
  );
}

export async function rotateWebhookSecret(
  api: ApiClient,
  organization: string,
  endpointId: string,
): Promise<WebhookWithSecret> {
  return unwrap(
    await api.POST(
      "/api/v1/organizations/{organization}/webhooks/{endpoint_id}/secret",
      endpoint(organization, endpointId),
    ),
  );
}

export const DELIVERY_PAGE_SIZE = 20;

export async function fetchDeliveries(
  api: ApiClient,
  organization: string,
  endpointId: string,
  cursor: string | null,
): Promise<DeliveryPage> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/webhooks/{endpoint_id}/deliveries", {
      params: {
        path: { organization, endpoint_id: endpointId },
        query: { limit: DELIVERY_PAGE_SIZE, ...(cursor ? { cursor } : {}) },
      },
    }),
  );
}

export async function pingWebhook(
  api: ApiClient,
  organization: string,
  endpointId: string,
): Promise<Delivery> {
  return unwrap(
    await api.POST(
      "/api/v1/organizations/{organization}/webhooks/{endpoint_id}/ping",
      endpoint(organization, endpointId),
    ),
  );
}

export async function retryDelivery(
  api: ApiClient,
  organization: string,
  endpointId: string,
  deliveryId: string,
): Promise<Delivery> {
  return unwrap(
    await api.POST(
      "/api/v1/organizations/{organization}/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry",
      {
        params: { path: { organization, endpoint_id: endpointId, delivery_id: deliveryId } },
      },
    ),
  );
}
