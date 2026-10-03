// Load test of the API with k6 (run in its Docker image, see `make load`).
//
// Four flows of an integration at once, each at a steady arrival rate
// (LIST_RATE, REPORT_RATE, UPLOAD_RATE, CHECK_RATE override the defaults):
//   list    the documents of a workspace                 GET, 30 per second
//   report  the latest check of a document, with findings GET, 10 per second
//   upload  a DOCX, read and checked by the worker        POST, 1 per second
//   check   a check requested, followed by its server-sent events to the end
//                                                         POST + SSE, 1 per 2 seconds
//
// Setup signs the stand's owner in through the demo client (direct grant),
// issues an API key for the run and revokes it in teardown. Model answers of
// documents checked before come from the cache: the run measures the
// product, not the model provider.
import { check, fail } from "k6";
import http from "k6/http";
import { Counter, Trend } from "k6/metrics";

const API = __ENV.API_URL || "http://127.0.0.1:46301/api";
const KEYCLOAK = __ENV.KEYCLOAK_URL || "http://localhost:46320";
const REALM = __ENV.KEYCLOAK_REALM || "snoska";
const ORG = __ENV.ORG || "polyarnaya-zvezda";
const DURATION = __ENV.DURATION || "60s";
const CHECKED = __ENV.CHECKED_TITLE || "Согласие покупателя на обработку ПДн";
const UPLOAD = open("/repo/backend/demo/reference/soglasie-zarya.docx", "b");

const checkSeconds = new Trend("check_seconds", true);
const checksSettled = new Counter("checks_settled");

export const options = {
  scenarios: {
    list: rate("list", Number(__ENV.LIST_RATE || 30), 1, 20, 200),
    report: rate("report", Number(__ENV.REPORT_RATE || 10), 1, 10, 100),
    upload: rate("upload", Number(__ENV.UPLOAD_RATE || 1), 1, 4, 40),
    check: rate("requestCheck", Number(__ENV.CHECK_RATE || 1), 2, 4, 60),
  },
  thresholds: {
    "http_req_failed{scenario:list}": ["rate<0.01"],
    "http_req_failed{scenario:report}": ["rate<0.01"],
    "http_req_failed{scenario:upload}": ["rate<0.01"],
    "http_req_duration{scenario:list}": ["p(95)<500"],
    "http_req_duration{scenario:report}": ["p(95)<800"],
    "http_req_duration{name:upload}": ["p(95)<1500"],
    "http_req_duration{name:request check}": ["p(95)<800"],
    check_seconds: ["p(95)<30000"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "max"],
};

function rate(exec, perUnit, unitSeconds, preAllocatedVUs, maxVUs) {
  return {
    executor: "constant-arrival-rate",
    exec,
    rate: perUnit,
    timeUnit: `${unitSeconds}s`,
    duration: DURATION,
    preAllocatedVUs,
    maxVUs,
  };
}

function ownerToken() {
  const response = http.post(
    `${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/token`,
    {
      grant_type: "password",
      client_id: __ENV.DEMO_CLIENT_ID || "snoska-demo",
      client_secret: __ENV.DEMO_CLIENT_SECRET,
      username: __ENV.OWNER_EMAIL || "kovaleva@polyarnaya-zvezda.example",
      password: __ENV.OWNER_PASSWORD,
      scope: "openid organization",
    },
    { tags: { name: "setup" } },
  );
  if (response.status !== 200) fail(`sign-in failed: ${response.status}`);
  return response.json("access_token");
}

function bearer(token) {
  return { headers: { Authorization: `Bearer ${token}` } };
}

export function setup() {
  const owner = ownerToken();
  const issued = http.post(
    `${API}/v1/organizations/${ORG}/api-keys`,
    JSON.stringify({
      name: "Нагрузочный тест",
      scopes: ["documents:read", "documents:write", "checks:run"],
    }),
    { headers: { ...bearer(owner).headers, "Content-Type": "application/json" } },
  );
  if (issued.status !== 201) fail(`API key not issued: ${issued.status}`);
  const key = issued.json();
  const listed = http.get(`${API}/v1/organizations/${ORG}/workspaces/main/documents`, bearer(owner));
  const document = listed.json("items").find((item) => item.title === CHECKED);
  if (!document) fail(`no document titled ${CHECKED}`);
  return { token: key.token, keyId: key.key.id, document: document.id };
}

export function teardown(data) {
  http.del(`${API}/v1/organizations/${ORG}/api-keys/${data.keyId}`, null, bearer(ownerToken()));
}

export function list(data) {
  const response = http.get(`${API}/v1/organizations/${ORG}/workspaces/main/documents`, {
    ...bearer(data.token),
    tags: { name: "list documents" },
  });
  check(response, { "list 200": (r) => r.status === 200 });
}

export function report(data) {
  const response = http.get(
    `${API}/v1/organizations/${ORG}/documents/${data.document}/versions/1/checks/latest`,
    { ...bearer(data.token), tags: { name: "check report" } },
  );
  check(response, { "report 200": (r) => r.status === 200 });
}

export function upload(data) {
  const response = http.post(
    `${API}/v1/organizations/${ORG}/workspaces/main/documents`,
    {
      file: http.file(UPLOAD, "soglasie.docx", "application/octet-stream"),
      kind: "pd_consent",
      title: `Нагрузочный тест ${__VU}-${__ITER}`,
    },
    { ...bearer(data.token), tags: { name: "upload" } },
  );
  check(response, { "upload 201": (r) => r.status === 201 });
}

export function requestCheck(data) {
  const started = Date.now();
  const requested = http.post(
    `${API}/v1/organizations/${ORG}/documents/${data.document}/versions/1/checks`,
    null,
    { ...bearer(data.token), tags: { name: "request check" } },
  );
  if (!check(requested, { "check accepted": (r) => r.status >= 200 && r.status < 300 })) return;
  // The stream ends with an `end` event once the run is settled.
  const events = http.get(
    `${API}/v1/organizations/${ORG}/check-runs/${requested.json("id")}/events`,
    { ...bearer(data.token), timeout: "180s", tags: { name: "run events" } },
  );
  if (check(events, { "run settled": (r) => r.status === 200 && r.body.includes("event: end") })) {
    checkSeconds.add(Date.now() - started);
    checksSettled.add(1);
  }
}

