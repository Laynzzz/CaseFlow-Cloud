package dev.caseflow.documents;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.io.IOException;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tenants/{tenantId}/templates")
public class TemplateController {
    private final JdbcTemplate db;
    private final Access access;
    private final Commands commands;
    private final ObjectStorage storage;
    private final TemplateValidator validator;
    public TemplateController(JdbcTemplate db,Access access,Commands commands,ObjectStorage storage,TemplateValidator validator) {
        this.db=db;this.access=access;this.commands=commands;this.storage=storage;this.validator=validator;
    }
    public record UploadInput(@NotBlank @Size(max=120) String name,@Min(1) @Max(10485760) int byteSize) {}
    public record VersionInput(@NotNull @PositiveOrZero Long expectedVersion) {}

    private Map<String,Object> one(UUID tenant,UUID id,boolean lock) {
        var rows=db.queryForList("SELECT * FROM core.template_versions WHERE tenant_id=? AND id=?"+(lock?" FOR UPDATE":""),tenant,id);
        if(rows.isEmpty())throw Problem.missing();return rows.getFirst();
    }
    private Map<String,Object> output(Map<String,Object> row) {
        var result=new LinkedHashMap<String,Object>();
        result.put("id",row.get("id"));result.put("name",row.get("name"));result.put("state",row.get("state"));
        result.put("version",row.get("version"));result.put("byteSize",row.get("byte_size"));result.put("sha256",row.get("sha256"));
        return result;
    }
    private void version(Map<String,Object> row,long expected) {
        if(((Number)row.get("version")).longValue()!=expected)throw Problem.conflict();
    }
    @GetMapping
    public Map<String,Object> list(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId) {
        UUID actor=access.identity(jwt);boolean admin=access.member(tenantId,actor,false).contains("ADMIN");
        return Map.of("items",db.queryForList("SELECT * FROM core.template_versions WHERE tenant_id=? AND (? OR state='PUBLISHED') ORDER BY created_at DESC,id DESC LIMIT 100",tenantId,admin).stream().map(this::output).toList());
    }
    @PostMapping
    public Map<String,Object> allocate(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,
        @RequestHeader("Idempotency-Key") String key,@Valid @RequestBody UploadInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"template:create",key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            UUID id=UUID.randomUUID();String objectKey="tenants/"+tenantId+"/uploads/templates/"+id;
            db.update("INSERT INTO core.template_versions(tenant_id,id,name,upload_key,byte_size,created_by) VALUES (?,?,?,?,?,?)",tenantId,id,input.name(),objectKey,input.byteSize(),actor);
            commands.audit(tenantId,null,actor,"TEMPLATE_UPLOAD_CREATED",Map.of("templateId",id));
            return output(one(tenantId,id,false));
        });
    }
    @PutMapping(value="/{templateId}/content",consumes="application/octet-stream")
    public Map<String,Object> upload(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID templateId,HttpServletRequest request) throws IOException {
        access.role(tenantId,access.identity(jwt),"ADMIN",false);var row=one(tenantId,templateId,false);
        Problem.require("UPLOADING".equals(row.get("state")),"Template upload is closed");
        byte[] bytes=request.getInputStream().readNBytes(ObjectStorage.MAX_BYTES+1);
        Problem.require(bytes.length==((Number)row.get("byte_size")).intValue() && bytes.length<=ObjectStorage.MAX_BYTES,"Upload size does not match the declared size");
        storage.put((String)row.get("upload_key"),bytes,false);
        return Map.of("uploaded",true);
    }
    @PostMapping("/{templateId}/finalize")
    public Map<String,Object> finalizeUpload(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID templateId,
        @RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"template:finalize:"+templateId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var row=one(tenantId,templateId,true);version(row,input.expectedVersion());
            Problem.require("UPLOADING".equals(row.get("state")),"Template has already been finalized");
            byte[] bytes=storage.read((String)row.get("upload_key"));
            Problem.require(bytes.length==((Number)row.get("byte_size")).intValue(),"Upload size does not match");validator.validate(bytes);
            String immutable="tenants/"+tenantId+"/templates/"+templateId+"/"+UUID.randomUUID()+".docx";
            storage.put(immutable,bytes,true);
            db.update("UPDATE core.template_versions SET state='VALIDATED',object_key=?,sha256=?,version=version+1 WHERE tenant_id=? AND id=?",immutable,ObjectStorage.checksum(bytes),tenantId,templateId);
            commands.audit(tenantId,null,actor,"TEMPLATE_VALIDATED",Map.of("templateId",templateId,"sha256",ObjectStorage.checksum(bytes)));
            return output(one(tenantId,templateId,false));
        });
    }
    @PostMapping("/{templateId}/publish")
    public Map<String,Object> publish(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID tenantId,@PathVariable UUID templateId,
        @RequestHeader("Idempotency-Key") String key,@Valid @RequestBody VersionInput input) {
        UUID actor=access.identity(jwt);
        return commands.run(tenantId,actor,"template:publish:"+templateId,key,input,()->access.role(tenantId,actor,"ADMIN",true),()->{
            var row=one(tenantId,templateId,true);version(row,input.expectedVersion());
            Problem.require("VALIDATED".equals(row.get("state")),"Validate a template before publishing");
            db.update("UPDATE core.template_versions SET state='PUBLISHED',version=version+1 WHERE tenant_id=? AND id=?",tenantId,templateId);
            commands.audit(tenantId,null,actor,"TEMPLATE_PUBLISHED",Map.of("templateId",templateId));
            return output(one(tenantId,templateId,false));
        });
    }
}
