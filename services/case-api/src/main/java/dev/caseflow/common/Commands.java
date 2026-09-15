package dev.caseflow.common;

import java.util.*;
import java.util.function.Supplier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class Commands {
    private final JdbcTemplate db;
    private final Json json;
    public Commands(JdbcTemplate db, Json json) { this.db = db; this.json = json; }
    @Transactional
    public Map<String,Object> run(UUID tenant, UUID actor, String operation, String key,
            Object request, Runnable authorize, Supplier<Map<String,Object>> action) {
        Problem.require(key != null && key.length() >= 8 && key.length() <= 128,
                "Idempotency-Key must contain 8 to 128 characters");
        authorize.run();
        String scope = tenant + ":" + actor + ":" + operation + ":" + key;
        boolean locked = Boolean.TRUE.equals(db.queryForObject(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(?, 0))", Boolean.class, scope));
        if (!locked) throw new Problem(409, "This command is in progress. Retry with the same key.", true);
        db.update("DELETE FROM core.command_records WHERE tenant_id=? AND actor_id=? AND operation=? AND key=? AND expires_at < now()",
                tenant, actor, operation, key);
        String hash = json.hash(request);
        var receipts = db.queryForList("SELECT request_hash,response::text FROM core.command_records WHERE tenant_id=? AND actor_id=? AND operation=? AND key=?",
                tenant, actor, operation, key);
        if (!receipts.isEmpty()) {
            var receipt = receipts.getFirst();
            if (!hash.equals(receipt.get("request_hash"))) throw new Problem(409, "Idempotency key was used for a different request");
            return json.object((String) receipt.get("response"));
        }
        var result = action.get();
        db.update("INSERT INTO core.command_records(tenant_id,actor_id,operation,key,request_hash,response) VALUES (?,?,?,?,?,?::jsonb)",
                tenant, actor, operation, key, hash, json.write(result));
        return result;
    }
    public void audit(UUID tenant, UUID caseId, UUID actor, String type, Object details) {
        db.update("INSERT INTO core.audit(id,tenant_id,case_id,actor_id,event_type,details) VALUES (?,?,?,?,?,?::jsonb)",
                UUID.randomUUID(), tenant, caseId, actor, type, json.write(details));
    }
}
