package dev.caseflow.evidence;

import dev.caseflow.common.*;
import dev.caseflow.identity.Access;
import java.nio.file.*;
import java.sql.DriverManager;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;
import static org.junit.jupiter.api.Assertions.*;

/** Real disposable SQL database; synthetic model fixture, never the running demo. */
@EnabledIfEnvironmentVariable(named="DB_ADMIN_PASSWORD",matches=".+")
class AssistantIntegrationTest {
    String databaseName;JdbcTemplate admin,db;TransactionTemplate tx;AssistantController controller;
    UUID tenant,caseId,jobId,actor;Jwt jwt;Json json;
    @BeforeEach void setup() throws Exception {
        databaseName="caseflow_test_"+UUID.randomUUID().toString().replace("-","");
        try(var connection=DriverManager.getConnection("jdbc:postgresql://127.0.0.1:54320/caseflow","caseflow_admin",System.getenv("DB_ADMIN_PASSWORD"))) {
            connection.createStatement().execute("CREATE DATABASE "+databaseName+" OWNER caseflow_migrator");
        }
        admin=new JdbcTemplate(new DriverManagerDataSource("jdbc:postgresql://127.0.0.1:54320/"+databaseName,"caseflow_migrator",System.getenv("DB_MIGRATOR_PASSWORD")));
        try(var files=Files.list(Path.of("../../db/migrations"))) {
            for(var path:files.filter(p->p.getFileName().toString().matches("V\\d+__.*\\.sql")).sorted(Comparator.comparingInt(p->Integer.parseInt(p.getFileName().toString().split("__")[0].substring(1)))).toList())admin.execute(Files.readString(path));
        }
        var dataSource=new DriverManagerDataSource("jdbc:postgresql://127.0.0.1:54320/"+databaseName,"caseflow_api",System.getenv("DB_API_PASSWORD"));
        db=new JdbcTemplate(dataSource);tx=new TransactionTemplate(new JdbcTransactionManager(dataSource));
        json=new Json(JsonMapper.builder().build());var access=new Access(db);var commands=new Commands(db,json);
        controller=new AssistantController(db,access,commands,json,jakarta.validation.Validation.buildDefaultValidatorFactory().getValidator());
        jwt=Jwt.withTokenValue("synthetic-not-a-real-token").header("alg","none").issuer("https://synthetic-tests.invalid").subject(UUID.randomUUID().toString()).claim("preferred_username","Synthetic requester").build();
        actor=access.identity(jwt);tenant=UUID.randomUUID();caseId=UUID.randomUUID();jobId=UUID.randomUUID();
        admin.update("INSERT INTO core.tenants(id,name) VALUES (?,'Isolated assistant test')",tenant);
        admin.update("INSERT INTO core.memberships(tenant_id,user_id,roles) VALUES (?,?,ARRAY['REQUESTER'])",tenant,actor);
        var purchase=Map.of("vendor","Original vendor","description","Equipment","currency","USD","costCenter","OPS","justification","Synthetic testing","lineItems",List.of(Map.of("description","Equipment","quantity","2","unitPrice","2100.00")),"total","4200.00");
        admin.update("INSERT INTO core.cases(tenant_id,id,owner_id,purchase) VALUES (?,?,?,?::jsonb)",tenant,caseId,actor,json.write(purchase));
        var input=Map.of("revision",0,"purchase",purchase,"policyIds",List.of());String hash=json.hash(input);
        admin.update("INSERT INTO core.job_requests(tenant_id,job_id,case_id,kind,input,input_hash,requested_by,status) VALUES (?,?,?,'EXTRACTION',?::jsonb,?,?,'SUCCEEDED')",tenant,jobId,caseId,json.write(input),hash,actor);
        admin.update("INSERT INTO worker.jobs(tenant_id,job_id,case_id,kind,attempt,input_hash,status,fence) VALUES (?,?,?,'EXTRACTION',1,?,'SUCCEEDED',1)",tenant,jobId,caseId,hash);
        var quote=List.of(Map.of("chunkId","synthetic-citation","quote","Synthetic Tools"));
        var suggestion=Map.of("vendor",Map.of("value","Synthetic Tools","citations",quote),"currency",Map.of("value","USD","citations",quote),"lineItems",Map.of("value",List.of(Map.of("description","Equipment","quantity","2","unitPrice","2100")),"citations",quote),"total",Map.of("value","4200","citations",quote),"warnings",List.of());
        admin.update("INSERT INTO worker.ai_results(tenant_id,job_id,attempt,fence,result) VALUES (?,?,1,1,?::jsonb)",tenant,jobId,json.write(Map.of("output",suggestion)));
    }
    @AfterEach void cleanup() throws Exception {
        if(databaseName!=null) {
            assertTrue(databaseName.matches("caseflow_test_[a-f0-9]{32}"));
            try(var connection=DriverManager.getConnection("jdbc:postgresql://127.0.0.1:54320/caseflow","caseflow_admin",System.getenv("DB_ADMIN_PASSWORD"))) {
                connection.createStatement().execute("DROP DATABASE "+databaseName+" WITH (FORCE)");
            }
        }
    }
    @Test void acceptsOnlySelectedFieldsAndReplaysWithoutAnotherMutation() {
        var body=new AssistantController.AcceptInput(0L,Set.of("vendor"));String key=UUID.randomUUID().toString();
        var first=tx.execute(t->controller.accept(jwt,tenant,caseId,jobId,key,body));
        var second=tx.execute(t->controller.accept(jwt,tenant,caseId,jobId,key,body));
        assertEquals(json.hash(first),json.hash(second));
        var purchase=json.object(db.queryForObject("SELECT purchase::text FROM core.cases WHERE id=?",String.class,caseId));
        assertEquals("Synthetic Tools",purchase.get("vendor"));assertEquals("OPS",purchase.get("costCenter"));assertEquals("4200.00",purchase.get("total"));
        assertEquals(1L,db.queryForObject("SELECT version FROM core.cases WHERE id=?",Long.class,caseId));
        assertEquals(1,db.queryForObject("SELECT count(*) FROM core.audit WHERE event_type='AI_SUGGESTIONS_ACCEPTED'",Integer.class));
        var stale=assertThrows(Problem.class,()->tx.execute(t->controller.accept(jwt,tenant,caseId,jobId,UUID.randomUUID().toString(),new AssistantController.AcceptInput(1L,Set.of("currency")))));
        assertEquals(409,stale.status);
    }
    @Test void comparisonIsPinnedAndDeduplicatedSeparatelyFromOrdinaryReview() {
        assertFalse(json.convert(Map.of("kind","REVIEW","expectedVersion",0),AssistantController.RunInput.class).compareRetrieval());
        admin.update("UPDATE core.cases SET policies_initialized=true WHERE id=?",caseId);
        admin.update("UPDATE worker.ai_budget SET total_limit_usd=1,tenant_daily_limit_usd=1");
        var ordinary=tx.execute(t->controller.run(jwt,tenant,caseId,UUID.randomUUID().toString(),new AssistantController.RunInput(AssistantController.Kind.REVIEW,0L,null)));
        var compared=tx.execute(t->controller.run(jwt,tenant,caseId,UUID.randomUUID().toString(),new AssistantController.RunInput(AssistantController.Kind.REVIEW,0L,null,true)));
        var repeated=tx.execute(t->controller.run(jwt,tenant,caseId,UUID.randomUUID().toString(),new AssistantController.RunInput(AssistantController.Kind.REVIEW,0L,null,true)));
        assertNotEquals(ordinary.get("jobId"),compared.get("jobId"));
        assertEquals(compared.get("jobId"),repeated.get("jobId"));
        assertEquals("true",db.queryForObject("SELECT input->>'compareRetrieval' FROM core.job_requests WHERE job_id=?",String.class,compared.get("jobId")));
        assertEquals(400,assertThrows(Problem.class,()->tx.execute(t->controller.run(jwt,tenant,caseId,UUID.randomUUID().toString(),new AssistantController.RunInput(AssistantController.Kind.EXTRACTION,0L,null,true)))).status);
    }
    @Test void rejectsUnsupportedFieldsAndRevokedMembership() {
        assertEquals(400,assertThrows(Problem.class,()->tx.execute(t->controller.accept(jwt,tenant,caseId,jobId,UUID.randomUUID().toString(),new AssistantController.AcceptInput(0L,Set.of("total"))))).status);
        admin.update("UPDATE core.memberships SET active=false WHERE tenant_id=? AND user_id=?",tenant,actor);
        assertEquals(404,assertThrows(Problem.class,()->tx.execute(t->controller.accept(jwt,tenant,caseId,jobId,UUID.randomUUID().toString(),new AssistantController.AcceptInput(0L,Set.of("vendor"))))).status);
        assertEquals(0L,db.queryForObject("SELECT version FROM core.cases WHERE id=?",Long.class,caseId));
    }
    @Test void refusesNewJobsWhenBudgetDisabled() {
        var problem=assertThrows(Problem.class,()->tx.execute(t->controller.run(jwt,tenant,caseId,UUID.randomUUID().toString(),new AssistantController.RunInput(AssistantController.Kind.REVIEW,0L,null))));
        assertEquals(503,problem.status);
        assertEquals(0,db.queryForObject("SELECT count(*) FROM core.outbox",Integer.class));
    }
}
