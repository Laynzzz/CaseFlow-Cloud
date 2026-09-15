package dev.caseflow.documents;

import dev.caseflow.common.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CompletionHandler {
    private final JdbcTemplate db;private final Commands commands;
    public CompletionHandler(JdbcTemplate db,Commands commands) {this.db=db;this.commands=commands;}
    private static final Map<String,Integer> RANK=Map.of("QUEUED",0,"RUNNING",1,"RETRY_WAIT",2,"FAILED",3,"SUCCEEDED",4);
    @Transactional
    public void apply(Map<String,Object> event) {
        UUID id=UUID.fromString((String)event.get("eventId"));
        if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM core.event_inbox WHERE event_id=?)",Boolean.class,id)))return;
        UUID tenant=UUID.fromString((String)event.get("tenantId")),jobId=UUID.fromString((String)event.get("jobId")),aggregate=UUID.fromString((String)event.get("aggregateId"));
        boolean policy="policy".equals(event.get("aggregateType"));
        if(!Integer.valueOf(1).equals(event.get("schemaVersion")) || (!policy&&!"case".equals(event.get("aggregateType")))) {receipt(id,"QUARANTINED","UNSUPPORTED_SCHEMA");return;}
        UUID caseId=policy?null:aggregate;
        var rows=policy?db.queryForList("SELECT id FROM core.sources WHERE tenant_id=? AND id=? AND kind='POLICY' FOR UPDATE",tenant,aggregate)
            :db.queryForList("SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE",tenant,caseId);
        var requests=db.queryForList("SELECT * FROM core.job_requests WHERE tenant_id=? AND job_id=? AND case_id IS NOT DISTINCT FROM ? AND (? OR source_id=?) FOR UPDATE",tenant,jobId,caseId,!policy,aggregate);
        if(rows.isEmpty()||requests.isEmpty()){receipt(id,"QUARANTINED","UNKNOWN_JOB");return;}
        var job=requests.getFirst();int attempt=((Number)event.get("attempt")).intValue();long fence=((Number)event.get("fence")).longValue();
        String status=(String)event.get("status");int current=((Number)job.get("attempt")).intValue();long previousFence=((Number)job.get("last_fence")).longValue();
        String kind=(String)job.get("kind");
        if(!RANK.containsKey(status)||!Objects.equals(event.get("eventType"),kind.toLowerCase(Locale.ROOT)+"."+status.toLowerCase(Locale.ROOT))||!Objects.equals(event.get("inputHash"),job.get("input_hash"))){receipt(id,"QUARANTINED","INVALID_COMPLETION");return;}
        if(attempt<current||"SUCCEEDED".equals(job.get("status"))||fence<previousFence){receipt(id,"STALE","OLDER_EXECUTION");return;}
        if(attempt>current){receipt(id,"QUARANTINED","FUTURE_ATTEMPT");return;}
        var worker=db.queryForList("SELECT * FROM worker.job_results WHERE tenant_id=? AND job_id=? AND attempt=?",tenant,jobId,attempt);
        if(worker.isEmpty()||fence>((Number)worker.getFirst().get("fence")).longValue()){receipt(id,"QUARANTINED","UNPROVEN_EXECUTION");return;}
        if(fence<((Number)worker.getFirst().get("fence")).longValue() || (fence==previousFence&&RANK.get(status)<=RANK.get((String)job.get("status")))){receipt(id,"STALE","OLDER_STATUS");return;}
        if("SUCCEEDED".equals(status)&&(!"SUCCEEDED".equals(worker.getFirst().get("status"))||!Boolean.TRUE.equals(worker.getFirst().get("result_exists")))){receipt(id,"QUARANTINED","MISSING_RESULT");return;}
        if("SUCCEEDED".equals(worker.getFirst().get("status"))&& !"SUCCEEDED".equals(status)){receipt(id,"STALE","WORKER_ALREADY_SUCCEEDED");return;}
        db.update("UPDATE core.job_requests SET status=?,last_fence=?,failure_code=?,updated_at=now() WHERE tenant_id=? AND job_id=?",status,fence,event.get("failureCode"),tenant,jobId);
        if("DOCUMENT".equals(kind)) db.update("UPDATE core.cases SET document_status=? WHERE tenant_id=? AND id=? AND generation_id=? AND state='APPROVED'",status,tenant,caseId,jobId);
        if("INGESTION".equals(kind)&&Set.of("SUCCEEDED","FAILED").contains(status))
            db.update("UPDATE core.sources SET state=?,failure_code=? WHERE tenant_id=? AND id=? AND ingestion_job_id=? AND state='INDEXING'", "SUCCEEDED".equals(status)?"INDEXED":"FAILED",event.get("failureCode"),tenant,job.get("source_id"),jobId);
        commands.audit(tenant,caseId,(UUID)job.get("requested_by"),kind+"_"+status,Map.of("jobId",jobId,"attempt",attempt,"fence",fence,"actorType","SYSTEM"));
        receipt(id,"APPLIED",null);
    }
    private void receipt(UUID id,String disposition,String reason) {
        db.update("INSERT INTO core.event_inbox(event_id,disposition,reason) VALUES (?,?,?) ON CONFLICT DO NOTHING",id,disposition,reason);
    }
}
