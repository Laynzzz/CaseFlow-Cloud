package dev.caseflow.cases;

import dev.caseflow.common.Json;
import dev.caseflow.identity.Access;
import com.zaxxer.hikari.HikariDataSource;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.sql.DriverManager;
import java.util.*;
import javax.sql.DataSource;
import org.springframework.jdbc.core.*;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import tools.jackson.databind.json.JsonMapper;

/** Disposable real database; captures executed SQL without replacing its results. */
final class CaseQueryFixture implements AutoCloseable {
    final String name="caseflow_test_"+UUID.randomUUID().toString().replace("-","");
    final JdbcTemplate admin;
    final ProbeJdbc db;
    final HikariDataSource pool;
    final Json json=new Json(JsonMapper.builder().build());
    final CaseQueries queries;
    boolean dropped;
    final UUID tenant=id("large"), small=id("small"), owner=id("owner"), other=id("other"),
            approver=id("approver"), auditor=id("auditor"), manager=id("manager");
    static UUID id(String value) { return UUID.nameUUIDFromBytes(value.getBytes(StandardCharsets.UTF_8)); }
    static String url(String name) { return "jdbc:postgresql://127.0.0.1:54320/"+name; }
    CaseQueryFixture(boolean baseline) throws Exception {
        try(var connection=DriverManager.getConnection(url("caseflow"),"caseflow_admin",System.getenv("DB_ADMIN_PASSWORD"))) {
            connection.createStatement().execute("CREATE DATABASE "+name+" OWNER caseflow_migrator");
        }
        admin=new JdbcTemplate(new DriverManagerDataSource(url(name),"caseflow_migrator",System.getenv("DB_MIGRATOR_PASSWORD")));
        pool=new HikariDataSource();pool.setJdbcUrl(url(name));pool.setUsername("caseflow_api");
        pool.setPassword(System.getenv("DB_API_PASSWORD"));pool.setMaximumPoolSize(2);pool.setMinimumIdle(1);
        pool.setConnectionTimeout(3000);pool.setPoolName("case-query-test");db=new ProbeJdbc(pool);
        admin.setQueryTimeout(60); db.setQueryTimeout(15);
        queries=new CaseQueries(db,json,new Access(db));
        try {
            try(var files=Files.list(Path.of("../../db/migrations"))) {
                for(var path:files.filter(p->p.getFileName().toString().matches("V\\d+__.*\\.sql"))
                        .sorted(Comparator.comparingInt(CaseQueryFixture::version)).toList()) {
                    if(!baseline || version(path)<=12) admin.execute(Files.readString(path));
                }
            }
            for(var pair:Map.of(owner,"REQUESTER",other,"REQUESTER",approver,"APPROVER",auditor,"AUDITOR",manager,"ADMIN").entrySet()) {
                admin.update("INSERT INTO core.identities(id,issuer,subject,display_name) VALUES (?,'https://synthetic-query.invalid',?,'Synthetic member')",pair.getKey(),pair.getKey().toString());
            }
            for(UUID t:List.of(tenant,small)) {
                admin.update("INSERT INTO core.tenants(id,name) VALUES (?,'Synthetic query tenant')",t);
                for(var pair:Map.of(owner,"REQUESTER",other,"REQUESTER",approver,"APPROVER",auditor,"AUDITOR",manager,"ADMIN").entrySet())
                    admin.update("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (?,?,ARRAY[?]::text[])",t,pair.getKey(),pair.getValue());
            }
        } catch(Exception error) { close(); throw error; }
    }
    static int version(Path path) { return Integer.parseInt(path.getFileName().toString().split("__")[0].substring(1)); }
    void insert(UUID t,UUID caseId,UUID actor,String state,String time) {
        admin.update("INSERT INTO core.cases(tenant_id,id,owner_id,state,purchase,created_at) VALUES (?,?,?,?,'{}',?::timestamptz)",t,caseId,actor,state,time);
    }
    void assign(UUID t,UUID caseId,int step,UUID actor,boolean done) {
        admin.update("INSERT INTO core.assignments(tenant_id,case_id,step,user_id,outcome,decided_at) VALUES (?,?,?,?,?,CASE WHEN ? THEN now() ELSE NULL END)",
                t,caseId,step,actor,done?"APPROVED":null,done);
    }
    @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> page) { return (List<Map<String,Object>>)page.get("items"); }
    static List<UUID> ids(Map<String,Object> page) { return rows(page).stream().map(r->(UUID)r.get("id")).toList(); }
    @Override public void close() throws Exception {
        pool.close();
        if(!name.matches("caseflow_test_[a-f0-9]{32}")) throw new IllegalStateException("Unsafe database name");
        try(var connection=DriverManager.getConnection(url("caseflow"),"caseflow_admin",System.getenv("DB_ADMIN_PASSWORD"))) {
            connection.createStatement().execute("DROP DATABASE "+name+" WITH (FORCE)");
            dropped=true;
        }
    }
    static final class ProbeJdbc extends JdbcTemplate {
        int calls; String caseSql; Object[] caseArgs;
        ProbeJdbc(DataSource source) { super(source); }
        @Override public <T> List<T> query(String sql,RowMapper<T> mapper,Object... args) {
            calls++;
            if(sql.stripLeading().startsWith("SELECT c.* FROM core.cases")) { caseSql=sql;caseArgs=args.clone(); }
            return super.query(sql,mapper,args);
        }
        @Override public void query(String sql,RowCallbackHandler callback,Object... args) {
            calls++;super.query(sql,callback,args);
        }
    }
}
