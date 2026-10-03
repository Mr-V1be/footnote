# syntax=docker/dockerfile:1.7
# Keycloak of the production stack, built ahead of time: build options are fixed here, so
# `start --optimized` skips the augmentation every start would otherwise repeat, and the
# realm and the login theme travel inside the image. Build from the repository root:
#   docker build -f infra/keycloak/Dockerfile -t snoska-keycloak .

ARG KEYCLOAK_IMAGE=keycloak/keycloak:26.8.0

FROM ${KEYCLOAK_IMAGE} AS build
# Features the realm does not use are left out: device and backchannel (CIBA) flows, pushed
# authorization requests, Kerberos and impersonation.
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=false \
    KC_FEATURES_DISABLED=ciba,device-flow,par,kerberos,impersonation
RUN /opt/keycloak/bin/kc.sh build

FROM ${KEYCLOAK_IMAGE}
COPY --from=build /opt/keycloak/ /opt/keycloak/
COPY infra/keycloak/realm-snoska.json /opt/keycloak/data/import/realm-snoska.json
COPY infra/keycloak/themes/snoska /opt/keycloak/themes/snoska
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized", "--import-realm"]
