package dev.caseflow.evidence;

import dev.caseflow.common.*;
import dev.caseflow.documents.ObjectStorage;
import dev.caseflow.identity.Access;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.io.IOException;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}/sources")
public class SourceController {
    private final JdbcTemplate db;private final Access access;private final Commands commands;
    private final ObjectStorage storage;private final Json json;
    public SourceController(JdbcTemplate db,Access access,Commands commands,ObjectStorage storage,Json json) {
        this.db=db;this.access=access;this.commands=commands;this.storage=storage;this.json=json;
    }
    public record UploadInput(@NotBlank @Size(max=120) String name,@NotNull Kind kind,UUID caseId,
        @NotBlank @Pattern(regexp="text/plain|application/pdf") String mediaType,
        @Min(1) @Max(10485760) int byteSize,@PositiveOrZero Long expectedCaseVersion) {}
    public record VersionInput(@NotNull @PositiveOrZero Long expectedVersion,@PositiveOrZero Long expectedCaseVersion) {}
    public enum Kind { QUOTE,POLICY }
    private Map<String,Object> one(UUID tenant,UUID id,boolean lock) {
        var rows=db.queryForList("SELECT * FROM core.sources WHERE tenant_id=? AND id=?"+(lock?" FOR UPDATE":""),tenant,id);
        if(rows.isEmpty())throw Problem.missing();return rows.getFirst();
    }
    private void authorize(UUID tenant,UUID actor,Map<String,Object> source,boolean write,boolean lock) {
        var roles=access.member(tenant,actor,lock);
        if("POLICY".equals(source.get("kind"))) {
            if(write&&!roles.contains("ADMIN"))throw Problem.forbidden();
            if(!write&&!roles.contains("ADMIN")&&!"PUBLISHED".equals(source.get("state")))throw Problem.missing();
        } else {
            UUID caseId=(UUID)source.get("case_id");access.caseVisible(tenant,actor,caseId,lock);
            if(write) {
                access.role(tenant,actor,"REQUESTER",false);
                UUID owner=db.queryForObject("SELECT owner_id FROM core.cases WHERE tenant_id=? AND id=?",UUID.class,tenant,caseId);
                if(!actor.equals(owner))throw Problem.forbidden();
            }
        }
    }
    private void draft(UUID tenant,UUID caseId,Long expected) {
        if(caseId==null)return;
        var row=db.queryForMap("SELECT state,version FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE",tenant,caseId);
        if(!"DRAFT".equals(row.get("state")))throw new Problem(409,"Quotes can only be attached to a draft");
        if(expected!=null&&expected.longValue()!=((Number)row.get("version")).longValue())throw Problem.conflict();
    }
    private Map<String,Object> output(Map<String,Object> row) {
        var result=new LinkedHashMap<String,Object>();
        for(String field:List.of("id","kind","name","state","version"))result.put(field,row.get(field));
        result.put("caseId",row.get("case_id"));result.put("mediaType",row.get("media_type"));
        result.put("byteSize",row.get("byte_size"));result.put("sha256",row.get("sha256"));
        result.put("jobId",row.get("ingestion_job_id"));result.put("failureCode",row.get("failure_code"));
        return result;
    }
    @GetMapping
    public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@RequestParam(required=false) UUID caseId) {
        UUID actor=access.identity(jwt);var roles=access.member(tenantId,actor,false);
        if(caseId!=null)access.caseVisible(tenantId,actor,caseId,false);
        var rows=caseId==null?db.queryForList("SELECT * FROM core.sources WHERE tenant_id=? AND kind='POLICY' AND (? OR state='PUBLISHED') ORDER BY created_at DESC,id DESC LIMIT 100",tenantId,roles.contains("ADMIN"))
            :db.queryForList("SELECT * FROM core.sources WHERE tenant_id=? AND case_id=? ORDER BY created_at DESC,id DESC LIMIT 100",tenantId,caseId);
        return Map.of("items",rows.stream().map(this::output).toList());
    }
    @GetMapping("/{sourceId}")
    public Map<String,Object> get(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID sourceId) {
        UUID actor=access.identity(jwt);access.member(tenantId,actor,false);var row=one(tenantId,sourceId,false);
        authorize(tenantId,actor,row,false,false);return output(row);
    }
    @GetMapping("/{sourceId}/chunks")
    public Map<String,Object> chunks(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID sourceId) {
        UUID actor=access.identity(jwt);access.member(tenantId,actor,false);var row=one(tenantId,sourceId,false);
        authorize(tenantId,actor,row,false,false);
        Problem.require(Set.of("INDEXED","PUBLISHED","DEACTIVATED").contains(row.get("state")),"Source indexing has not succeeded");
        var metadata=db.queryForList("SELECT parser_version AS \"parserVersion\",chunk_version AS \"chunkVersion\",page_count AS \"pageCount\" FROM worker.source_results WHERE tenant_id=? AND source_id=?",tenantId,sourceId);
        return Map.of("source",output(row),"metadata",metadata.getFirst(),"items",db.queryForList("SELECT id,page,section,start_offset AS start,end_offset AS end,text,sha256 FROM worker.source_chunks WHERE tenant_id=? AND source_id=? ORDER BY ordinal LIMIT 1000",tenantId,sourceId));
    }
    @PostMapping
    public Map<String,Object> allocate(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody UploadInput input) {
        UUID actor=access.identity(jwt);
        Problem.require((input.kind()==Kind.QUOTE)==(input.caseId()!=null),"Quotes require a case; policies belong to the organization");
        var scope=new HashMap<String,Object>();scope.put("kind",input.kind().name());scope.put("case_id",input.caseId());
        return commands.run(tenantId,actor,"source:create",key,input,()->authorize(tenantId,actor,scope,true,true),()->{
            if(input.caseId()!=null)Problem.require(input.expectedCaseVersion()!=null,"Expected draft version is required");
            draft(tenantId,input.caseId(),input.expectedCaseVersion());
            UUID id=UUID.randomUUID();
            db.update("INSERT INTO core.sources(tenant_id,id,case_id,kind,name,media_type,upload_key,byte_size,created_by) VALUES (?,?,?,?,?,?,?,?,?)",tenantId,id,input.caseId(),input.kind().name(),input.name(),input.mediaType(),"tenants/"+tenantId+"/uploads/sources/"+id,input.byteSize(),actor);
            commands.audit(tenantId,input.caseId(),actor,"SOURCE_UPLOAD_CREATED",Map.of("sourceId",id,"kind",input.kind()));
            return output(one(tenantId,id,false));
        });
    }
    @PutMapping(value="/{sourceId}/content",consumes="application/octet-stream")
    @Transactional
    public Map<String,Object> upload(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID sourceId,HttpServletRequest request) throws IOException {
        UUID actor=access.identity(jwt);access.member(tenantId,actor,true);var row=one(tenantId,sourceId,false);
        authorize(tenantId,actor,row,true,true);draft(tenantId,(UUID)row.get("case_id"),null);row=one(tenantId,sourceId,true);
        Problem.require("UPLOADING".equals(row.get("state")),"Source upload is closed");
        byte[] bytes=request.getInputStream().readNBytes(ObjectStorage.MAX_BYTES+1);
        Problem.require(bytes.length==((Number)row.get("byte_size")).intValue()&&bytes.length<=ObjectStorage.MAX_BYTES,"Upload size does not match");
        storage.put((String)row.get("upload_key"),bytes,false,(String)row.get("media_type"));return Map.of("uploaded",true);
    }
    @PostMapping("/{sourceId}/finalize")
    public Map<String,Object> finalizeUpload(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID sourceId,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"source:finalize:"+sourceId,key,input,()->{access.member(tenantId,actor,true);authorize(tenantId,actor,one(tenantId,sourceId,false),true,true);},()->{
            var original=one(tenantId,sourceId,false);UUID caseId=(UUID)original.get("case_id");
            if(caseId!=null)Problem.require(input.expectedCaseVersion()!=null,"Expected draft version is required");
            draft(tenantId,caseId,input.expectedCaseVersion());var row=one(tenantId,sourceId,true);
            if(input.expectedVersion()!=((Number)row.get("version")).longValue())throw Problem.conflict();
            Problem.require("UPLOADING".equals(row.get("state")),"Source has already been finalized");
            byte[] bytes=storage.read((String)row.get("upload_key"));
            Problem.require(bytes.length==((Number)row.get("byte_size")).intValue(),"Upload size does not match");
            String immutable="tenants/"+tenantId+"/sources/"+sourceId+"/"+UUID.randomUUID();String sha=ObjectStorage.checksum(bytes);
            storage.put(immutable,bytes,true,(String)row.get("media_type"));
            UUID job=UUID.randomUUID();long revision=caseId==null?1:input.expectedCaseVersion()+1;
            var payload=Map.<String,Object>of("tenantId",tenantId,"sourceId",sourceId,"sourceVersion",1,"revision",revision,"key",immutable,"sha256",sha,"byteSize",bytes.length,"mediaType",row.get("media_type"));
            String hash=json.hash(payload);
            db.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,source_id,kind,input,input_hash,requested_by) VALUES (?,?,?,?,'INGESTION',?::jsonb,?,?)",tenantId,job,caseId,sourceId,json.write(payload),hash,actor);
            db.update("UPDATE core.sources SET state='INDEXING',object_key=?,sha256=?,ingestion_job_id=?,version=version+1 WHERE tenant_id=? AND id=?",immutable,sha,job,tenantId,sourceId);
            if(caseId!=null)db.update("UPDATE core.cases SET version=version+1,updated_at=now() WHERE tenant_id=? AND id=?",tenantId,caseId);
            UUID event=UUID.randomUUID();var envelope=new LinkedHashMap<String,Object>();
            envelope.put("eventId",event);envelope.put("eventType","ingestion.requested");envelope.put("schemaVersion",1);
            envelope.put("timestamp",Instant.now().toString());envelope.put("tenantId",tenantId);envelope.put("aggregateId",caseId==null?sourceId:caseId);
            envelope.put("aggregateType",caseId==null?"policy":"case");envelope.put("aggregateSequence",revision);envelope.put("jobId",job);
            envelope.put("attempt",1);envelope.put("correlationId",job);envelope.put("causationId",key);envelope.put("traceContext",Map.of());envelope.put("inputHash",hash);
            db.update("INSERT INTO core.outbox(event_id,tenant_id,case_id,event_type,payload) VALUES (?,?,?,'ingestion.requested',?::jsonb)",event,tenantId,caseId,json.write(envelope));
            commands.audit(tenantId,caseId,actor,"SOURCE_FINALIZED",Map.of("sourceId",sourceId,"jobId",job,"sha256",sha));
            return output(one(tenantId,sourceId,false));
        });
    }
    @PostMapping("/{sourceId}/{action:publish|deactivate}")
    public Map<String,Object> policyState(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID sourceId,@PathVariable String action,@RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"source:"+action+":"+sourceId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var row=one(tenantId,sourceId,true);if(!"POLICY".equals(row.get("kind")))throw Problem.missing();
            if(input.expectedVersion()!=((Number)row.get("version")).longValue())throw Problem.conflict();
            String required="publish".equals(action)?"INDEXED":"PUBLISHED";
            Problem.require(required.equals(row.get("state")),"publish".equals(action)?"Index the policy before publishing":"Only published policies can be deactivated");
            if("publish".equals(action)&&!Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM worker.source_results WHERE tenant_id=? AND source_id=? AND job_id=? AND source_sha256=?)",Boolean.class,tenantId,sourceId,row.get("ingestion_job_id"),row.get("sha256"))))throw new Problem(409,"Verified policy index is unavailable");
            db.update("UPDATE core.sources SET state=?,version=version+1 WHERE tenant_id=? AND id=?","publish".equals(action)?"PUBLISHED":"DEACTIVATED",tenantId,sourceId);
            commands.audit(tenantId,null,actor,"POLICY_"+action.toUpperCase(Locale.ROOT),Map.of("sourceId",sourceId));return output(one(tenantId,sourceId,false));
        });
    }
}
