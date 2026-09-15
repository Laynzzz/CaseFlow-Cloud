package dev.caseflow.documents;

import dev.caseflow.common.*;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class DocumentJobs {
    private final JdbcTemplate db;private final Json json;
    public DocumentJobs(JdbcTemplate db,Json json) {this.db=db;this.json=json;}
    // Called inside the approval command's transaction; no broker or storage call here.
    public UUID request(UUID tenant,UUID caseId,UUID actor,Map<String,Object> row,String cause) {
        var templates=db.queryForList("SELECT id,object_key,sha256 FROM core.template_versions WHERE tenant_id=? AND id=? AND state='PUBLISHED'",tenant,row.get("templateId"));
        Problem.require(!templates.isEmpty(),"A published template must be pinned before approval");
        var template=templates.getFirst();
        var input=new LinkedHashMap<String,Object>();
        input.put("caseId",caseId);input.put("tenantId",tenant);input.put("purchase",row.get("purchase"));
        input.put("approvedAt",Instant.now().toString());input.put("revision",((Number)row.get("version")).longValue()+1);
        input.put("template",Map.of("id",template.get("id"),"key",template.get("object_key"),"sha256",template.get("sha256")));
        input.put("approvers",db.queryForList("SELECT i.display_name AS name,a.step FROM core.assignments a JOIN core.identities i ON i.id=a.user_id WHERE a.tenant_id=? AND a.case_id=? ORDER BY a.step",tenant,caseId));
        UUID job=UUID.randomUUID();String hash=json.hash(input);
        db.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by) VALUES (?,?,?,'DOCUMENT',?::jsonb,?,?)",tenant,job,caseId,json.write(input),hash,actor);
        enqueue(tenant,caseId,job,1,hash,((Number)input.get("revision")).longValue(),cause);
        return job;
    }
    public void enqueue(UUID tenant,UUID caseId,UUID job,int attempt,String hash,long sequence,String cause) {
        UUID event=UUID.randomUUID();var envelope=new LinkedHashMap<String,Object>();
        envelope.put("eventId",event);envelope.put("eventType","document.requested");envelope.put("schemaVersion",1);
        envelope.put("timestamp",Instant.now().toString());envelope.put("tenantId",tenant);envelope.put("aggregateId",caseId);
        envelope.put("aggregateType","case");envelope.put("aggregateSequence",sequence);envelope.put("jobId",job);
        envelope.put("attempt",attempt);envelope.put("correlationId",job);envelope.put("causationId",cause);
        envelope.put("traceContext",Map.of());envelope.put("inputHash",hash);
        db.update("INSERT INTO core.outbox(event_id,tenant_id,case_id,event_type,payload) VALUES (?,?,?,'document.requested',?::jsonb)",event,tenant,caseId,json.write(envelope));
    }
}
