package dev.caseflow.evidence;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}/cases/{caseId}/policies")
public class PolicyPinController {
    private final JdbcTemplate db;private final Access access;private final Commands commands;private final PolicyPins pins;
    public PolicyPinController(JdbcTemplate db,Access access,Commands commands,PolicyPins pins){this.db=db;this.access=access;this.commands=commands;this.pins=pins;}
    public record VersionInput(@NotNull @PositiveOrZero Long expectedVersion) {}
    @GetMapping public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId) {
        access.caseVisible(tenantId,access.identity(jwt),caseId,false);return pins.list(tenantId,caseId);
    }
    @PostMapping("/refresh") public Map<String,Object> refresh(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"policies:refresh:"+caseId,key,input,()->{access.caseVisible(tenantId,actor,caseId,true);access.role(tenantId,actor,"REQUESTER",false);},()->{
            var row=db.queryForMap("SELECT owner_id,state,version FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE",tenantId,caseId);
            if(!actor.equals(row.get("owner_id")))throw Problem.forbidden();
            if(!"DRAFT".equals(row.get("state")))throw new Problem(409,"Policy versions are fixed after a purchase starts");
            if(input.expectedVersion()!=((Number)row.get("version")).longValue())throw Problem.conflict();
            pins.replace(tenantId,caseId);
            db.update("UPDATE core.cases SET version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",tenantId,caseId);
            var result=pins.list(tenantId,caseId);commands.audit(tenantId,caseId,actor,"POLICIES_REFRESHED",result);return result;
        });
    }
    @GetMapping("/search") public Map<String,Object> search(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestParam String query) {
        access.caseVisible(tenantId,access.identity(jwt),caseId,false);
        Problem.require(!query.isBlank()&&query.length()<=500,"Search must contain 1 to 500 characters");
        return Map.of("method","postgres-full-text-v1","items",db.queryForList("""
            SELECT ch.id,ch.source_id AS "sourceId",s.name,ch.page,ch.section,ch.start_offset AS start,
                   ch.end_offset AS end,ch.text,ch.sha256,ts_rank_cd(ch.search,websearch_to_tsquery('english',?)) AS score
            FROM worker.source_chunks ch JOIN core.case_policy_pins p ON p.tenant_id=ch.tenant_id AND p.source_id=ch.source_id
            JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id
            JOIN core.cases c ON c.tenant_id=p.tenant_id AND c.id=p.case_id
            WHERE p.tenant_id=? AND p.case_id=? AND (s.state='PUBLISHED' OR (c.state<>'DRAFT' AND s.state='DEACTIVATED'))
              AND ch.search @@ websearch_to_tsquery('english',?)
            ORDER BY score DESC,ch.source_id,ch.ordinal LIMIT 5
            """,query,tenantId,caseId,query));
    }
}
