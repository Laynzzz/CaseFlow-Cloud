package dev.caseflow.identity;

import dev.caseflow.common.Problem;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

@Service
public class Access {
    private final JdbcTemplate db;
    public Access(JdbcTemplate db) { this.db = db; }
    public UUID identity(Jwt token) {
        String issuer = token.getIssuer().toString();
        String subject = token.getSubject();
        String name = token.getClaimAsString("preferred_username");
        if (name == null || name.isBlank()) name = "Member";
        return db.queryForObject("""
                INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (?,?,?,?)
                ON CONFLICT (issuer,subject) DO UPDATE SET display_name=EXCLUDED.display_name RETURNING id
                """, UUID.class, UUID.randomUUID(), issuer, subject, name);
    }
    public Set<String> member(UUID tenant, UUID actor, boolean lock) {
        var rows = db.query("SELECT roles,active FROM core.memberships WHERE tenant_id=? AND user_id=?" + (lock ? " FOR SHARE" : ""),
                (rs, n) -> rs.getBoolean("active")
                        ? new HashSet<>(Arrays.asList((String[]) rs.getArray("roles").getArray())) : Set.<String>of(), tenant, actor);
        if (rows.isEmpty() || rows.getFirst().isEmpty()) throw Problem.missing();
        return rows.getFirst();
    }
    public void role(UUID tenant, UUID actor, String role, boolean lock) {
        if (!member(tenant, actor, lock).contains(role)) throw Problem.forbidden();
    }
    public void caseVisible(UUID tenant, UUID actor, UUID caseId, boolean lockMembership) {
        var roles = member(tenant, actor, lockMembership);
        Boolean visible = db.queryForObject("""
                SELECT EXISTS(SELECT 1 FROM core.cases c WHERE c.tenant_id=? AND c.id=?
                  AND (? OR c.owner_id=? OR EXISTS(SELECT 1 FROM core.assignments a
                    WHERE a.tenant_id=c.tenant_id AND a.case_id=c.id AND a.user_id=?)))
                """, Boolean.class, tenant, caseId, roles.contains("ADMIN") || roles.contains("AUDITOR"), actor, actor);
        if (!Boolean.TRUE.equals(visible)) throw Problem.missing();
    }
}
