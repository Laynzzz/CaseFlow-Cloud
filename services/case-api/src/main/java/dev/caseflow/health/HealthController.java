package dev.caseflow.health;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    private static final Logger log = LoggerFactory.getLogger(HealthController.class);
    private final JdbcTemplate jdbc;

    public HealthController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/api/v1/health")
    public ResponseEntity<?> health() {
        try {
            String version = jdbc.queryForObject(
                    "SELECT value FROM core.system_metadata WHERE key = 'schema_version'", String.class);
            if (!"1".equals(version)) {
                return unavailable();
            }
            return ResponseEntity.ok(new HealthResponse("UP", "case-api", "UP", version));
        } catch (DataAccessException ex) {
            // Public health responses must not disclose database URLs or driver messages.
            log.warn("Database readiness check failed ({})", ex.getClass().getSimpleName());
            return unavailable();
        }
    }

    private ResponseEntity<ProblemDetail> unavailable() {
        var problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.SERVICE_UNAVAILABLE, "The database is not ready. Try again shortly.");
        problem.setTitle("Service unavailable");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(problem);
    }

    public record HealthResponse(String status, String service, String database, String schemaVersion) {}
}
