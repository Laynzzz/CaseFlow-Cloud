package dev.caseflow.cases;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import dev.caseflow.documents.DocumentJobs;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}/cases")
public class CaseController {
    private final JdbcTemplate db; private final Access access; private final Commands commands; private final Json json; private final CaseQueries queries;
    private final DocumentJobs documents;
    public CaseController(JdbcTemplate db,Access access,Commands commands,Json json,CaseQueries queries,DocumentJobs documents) {this.db=db;this.access=access;this.commands=commands;this.json=json;this.queries=queries;this.documents=documents;}
    public record Input(@NotNull @Valid Purchase purchase,UUID workflowId,UUID templateId,UUID originalCaseId,@PositiveOrZero Long expectedVersion) {}
    public record AssignInput(@NotNull @PositiveOrZero Long expectedVersion,@NotNull @Size(min=2,max=2) List<@NotNull UUID> approverIds) {}
    public record VersionInput(@NotNull @PositiveOrZero Long expectedVersion) {}
    public record ActionInput(@NotNull @PositiveOrZero Long expectedVersion,@NotNull Action action,@Size(max=4000) String comment) {}
    public enum Action { APPROVE,REJECT,CANCEL,COMMENT }
    private void version(Map<String,Object> row,Long expected) {
        if(expected==null || expected.longValue()!=((Number)row.get("version")).longValue()) throw Problem.conflict();
    }
    private void owner(Map<String,Object> row,UUID actor) {if(!actor.equals(row.get("ownerId"))) throw Problem.forbidden();}
    private void draft(Map<String,Object> row) {if(!"DRAFT".equals(row.get("state"))) throw new Problem(409,"Only drafts can be edited");}
    private void bump(UUID tenant,UUID id) {db.update("UPDATE core.cases SET version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",tenant,id);}
    private void workflow(UUID tenant,UUID id) {
        if(id!=null && !Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM core.workflow_versions WHERE tenant_id=? AND id=? AND published)",Boolean.class,tenant,id))) throw Problem.missing();
    }
    private void template(UUID tenant,UUID id) {
        if(id!=null && !Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM core.template_versions WHERE tenant_id=? AND id=? AND state='PUBLISHED')",Boolean.class,tenant,id)))throw Problem.missing();
    }
    @GetMapping
    public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@RequestParam(required=false) String state,@RequestParam(defaultValue="false") boolean assignedToMe,@RequestParam(required=false) String cursor,@RequestParam(defaultValue="25") int limit) {
        return queries.list(tenantId,access.identity(jwt),state,assignedToMe,cursor,limit);
    }
    @GetMapping("/{caseId}")
    public Map<String,Object> get(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId) {
        UUID actor=access.identity(jwt);access.caseVisible(tenantId,actor,caseId,false);return queries.one(tenantId,caseId,false);
    }
    @PostMapping
    public Map<String,Object> create(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody Input input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"case:create",key,input,()->access.role(tenantId,actor,"REQUESTER",true),()->{
            workflow(tenantId,input.workflowId());template(tenantId,input.templateId());
            if(input.originalCaseId()!=null) {
                access.caseVisible(tenantId,actor,input.originalCaseId(),false);var old=queries.one(tenantId,input.originalCaseId(),true);owner(old,actor);
                Problem.require(Set.of("REJECTED","CANCELLED").contains(old.get("state")),"Only rejected or cancelled cases can be corrected");
            }
            UUID id=UUID.randomUUID();
            db.update("INSERT INTO core.cases(tenant_id,id,owner_id,purchase,workflow_id,template_id,original_case_id) VALUES (?,?,?,?::jsonb,?,?,?)",tenantId,id,actor,json.write(input.purchase().normalized(false)),input.workflowId(),input.templateId(),input.originalCaseId());
            commands.audit(tenantId,id,actor,"DRAFT_CREATED",Map.of()); return queries.one(tenantId,id,false);
        });
    }
    @PutMapping("/{caseId}")
    public Map<String,Object> update(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody Input input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"case:update:"+caseId,key,input,()->{access.caseVisible(tenantId,actor,caseId,true);access.role(tenantId,actor,"REQUESTER",false);},()->{
            var row=queries.one(tenantId,caseId,true);owner(row,actor);draft(row);version(row,input.expectedVersion());workflow(tenantId,input.workflowId());template(tenantId,input.templateId());
            db.update("UPDATE core.cases SET purchase=?::jsonb,workflow_id=?,template_id=?,version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",json.write(input.purchase().normalized(false)),input.workflowId(),input.templateId(),tenantId,caseId);
            commands.audit(tenantId,caseId,actor,"DRAFT_UPDATED",Map.of("previousVersion",row.get("version")));return queries.one(tenantId,caseId,false);
        });
    }
    @PutMapping("/{caseId}/assignments")
    public Map<String,Object> assign(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody AssignInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"case:assign:"+caseId,key,input,()->access.caseVisible(tenantId,actor,caseId,true),()->{
            var row=queries.one(tenantId,caseId,true);version(row,input.expectedVersion());
            var roles=access.member(tenantId,actor,false);
            if(!roles.contains("ADMIN")) {owner(row,actor);draft(row);access.role(tenantId,actor,"REQUESTER",false);}
            if(!Set.of("DRAFT","ACTIVE").contains(row.get("state"))) throw new Problem(409,"Terminal cases cannot be reassigned");
            Problem.require(!input.approverIds().contains(row.get("ownerId")),"A requester cannot approve their own case");
            // Lock candidates in stable order; deactivation cannot race assignment eligibility.
            input.approverIds().stream().distinct().sorted().forEach(id->access.role(tenantId,id,"APPROVER",true));
            for(int step=0;step<2;step++) {
                var old=db.queryForList("SELECT user_id,outcome FROM core.assignments WHERE tenant_id=? AND case_id=? AND step=?",tenantId,caseId,step);
                UUID assigned=input.approverIds().get(step);
                if(!old.isEmpty() && old.getFirst().get("outcome")!=null) {
                    if(!assigned.equals(old.getFirst().get("user_id"))) throw new Problem(409,"A completed step cannot be reassigned");
                } else {
                    db.update("INSERT INTO core.assignments(tenant_id,case_id,step,user_id) VALUES (?,?,?,?) ON CONFLICT (tenant_id,case_id,step) DO UPDATE SET user_id=EXCLUDED.user_id",tenantId,caseId,step,assigned);
                }
            }
            bump(tenantId,caseId);commands.audit(tenantId,caseId,actor,"ASSIGNMENTS_CHANGED",Map.of("approverIds",input.approverIds()));return queries.one(tenantId,caseId,false);
        });
    }
    @PostMapping("/{caseId}/start")
    public Map<String,Object> start(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"case:start:"+caseId,key,input,()->{access.caseVisible(tenantId,actor,caseId,true);access.role(tenantId,actor,"REQUESTER",false);},()->{
            var row=queries.one(tenantId,caseId,true);owner(row,actor);draft(row);version(row,input.expectedVersion());
            var purchase=new LinkedHashMap<>((Map<String,Object>)row.get("purchase"));purchase.remove("total");json.convert(purchase,Purchase.class).normalized(true);
            Problem.require(row.get("workflowId")!=null,"Select a published workflow");workflow(tenantId,(UUID)row.get("workflowId"));
            Problem.require(row.get("templateId")!=null,"Select a published document template");template(tenantId,(UUID)row.get("templateId"));
            var assignments=db.queryForList("SELECT user_id FROM core.assignments WHERE tenant_id=? AND case_id=? ORDER BY step",tenantId,caseId);
            Problem.require(assignments.size()==2,"Assign two approval steps");
            assignments.stream().map(a->(UUID)a.get("user_id")).distinct().sorted().forEach(id->{Problem.require(!actor.equals(id),"Self-approval is prohibited");access.role(tenantId,id,"APPROVER",true);});
            db.update("UPDATE core.cases SET state='ACTIVE',workflow_snapshot=(SELECT steps FROM core.workflow_versions WHERE tenant_id=? AND id=?),version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",tenantId,row.get("workflowId"),tenantId,caseId);
            commands.audit(tenantId,caseId,actor,"CASE_STARTED",Map.of("workflowId",row.get("workflowId")));return queries.one(tenantId,caseId,false);
        });
    }
    @PostMapping("/{caseId}/actions")
    public Map<String,Object> act(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody ActionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"case:action:"+caseId,key,input,()->{
            access.caseVisible(tenantId,actor,caseId,true);
            var roles=access.member(tenantId,actor,false);
            switch(input.action()) {
                case APPROVE,REJECT -> {if(!roles.contains("APPROVER")) throw Problem.forbidden();}
                case CANCEL -> {if(!roles.contains("REQUESTER")) throw Problem.forbidden();}
                case COMMENT -> {if(Collections.disjoint(roles,Set.of("ADMIN","REQUESTER","APPROVER"))) throw Problem.forbidden();}
            }
        },()->{
            var row=queries.one(tenantId,caseId,true);version(row,input.expectedVersion());
            if(input.action()==Action.COMMENT) {
                Problem.require(input.comment()!=null&&!input.comment().isBlank(),"Enter a comment");
            } else if(input.action()==Action.CANCEL) {
                owner(row,actor);if(!Set.of("DRAFT","ACTIVE").contains(row.get("state"))) throw new Problem(409,"This case is terminal");
                db.update("UPDATE core.cases SET state='CANCELLED' WHERE tenant_id=? AND id=?",tenantId,caseId);
            } else {
                if(!"ACTIVE".equals(row.get("state"))) throw new Problem(409,"Only active cases can be reviewed");
                if(actor.equals(row.get("ownerId"))) throw Problem.forbidden();
                var next=db.queryForList("SELECT step,user_id FROM core.assignments WHERE tenant_id=? AND case_id=? AND outcome IS NULL ORDER BY step LIMIT 1",tenantId,caseId);
                if(next.isEmpty() || !actor.equals(next.getFirst().get("user_id"))) throw new Problem(403,"Only the current assigned approver may decide");
                String outcome=input.action()==Action.APPROVE?"APPROVED":"REJECTED";
                db.update("UPDATE core.assignments SET outcome=?,decided_at=now() WHERE tenant_id=? AND case_id=? AND step=?",outcome,tenantId,caseId,next.getFirst().get("step"));
                if(input.action()==Action.REJECT) db.update("UPDATE core.cases SET state='REJECTED' WHERE tenant_id=? AND id=?",tenantId,caseId);
                else if(((Number)next.getFirst().get("step")).intValue()==1) {
                    UUID job=documents.request(tenantId,caseId,actor,row,key);
                    db.update("UPDATE core.cases SET state='APPROVED',approved_at=now(),generation_id=?,document_status='QUEUED' WHERE tenant_id=? AND id=?",job,tenantId,caseId);
                }
            }
            bump(tenantId,caseId);commands.audit(tenantId,caseId,actor,"CASE_"+input.action(),Map.of("comment",input.comment()==null?"":input.comment()));return queries.one(tenantId,caseId,false);
        });
    }
    @GetMapping("/{caseId}/audit")
    public Map<String,Object> audit(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestParam(required=false) String cursor,@RequestParam(defaultValue="25") int limit) {
        return queries.audit(tenantId,access.identity(jwt),caseId,cursor,limit);
    }
}
