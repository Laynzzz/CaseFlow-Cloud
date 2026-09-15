# Foundation versions

Checked 2026-09-11. These are the selected versions, not assumptions based on
globally installed tools. Remaining services are deliberately not versioned
until their integration is introduced.

| Component | Selected version | Evidence |
| --- | --- | --- |
| Java | 21; local Temurin 21.0.12.1 | Java toolchain in Gradle; local `java -version` |
| Spring Boot | 4.1.1 | Spring Initializr metadata and official system requirements |
| Gradle | 9.7.1 | Wrapper properties, published SHA-256, executed build |
| PostgreSQL | 18.6-bookworm | Docker Official Image registry manifest; digest in Compose |
| Node | local 22.20.0; supported project range 22.12+ within 22 | npm engines and local version |
| React / React DOM | 19.3.0 | npm registry and package-lock.json |
| Vite / React plugin | 8.3.0 / 6.1.1 | npm engine/peer requirements and build |
| TypeScript | 5.9.3 | API generator requires TypeScript 5 |
| openapi-typescript / openapi-fetch | 7.13.0 / 0.17.0 | npm peer metadata, generation, typecheck |
| Flyway / PostgreSQL JDBC driver | Spring Boot managed | Exact resolved versions in gradle.lockfile |
| Keycloak server / browser adapter | 26.7.3 / 26.2.4 | Server digest in Compose; adapter package lock; real PKCE integration |
| TanStack Query / React Router DOM | 5.102.8 / 7.18.3 | npm package lock and browser journey |
| React Hook Form / Zod | 7.88.0 / 4.6.5 | npm package lock and draft UI |
| Prettier | 3.9.6 | Registry version checked September 14; format check executed |
| Kafka / SeaweedFS | 4.2.1 / 4.47 | Verified registry Linux amd64 digests in Compose; real pipeline |
| AWS Java SDK | 2.54.18 | Maven metadata, Gradle lock and real local S3 operations |
| Python | 3.12.10 local | Isolated worker venv and pytest |
| docxtpl / python-docx | 0.20.2 / 1.2.0 | PyPI, worker requirements.lock and rendered DOCX |
| psycopg / confluent-kafka | 3.3.5 / 2.15.1 | Locked wheels; PostgreSQL and Kafka checks |
| boto3 / FastAPI / uvicorn | 1.43.94 / 0.141.1 / 0.53.0 | Exact requirements.lock; running worker and S3 checks |

The first npm attempt with TypeScript 6.0.3 failed peer dependency resolution
because openapi-typescript declares `^5.x`. Adjusted to 5.9.3 without bypassing
peer checks. The global tool installation is unchanged.

Official references:

- [Spring Boot system requirements](https://docs.spring.io/spring-boot/system-requirements.html)
- [Spring Boot Flyway initialization](https://docs.spring.io/spring-boot/how-to/data-initialization.html)
- [Gradle Wrapper and checksum verification](https://docs.gradle.org/current/userguide/gradle_wrapper.html)
- [Vite requirements](https://vite.dev/guide/)
- [PostgreSQL Official Image](https://hub.docker.com/_/postgres)
- [OpenAPI TypeScript documentation](https://openapi-ts.dev/introduction)
