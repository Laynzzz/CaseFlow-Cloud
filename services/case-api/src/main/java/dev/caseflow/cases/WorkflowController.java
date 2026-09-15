package dev.caseflow.cases;

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
@RequestMapping("/api/v1/tenants/{tenantId}/workflows")
public class WorkflowController {
    private final JdbcTemplate db; private final Access access; private final Commands commands; private final Json json;
    public WorkflowController(JdbcTemplate db,Access access,Commands commands,Json json) { this.db=db;this.access=access;this.commands=commands;this.json=json; }
    public record Input(@NotBlank @Size(max=120) String name,@NotNull @Size(min=2,max=2) List<@NotBlank @Size(max=80) String> steps,@PositiveOrZero Long expectedVersion) {}
    public record VersionInput(@NotNull @PositiveOrZero Long expectedVersion) {}
    private Map<String,Object> row(java.sql.ResultSet rs) throws java.sql.SQLException {
        return Map.of("id",rs.getObject("id"),"name",rs.getString("name"),"steps",json.list(rs.getString("steps")),"published",rs.getBoolean("published"),"version",rs.getLong("version"));
    }
    private Map<String,Object> one(UUID tenant,UUID id,boolean lock) {
        var rows=db.query("SELECT * FROM core.workflow_versions WHERE tenant_id=? AND id=?"+(lock?" FOR UPDATE":""),(rs,n)->row(rs),tenant,id);
        if(rows.isEmpty()) throw Problem.missing(); return rows.getFirst();
    }
    @GetMapping
    public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId) {
        var roles=access.member(tenantId,access.identity(jwt),false);
        return Map.of("items",db.query("SELECT * FROM core.workflow_versions WHERE tenant_id=? AND (published OR ?) ORDER BY created_at DESC,id DESC",(rs,n)->row(rs),tenantId,roles.contains("ADMIN")));
    }
    @PostMapping
    public Map<String,Object> create(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody Input input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"workflow:create",key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            UUID id=UUID.randomUUID();
            db.update("INSERT INTO core.workflow_versions(tenant_id,id,name,steps) VALUES (?,?,?,?::jsonb)",tenantId,id,input.name().trim(),json.write(input.steps()));
            commands.audit(tenantId,null,actor,"WORKFLOW_CREATED",Map.of("workflowId",id)); return one(tenantId,id,false);
        });
    }
    @PutMapping("/{workflowId}")
    public Map<String,Object> update(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID workflowId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody Input input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"workflow:update:"+workflowId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var old=one(tenantId,workflowId,true);
            if(Boolean.TRUE.equals(old.get("published"))) throw new Problem(409,"Published versions cannot be changed. Create a new draft version.");
            if(input.expectedVersion()==null || input.expectedVersion().longValue()!=((Number)old.get("version")).longValue()) throw Problem.conflict();
            db.update("UPDATE core.workflow_versions SET name=?,steps=?::jsonb,version=version+1 WHERE tenant_id=? AND id=?",input.name().trim(),json.write(input.steps()),tenantId,workflowId);
            commands.audit(tenantId,null,actor,"WORKFLOW_UPDATED",Map.of("workflowId",workflowId)); return one(tenantId,workflowId,false);
        });
    }
    @PostMapping("/{workflowId}/publish")
    public Map<String,Object> publish(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID workflowId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"workflow:publish:"+workflowId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var old=one(tenantId,workflowId,true);
            if(Boolean.TRUE.equals(old.get("published")) || input.expectedVersion().longValue()!=((Number)old.get("version")).longValue()) throw Problem.conflict();
            db.update("UPDATE core.workflow_versions SET published=true,version=version+1 WHERE tenant_id=? AND id=?",tenantId,workflowId);
            commands.audit(tenantId,null,actor,"WORKFLOW_PUBLISHED",Map.of("workflowId",workflowId)); return one(tenantId,workflowId,false);
        });
    }
}
