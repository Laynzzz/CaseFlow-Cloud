package dev.caseflow.identity;

import dev.caseflow.common.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
public class IdentityController {
    private final JdbcTemplate db;
    private final Access access;
    private final Commands commands;
    public IdentityController(JdbcTemplate db, Access access, Commands commands) {
        this.db=db; this.access=access; this.commands=commands;
    }
    public record TenantInput(@NotBlank @Size(max=120) String name) {}
    public record MembershipInput(@NotNull UUID userId, @NotEmpty Set<String> roles,
                                  boolean active, @PositiveOrZero Long expectedVersion) {}

    @GetMapping("/me")
    public Map<String,Object> me(@AuthenticationPrincipal Jwt jwt) {
        UUID actor = access.identity(jwt);
        var memberships = db.query("""
                SELECT t.id,t.name,m.roles,m.active,m.version FROM core.tenants t
                JOIN core.memberships m ON m.tenant_id=t.id WHERE m.user_id=? AND m.active ORDER BY t.name,t.id
                """, (rs,n) -> Map.of("id",rs.getObject("id"),"name",rs.getString("name"),
                "roles",rs.getArray("roles").getArray(),"active",rs.getBoolean("active"),"version",rs.getLong("version")), actor);
        String name=db.queryForObject("SELECT display_name FROM core.identities WHERE id=?",String.class,actor);
        return Map.of("id",actor,"displayName",name,"memberships",memberships);
    }

    @PostMapping("/tenants")
    @Transactional
    public Map<String,Object> createTenant(@AuthenticationPrincipal Jwt jwt, @Valid @RequestBody TenantInput input) {
        UUID actor=access.identity(jwt), tenant=UUID.randomUUID();
        db.update("INSERT INTO core.tenants(id,name) VALUES (?,?)",tenant,input.name().trim());
        db.update("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (?, ?, ARRAY['ADMIN','REQUESTER'])",tenant,actor);
        commands.audit(tenant,null,actor,"TENANT_CREATED",Map.of("name",input.name().trim()));
        return Map.of("id",tenant,"name",input.name().trim());
    }

    @GetMapping("/tenants/{tenantId}/memberships")
    public Map<String,Object> memberships(@AuthenticationPrincipal Jwt jwt, @PathVariable UUID tenantId) {
        UUID actor=access.identity(jwt); access.member(tenantId,actor,false);
        return Map.of("items",db.query("""
                SELECT m.*,i.display_name FROM core.memberships m JOIN core.identities i ON i.id=m.user_id
                WHERE m.tenant_id=? ORDER BY i.display_name,m.user_id
                """,(rs,n)-> Map.of("userId",rs.getObject("user_id"),"displayName",rs.getString("display_name"),
                "roles",rs.getArray("roles").getArray(),"active",rs.getBoolean("active"),"version",rs.getLong("version")),tenantId));
    }

    @PutMapping("/tenants/{tenantId}/memberships")
    public Map<String,Object> saveMembership(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,
            @RequestHeader("Idempotency-Key") String key,@Valid @RequestBody MembershipInput input) {
        UUID actor=access.identity(jwt);
        Problem.require(Set.of("ADMIN","REQUESTER","APPROVER","AUDITOR").containsAll(input.roles()),"Invalid roles");
        return commands.run(tenantId,actor,"membership:"+input.userId(),key,input,()->{
            access.role(tenantId,actor,"ADMIN",false);
            // Serialize membership changes, including concurrent attempts to remove the last administrator.
            db.queryForObject("SELECT id FROM core.tenants WHERE id=? FOR UPDATE",UUID.class,tenantId);
            access.role(tenantId,actor,"ADMIN",true);
        },()->{
            var known=db.queryForList("SELECT display_name FROM core.identities WHERE id=?",input.userId());
            if(known.isEmpty()) throw new Problem(400,"The identity must sign in before it can be added");
            var old=db.queryForList("SELECT version,roles,active FROM core.memberships WHERE tenant_id=? AND user_id=? FOR UPDATE",tenantId,input.userId());
            String roles="{"+String.join(",",new TreeSet<>(input.roles()))+"}";
            long next=0;
            if(old.isEmpty()) {
                if(input.expectedVersion()!=null) throw Problem.conflict();
                db.update("INSERT INTO core.memberships(tenant_id,user_id,roles,active) VALUES (?,?,?::text[],?)",tenantId,input.userId(),roles,input.active());
            } else {
                long previous=((Number)old.getFirst().get("version")).longValue();
                if(input.expectedVersion()==null || input.expectedVersion()!=previous) throw Problem.conflict();
                if(!input.active() || !input.roles().contains("ADMIN")) {
                    int others=db.queryForObject("SELECT count(*) FROM core.memberships WHERE tenant_id=? AND user_id<>? AND active AND 'ADMIN'=ANY(roles)",Integer.class,tenantId,input.userId());
                    boolean wasAdmin=Boolean.TRUE.equals(db.queryForObject("SELECT active AND 'ADMIN'=ANY(roles) FROM core.memberships WHERE tenant_id=? AND user_id=?",Boolean.class,tenantId,input.userId()));
                    if(wasAdmin && others==0) throw new Problem(409,"An organization must retain an active administrator");
                }
                next=previous+1;
                db.update("UPDATE core.memberships SET roles=?::text[],active=?,version=? WHERE tenant_id=? AND user_id=?",roles,input.active(),next,tenantId,input.userId());
            }
            commands.audit(tenantId,null,actor,"MEMBERSHIP_CHANGED",Map.of("userId",input.userId(),"roles",input.roles(),"active",input.active()));
            return Map.of("userId",input.userId(),"displayName",known.getFirst().get("display_name"),"roles",input.roles(),"active",input.active(),"version",next);
        });
    }
}
