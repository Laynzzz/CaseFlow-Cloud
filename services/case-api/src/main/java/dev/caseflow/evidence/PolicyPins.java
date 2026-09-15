package dev.caseflow.evidence;

import dev.caseflow.common.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class PolicyPins {
    private final JdbcTemplate db;
    public PolicyPins(JdbcTemplate db) {this.db=db;}
    // Caller holds the case lock. Shared source locks serialize deactivation with pinning.
    public void replace(UUID tenant,UUID caseId) {
        var sources=db.queryForList("SELECT id,version FROM core.sources WHERE tenant_id=? AND kind='POLICY' AND state='PUBLISHED' ORDER BY id FOR SHARE",tenant);
        Problem.require(sources.size()<=100,"At most 100 published policy versions can be pinned; deactivate obsolete versions first");
        db.update("DELETE FROM core.case_policy_pins WHERE tenant_id=? AND case_id=?",tenant,caseId);
        for(var source:sources)db.update("INSERT INTO core.case_policy_pins(tenant_id,case_id,source_id,source_version) VALUES (?,?,?,?)",tenant,caseId,source.get("id"),source.get("version"));
        db.update("UPDATE core.cases SET policies_initialized=true WHERE tenant_id=? AND id=?",tenant,caseId);
    }
    public void beforeStart(UUID tenant,UUID caseId) {
        if(!Boolean.TRUE.equals(db.queryForObject("SELECT policies_initialized FROM core.cases WHERE tenant_id=? AND id=?",Boolean.class,tenant,caseId)))replace(tenant,caseId);
        var sources=db.queryForList("SELECT s.state FROM core.case_policy_pins p JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id WHERE p.tenant_id=? AND p.case_id=? ORDER BY s.id FOR SHARE OF s",tenant,caseId);
        if(sources.stream().anyMatch(s->!"PUBLISHED".equals(s.get("state"))))throw new Problem(409,"A pinned policy was deactivated. Refresh policies before starting this draft.");
    }
    public Map<String,Object> list(UUID tenant,UUID caseId) {
        boolean initialized=Boolean.TRUE.equals(db.queryForObject("SELECT policies_initialized FROM core.cases WHERE tenant_id=? AND id=?",Boolean.class,tenant,caseId));
        return Map.of("initialized",initialized,"items",db.queryForList("SELECT s.id,s.name,p.source_version AS version,s.state FROM core.case_policy_pins p JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id WHERE p.tenant_id=? AND p.case_id=? ORDER BY s.name,s.id",tenant,caseId));
    }
}
