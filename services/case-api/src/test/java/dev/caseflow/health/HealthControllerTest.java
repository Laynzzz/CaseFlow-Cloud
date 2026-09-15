package dev.caseflow.health;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.ProblemDetail;
import org.springframework.jdbc.core.JdbcTemplate;

class HealthControllerTest {
    private final JdbcTemplate jdbc = mock(JdbcTemplate.class);
    private final HealthController controller = new HealthController(jdbc);

    @Test
    void reportsReadyOnlyAfterReadingTheMigratedSchema() {
        when(jdbc.queryForObject(anyString(), eq(String.class))).thenReturn("1");
        var response = controller.health();
        assertEquals(200, response.getStatusCode().value());
        assertEquals(new HealthController.HealthResponse("UP", "case-api", "UP", "1"), response.getBody());
    }

    @Test
    void databaseFailureReturnsRetryableStatusWithoutLeakingDriverDetails() {
        when(jdbc.queryForObject(anyString(), eq(String.class)))
                .thenThrow(new DataAccessResourceFailureException("private database connection details"));
        var response = controller.health();
        assertEquals(503, response.getStatusCode().value());
        var problem = assertInstanceOf(ProblemDetail.class, response.getBody());
        assertFalse(problem.getDetail().contains("private"));
    }

    @Test
    void unexpectedSchemaCannotPassReadiness() {
        when(jdbc.queryForObject(anyString(), eq(String.class))).thenReturn("unexpected");
        assertEquals(503, controller.health().getStatusCode().value());
    }
}
