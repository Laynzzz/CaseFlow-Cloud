package dev.caseflow.cases;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class CaseQueries {
    private final JdbcTemplate db; private final Json json; private final Access access;
    public CaseQueries(JdbcTemplate db,Json json,Access access) { this.db=db;this.json=json;this.access=access; }
    private Map<String,Object> row(ResultSet rs) throws SQLException {
        var out=new LinkedHashMap<String,Object>();
        out.put("id",rs.getObject("id")); out.put("ownerId",rs.getObject("owner_id")); out.put("state",rs.getString("state"));
        out.put("purchase",json.object(rs.getString("purchase"))); out.put("workflowId",rs.getObject("workflow_id"));
        out.put("templateId",rs.getObject("template_id"));
        out.put("originalCaseId",rs.getObject("original_case_id")); out.put("version",rs.getLong("version"));
        out.put("createdAt",rs.getObject("created_at",OffsetDateTime.class).toString());
        out.put("updatedAt",rs.getObject("updated_at",OffsetDateTime.class).toString());
        out.put("documentStatus",rs.getString("document_status")); return out;
    }
    public Map<String,Object> one(UUID tenant,UUID id,boolean lock) {
        var rows=db.query("SELECT * FROM core.cases WHERE tenant_id=? AND id=?"+(lock?" FOR UPDATE":""),(rs,n)->row(rs),tenant,id);
        if(rows.isEmpty()) throw Problem.missing(); attachAssignments(tenant,rows); return rows.getFirst();
    }
    private void attachAssignments(UUID tenant,List<Map<String,Object>> rows) {
        if(rows.isEmpty()) return;
        var byId=new HashMap<UUID,List<Map<String,Object>>>();
        var args=new ArrayList<Object>(); args.add(tenant);
        rows.forEach(row->{UUID id=(UUID)row.get("id");args.add(id);byId.put(id,new ArrayList<>());});
        String placeholders=String.join(",",Collections.nCopies(rows.size(),"?"));
        db.query("SELECT a.*,i.display_name FROM core.assignments a JOIN core.identities i ON i.id=a.user_id WHERE a.tenant_id=? AND a.case_id IN ("+placeholders+") ORDER BY a.step",rs->{
            var assignment=new LinkedHashMap<String,Object>();
            assignment.put("step",rs.getInt("step")); assignment.put("userId",rs.getObject("user_id"));
            assignment.put("displayName",rs.getString("display_name"));assignment.put("outcome",rs.getString("outcome"));
            byId.get(rs.getObject("case_id",UUID.class)).add(assignment);
        },args.toArray());
        rows.forEach(row->row.put("assignments",byId.get(row.get("id"))));
    }
    public static Object[] cursor(String cursor) {
        try {
            String[] parts=new String(Base64.getUrlDecoder().decode(cursor),StandardCharsets.UTF_8).split("\\|",-1);
            if(parts.length!=2) throw new IllegalArgumentException();
            return new Object[]{OffsetDateTime.parse(parts[0]),UUID.fromString(parts[1])};
        } catch(RuntimeException e) { throw new Problem(400,"Invalid pagination cursor"); }
    }
    public static String cursorFor(Map<String,Object> row) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString((row.get("createdAt")+"|"+row.get("id")).getBytes(StandardCharsets.UTF_8));
    }
    public Map<String,Object> list(UUID tenant,UUID actor,String state,boolean assigned,String cursor,int limit) {
        Problem.require(limit>=1 && limit<=100,"Limit must be 1 to 100");
        if(state!=null) Problem.require(Set.of("DRAFT","ACTIVE","APPROVED","REJECTED","CANCELLED").contains(state),"Invalid state");
        var roles=access.member(tenant,actor,false);
        var args=new ArrayList<Object>(List.of(tenant,roles.contains("ADMIN")||roles.contains("AUDITOR"),actor,actor));
        var sql=new StringBuilder("""
                SELECT c.* FROM core.cases c WHERE c.tenant_id=? AND (? OR c.owner_id=?
                OR EXISTS(SELECT 1 FROM core.assignments a WHERE a.tenant_id=c.tenant_id AND a.case_id=c.id AND a.user_id=?))
                """);
        if(state!=null) {sql.append(" AND c.state=?");args.add(state);}
        if(assigned) {sql.append(" AND c.state='ACTIVE' AND EXISTS(SELECT 1 FROM core.assignments a WHERE a.tenant_id=c.tenant_id AND a.case_id=c.id AND a.user_id=? AND a.outcome IS NULL)");args.add(actor);}
        if(cursor!=null) {sql.append(" AND (c.created_at,c.id) < (?,?)");args.addAll(Arrays.asList(cursor(cursor)));}
        sql.append(" ORDER BY c.created_at DESC,c.id DESC LIMIT ?"); args.add(limit+1);
        var rows=db.query(sql.toString(),(rs,n)->row(rs),args.toArray());
        String next=rows.size()>limit?cursorFor(rows.get(limit-1)):null;
        if(rows.size()>limit) rows=new ArrayList<>(rows.subList(0,limit));
        attachAssignments(tenant,rows);
        var page=new LinkedHashMap<String,Object>();page.put("items",rows);page.put("nextCursor",next);return page;
    }
    public Map<String,Object> audit(UUID tenant,UUID actor,UUID id,String cursor,int limit) {
        access.caseVisible(tenant,actor,id,false);Problem.require(limit>=1&&limit<=100,"Invalid limit");
        var args=new ArrayList<Object>(List.of(tenant,id));
        String suffix="";
        if(cursor!=null){suffix=" AND (created_at,id) < (?,?)";args.addAll(Arrays.asList(cursor(cursor)));} args.add(limit+1);
        var rows=db.query("SELECT * FROM core.audit WHERE tenant_id=? AND case_id=?"+suffix+" ORDER BY created_at DESC,id DESC LIMIT ?",(rs,n)->{
            Map<String,Object> event=new LinkedHashMap<>();event.put("id",rs.getObject("id"));event.put("actorId",rs.getObject("actor_id"));event.put("eventType",rs.getString("event_type"));event.put("details",json.object(rs.getString("details")));event.put("createdAt",rs.getObject("created_at",OffsetDateTime.class).toString());return event;
        },args.toArray());
        var result=new LinkedHashMap<String,Object>();result.put("nextCursor",rows.size()>limit?cursorFor(rows.get(limit-1)):null);result.put("items",rows.subList(0,Math.min(limit,rows.size())));return result;
    }
}
