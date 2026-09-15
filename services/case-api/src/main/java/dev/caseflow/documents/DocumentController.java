package dev.caseflow.documents;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}")
public class DocumentController {
    private final JdbcTemplate db;private final Access access;private final Commands commands;
    private final ObjectStorage storage;private final DocumentJobs jobs;
    public DocumentController(JdbcTemplate db,Access access,Commands commands,ObjectStorage storage,DocumentJobs jobs) {
        this.db=db;this.access=access;this.commands=commands;this.storage=storage;this.jobs=jobs;
    }
    public record RetryInput(@Min(1) int expectedAttempt) {}
    private Map<String,Object> find(UUID tenant,UUID job) {
        var rows=db.queryForList("SELECT * FROM core.job_requests WHERE tenant_id=? AND job_id=? AND kind='DOCUMENT'",tenant,job);
        if(rows.isEmpty())throw Problem.missing();return rows.getFirst();
    }
    private Map<String,Object> result(UUID tenant,UUID job) {
        var request=find(tenant,job);var out=new LinkedHashMap<String,Object>();
        out.put("jobId",job);out.put("attempt",request.get("attempt"));out.put("status",request.get("status"));
        out.put("failureCode",request.get("failure_code"));out.put("createdAt",((java.sql.Timestamp)request.get("created_at")).toInstant().toString());
        var results=db.queryForList("SELECT sha256,byte_size FROM worker.document_results WHERE tenant_id=? AND job_id=? AND attempt=? AND status='SUCCEEDED'",tenant,job,request.get("attempt"));
        out.put("sha256",results.isEmpty()?null:results.getFirst().get("sha256"));
        out.put("byteSize",results.isEmpty()?null:results.getFirst().get("byte_size"));return out;
    }
    @GetMapping("/cases/{caseId}/documents")
    public Map<String,Object> documents(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId) {
        access.caseVisible(tenantId,access.identity(jwt),caseId,false);
        return Map.of("items",db.queryForList("SELECT job_id FROM core.job_requests WHERE tenant_id=? AND case_id=? AND kind='DOCUMENT' ORDER BY created_at DESC LIMIT 100",tenantId,caseId)
            .stream().map(row->result(tenantId,(UUID)row.get("job_id"))).toList());
    }
    @GetMapping("/jobs/{jobId}")
    public Map<String,Object> status(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID jobId) {
        UUID actor=access.identity(jwt);access.member(tenantId,actor,false);var job=find(tenantId,jobId);
        access.caseVisible(tenantId,actor,(UUID)job.get("case_id"),false);return result(tenantId,jobId);
    }
    @PostMapping("/cases/{caseId}/documents/{jobId}/download-url")
    public Map<String,Object> download(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID caseId,@PathVariable UUID jobId) {
        access.caseVisible(tenantId,access.identity(jwt),caseId,false);var job=find(tenantId,jobId);
        if(!caseId.equals(job.get("case_id")))throw Problem.missing();
        if(!"SUCCEEDED".equals(job.get("status")))throw new Problem(409,"The document is not ready");
        var rows=db.queryForList("SELECT object_key FROM worker.document_results WHERE tenant_id=? AND job_id=? AND attempt=? AND status='SUCCEEDED'",tenantId,jobId,job.get("attempt"));
        if(rows.isEmpty()||rows.getFirst().get("object_key")==null)throw new Problem(503,"Document metadata is not available",true);
        return Map.of("url",storage.download((String)rows.getFirst().get("object_key")),"expiresInSeconds",60);
    }
    @PostMapping("/jobs/{jobId}/retry")
    public Map<String,Object> retry(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID jobId,
        @RequestHeader("Idempotency-Key") String key,@Valid @RequestBody RetryInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"document:retry:"+jobId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var job=find(tenantId,jobId);UUID caseId=(UUID)job.get("case_id");
            db.queryForMap("SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE",tenantId,caseId);
            job=db.queryForMap("SELECT * FROM core.job_requests WHERE tenant_id=? AND job_id=? FOR UPDATE",tenantId,jobId);
            if(!"FAILED".equals(job.get("status")) || input.expectedAttempt()!=((Number)job.get("attempt")).intValue())throw Problem.conflict();
            int attempt=input.expectedAttempt()+1;
            db.update("UPDATE core.job_requests SET attempt=?,status='QUEUED',failure_code=NULL,last_fence=0,updated_at=now() WHERE tenant_id=? AND job_id=?",attempt,tenantId,jobId);
            db.update("UPDATE core.cases SET document_status='QUEUED' WHERE tenant_id=? AND id=? AND generation_id=?",tenantId,caseId,jobId);
            jobs.enqueue(tenantId,caseId,jobId,attempt,(String)job.get("input_hash"),0,key);
            commands.audit(tenantId,caseId,actor,"DOCUMENT_RETRY_REQUESTED",Map.of("jobId",jobId,"attempt",attempt));
            return result(tenantId,jobId);
        });
    }
}
