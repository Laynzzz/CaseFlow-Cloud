FROM node:22.23.2-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS web
WORKDIR /source/apps/web
COPY apps/web/package*.json ./
RUN npm ci --ignore-scripts
COPY apps/web/ ./
ARG VITE_OIDC_URL=http://127.0.0.1:18180
ENV VITE_OIDC_URL=${VITE_OIDC_URL}
RUN npm run build

FROM eclipse-temurin:21.0.12_8-jdk-noble@sha256:5dd9dbc6f6eccb82184b340da9488b70b68d2af81474cf8f280f8ce6b2933282 AS build
WORKDIR /source/services/case-api
COPY services/case-api/ ./
COPY db/migrations/ /source/db/migrations/
COPY --from=web /source/apps/web/dist/ ./src/main/resources/static/
RUN --mount=type=cache,target=/root/.gradle sed -i 's/\r$//' gradlew && chmod +x gradlew && ./gradlew --no-daemon bootJar
COPY infrastructure/release/HealthProbe.java /tmp/HealthProbe.java
RUN javac -d /probe /tmp/HealthProbe.java

FROM eclipse-temurin:21.0.12_8-jre-noble@sha256:86883d2dc1d0e57d4fb2c539f5fd3a2155749c0bdcdccb9cb452828bdc8b0caf
ARG REVISION=unknown
LABEL org.opencontainers.image.title="CaseFlow API and web" org.opencontainers.image.revision=${REVISION}
WORKDIR /app
COPY --from=build /source/services/case-api/build/libs/*-SNAPSHOT.jar /app/case-api.jar
COPY --from=build /probe/ /app/probe/
USER 10001:10001
ENV API_ADDRESS=0.0.0.0 API_PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=5s --start-period=60s --retries=12 CMD ["java", "-cp", "/app/probe", "HealthProbe"]
ENTRYPOINT ["java", "-jar", "/app/case-api.jar"]
