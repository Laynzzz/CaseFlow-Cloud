package dev.caseflow.evidence;

import dev.caseflow.cases.Purchase;
import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import jakarta.validation.Valid;
import jakarta.validation.Validator;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}/cases/{caseId}/assistant")
public class AssistantController {
    private final JdbcTemplate db;private final Access access;private final Commands commands;private final Json json;private final Validator validator;
    public AssistantController(JdbcTemplate db,Access access,Commands commands,Json json,Validator validator){this.db=db;this.access=access;this.commands=commands;this.json=json;this.validator=validator;}
    public record RunInput(@NotNull Kind kind,@NotNull @PositiveOrZero Long expectedVersion,UUID sourceId,Boolean compareRetrieval) {
        public RunInput { compareRetrieval=Boolean.TRUE.equals(compareRetrieval); }
        public RunInput(Kind kind,Long expectedVersion,UUID sourceId){this(kind,expectedVersion,sourceId,false);}
    }
    public record AcceptInput(@NotNull @PositiveOrZero Long expectedVersion,@NotNull @Size(min=1,max=3) Set<String> fields) {}
    public enum Kind { EXTRACTION,REVIEW }
    private Map<String,Object> current(UUID tenant,UUID caseId,boolean lock) {
        return db.queryForMap("SELECT * FROM core.cases WHERE tenant_id=? AND id=?"+(lock?" FOR UPDATE":""),tenant,caseId);
    }
    private Map<String,Object> job(UUID tenant,UUID caseId,UUID id) {
        var rows=db.queryForList("SELECT * FROM core.job_requests WHERE tenant_id=? AND case_id=? AND job_id=? AND kind IN ('EXTRACTION','REVIEW')",tenant,caseId,id);
        if(rows.isEmpty())throw Problem.missing();return rows.getFirst();
    }
    private Map<String,Object> output(Map<String,Object> row,long revision) {
        var input=json.object(row.get("input").toString());var value=new LinkedHashMap<String,Object>();
        value.put("jobId",row.get("job_id"));value.put("kind",row.get("kind"));value.put("status",row.get("status"));value.put("failureCode",row.get("failure_code"));
        value.put("revision",input.get("revision"));value.put("stale",((Number)input.get("revision")).longValue()!=revision);
        var results=db.queryForList("SELECT result FROM worker.assistant_results WHERE tenant_id=? AND job_id=? AND attempt=?",row.get("tenant_id"),row.get("job_id"),row.get("attempt"));
        boolean excluded="REVIEW".equals(row.get("kind"))&&Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM core.cases c JOIN core.case_policy_pins p ON p.tenant_id=c.tenant_id AND p.case_id=c.id JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id WHERE c.tenant_id=? AND c.id=? AND c.state='DRAFT' AND s.state<>'PUBLISHED')",Boolean.class,row.get("tenant_id"),row.get("case_id")));
        if(excluded)value.put("stale",true);
        value.put("result",!excluded&&"SUCCEEDED".equals(row.get("status"))&&!results.isEmpty()?json.object(results.getFirst().get("result").toString()):null);return value;
    }
    @GetMapping public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId) {
        access.caseVisible(tenantId,access.identity(jwt),caseId,false);long version=((Number)current(tenantId,caseId,false).get("version")).longValue();
        boolean enabled=Boolean.TRUE.equals(db.queryForObject("SELECT enabled FROM worker.ai_availability",Boolean.class));
        return Map.of("enabled",enabled,"items",db.queryForList("SELECT * FROM core.job_requests WHERE tenant_id=? AND case_id=? AND kind IN ('EXTRACTION','REVIEW') ORDER BY created_at DESC LIMIT 20",tenantId,caseId).stream().map(row->output(row,version)).toList());
    }
    @PostMapping public Map<String,Object> run(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody RunInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"assistant:run:"+caseId,key,input,()->{
            access.caseVisible(tenantId,actor,caseId,true);var roles=access.member(tenantId,actor,false);
            if(Collections.disjoint(roles,Set.of("ADMIN","REQUESTER","APPROVER")))throw Problem.forbidden();
        },()->{
            var row=current(tenantId,caseId,true);long revision=((Number)row.get("version")).longValue();
            if(revision!=input.expectedVersion())throw Problem.conflict();
            Problem.require(Set.of("DRAFT","ACTIVE").contains(row.get("state")),"New AI jobs are only available on draft or active purchases");
            if(!Boolean.TRUE.equals(db.queryForObject("SELECT enabled FROM worker.ai_availability",Boolean.class)))throw new Problem(503,"AI testing is not configured. Manual purchase entry and policy search are available.");
            List<String> policies=new ArrayList<>();
            if(input.kind()==Kind.EXTRACTION) {
                Problem.require(!input.compareRetrieval(),"Retrieval comparison is available for policy reviews only");
                access.role(tenantId,actor,"REQUESTER",false);
                if(!actor.equals(row.get("owner_id"))||!"DRAFT".equals(row.get("state")))throw Problem.forbidden();
                if(input.sourceId()==null||!Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM core.sources WHERE tenant_id=? AND id=? AND case_id=? AND kind='QUOTE' AND state='INDEXED')",Boolean.class,tenantId,input.sourceId(),caseId)))throw Problem.missing();
            } else {
                Problem.require(input.sourceId()==null,"Policy review does not accept a quote source ID");
                if(!Boolean.TRUE.equals(row.get("policies_initialized")))throw new Problem(409,"Refresh the purchase policies before requesting a review");
                var pins=db.queryForList("SELECT s.id,s.state FROM core.case_policy_pins p JOIN core.sources s ON s.tenant_id=p.tenant_id AND s.id=p.source_id WHERE p.tenant_id=? AND p.case_id=? ORDER BY s.id FOR SHARE OF s",tenantId,caseId);
                if("DRAFT".equals(row.get("state"))&&pins.stream().anyMatch(p->!"PUBLISHED".equals(p.get("state"))))throw new Problem(409,"Refresh deactivated policies before requesting a new review");
                policies=pins.stream().map(p->p.get("id").toString()).toList();
            }
            // Bound queue admission as well as provider spending; repeats at one revision reuse the logical job.
            if(!Boolean.TRUE.equals(db.queryForObject("SELECT pg_try_advisory_xact_lock(hashtextextended(?,29))",Boolean.class,tenantId.toString())))throw new Problem(409,"AI admission is busy. Retry with the same key.",true);
            var existing=db.queryForList("SELECT * FROM core.job_requests WHERE tenant_id=? AND case_id=? AND kind=? AND source_id IS NOT DISTINCT FROM ? AND input->>'revision'=? AND COALESCE((input->>'compareRetrieval')::boolean,false)=? AND status<>'FAILED' ORDER BY created_at DESC LIMIT 1",tenantId,caseId,input.kind().name(),input.sourceId(),Long.toString(revision),input.compareRetrieval());
            if(!existing.isEmpty())return output(existing.getFirst(),revision);
            int active=db.queryForObject("SELECT count(*) FROM core.job_requests WHERE tenant_id=? AND kind IN ('EXTRACTION','REVIEW') AND status IN ('QUEUED','RUNNING','RETRY_WAIT')",Integer.class,tenantId);
            if(active>=10)throw new Problem(409,"The organization AI queue is full. Try again later.",true);
            UUID jobId=UUID.randomUUID();var payload=new LinkedHashMap<String,Object>();payload.put("revision",revision);payload.put("purchase",json.object(row.get("purchase").toString()));payload.put("policyIds",policies);payload.put("sourceId",input.sourceId());
            payload.put("compareRetrieval",input.compareRetrieval());
            if(input.kind()==Kind.EXTRACTION) {
                var source=db.queryForMap("SELECT version,sha256 FROM core.sources WHERE tenant_id=? AND id=?",tenantId,input.sourceId());
                payload.put("sourceVersion",source.get("version"));payload.put("sourceSha256",source.get("sha256"));
            }
            String hash=json.hash(payload);
            db.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,source_id,kind,input,input_hash,requested_by) VALUES (?,?,?,?,?,?::jsonb,?,?)",tenantId,jobId,caseId,input.sourceId(),input.kind().name(),json.write(payload),hash,actor);
            UUID event=UUID.randomUUID();var envelope=new LinkedHashMap<String,Object>();
            envelope.put("eventId",event);envelope.put("eventType",input.kind().name().toLowerCase(Locale.ROOT)+".requested");envelope.put("schemaVersion",1);envelope.put("timestamp",Instant.now().toString());envelope.put("tenantId",tenantId);envelope.put("aggregateId",caseId);envelope.put("aggregateType","case");envelope.put("aggregateSequence",revision);envelope.put("jobId",jobId);envelope.put("attempt",1);envelope.put("correlationId",jobId);envelope.put("causationId",key);envelope.put("traceContext",Map.of());envelope.put("inputHash",hash);
            db.update("INSERT INTO core.outbox(event_id,tenant_id,case_id,event_type,payload) VALUES (?,?,?,?,?::jsonb)",event,tenantId,caseId,envelope.get("eventType"),json.write(envelope));
            commands.audit(tenantId,caseId,actor,"AI_"+input.kind()+"_REQUESTED",Map.of("jobId",jobId,"revision",revision));return output(job(tenantId,caseId,jobId),revision);
        });
    }
    @PostMapping("/{jobId}/accept") public Map<String,Object> accept(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@PathVariable UUID jobId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody AcceptInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"assistant:accept:"+jobId,key,input,()->{access.caseVisible(tenantId,actor,caseId,true);access.role(tenantId,actor,"REQUESTER",false);},()->{
            var row=current(tenantId,caseId,true);if(!actor.equals(row.get("owner_id")))throw Problem.forbidden();
            if(!"DRAFT".equals(row.get("state"))||input.expectedVersion()!=((Number)row.get("version")).longValue())throw Problem.conflict();
            var request=job(tenantId,caseId,jobId);var result=output(request,input.expectedVersion());
            if(!"EXTRACTION".equals(request.get("kind"))||!"SUCCEEDED".equals(request.get("status"))||Boolean.TRUE.equals(result.get("stale"))||result.get("result")==null)throw new Problem(409,"Only successful suggestions for this exact draft version can be accepted");
            Problem.require(Set.of("vendor","currency","lineItems").containsAll(input.fields()),"Choose vendor, currency or line items; totals are computed from items");
            var generated=(Map<String,Object>)((Map<String,Object>)result.get("result")).get("output");
            var before=json.object(row.get("purchase").toString());var changed=new LinkedHashMap<>(before);changed.remove("total");
            for(String field:input.fields()) {var suggested=(Map<String,Object>)generated.get(field);Problem.require(suggested.get("value")!=null,"Missing values cannot be accepted");changed.put(field,suggested.get("value"));}
            if(input.fields().contains("lineItems")) {
                Object suggestedCurrency=((Map<String,Object>)generated.get("currency")).get("value");
                Problem.require(suggestedCurrency!=null&&suggestedCurrency.equals(changed.get("currency")),"Accept the quote currency with its line items or match the draft currency first");
            }
            Purchase purchase=json.convert(changed,Purchase.class);Problem.require(validator.validate(purchase).isEmpty(),"Suggested fields do not satisfy purchase validation");
            var normalized=purchase.normalized(false);
            Object suggestedTotal=((Map<String,Object>)generated.get("total")).get("value");
            if(input.fields().contains("lineItems")&&suggestedTotal!=null)Problem.require(new BigDecimal(suggestedTotal.toString()).compareTo(new BigDecimal(normalized.get("total").toString()))==0,"Suggested total does not match the selected items");
            db.update("UPDATE core.cases SET purchase=?::jsonb,version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",json.write(normalized),tenantId,caseId);
            commands.audit(tenantId,caseId,actor,"AI_SUGGESTIONS_ACCEPTED",Map.of("jobId",jobId,"fields",input.fields(),"before",before,"suggested",generated,"accepted",normalized));
            return Map.of("accepted",true,"version",input.expectedVersion()+1);
        });
    }
}
