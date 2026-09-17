package dev.caseflow.cases;

import dev.caseflow.common.Problem;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import java.sql.SQLException;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import static dev.caseflow.cases.CaseQueryFixture.*;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named="DB_ADMIN_PASSWORD",matches=".+")
class CaseQueriesIntegrationTest {
    CaseQueryFixture f;
    final UUID a=new UUID(0,1),b=new UUID(0,2),c=new UUID(0,3),d=new UUID(0,4);
    @BeforeEach void setup() throws Exception {
        f=new CaseQueryFixture(false);
        f.insert(f.tenant,a,f.owner,"DRAFT","2026-01-01T00:00:00Z");
        f.insert(f.tenant,b,f.other,"ACTIVE","2026-01-02T00:00:00Z");
        f.insert(f.tenant,c,f.other,"CANCELLED","2026-01-03T00:00:00Z");
        f.insert(f.tenant,d,f.owner,"ACTIVE","2026-01-04T00:00:00Z");
        f.insert(f.small,d,f.other,"ACTIVE","2026-01-05T00:00:00Z");
        f.insert(f.small,a,f.other,"ACTIVE","2025-01-05T00:00:00Z");
        f.assign(f.tenant,b,0,f.approver,true); f.assign(f.tenant,b,1,f.approver,false);
        f.assign(f.tenant,c,0,f.approver,true);
        f.assign(f.tenant,d,0,f.approver,false);f.assign(f.small,d,0,f.other,false);
        f.assign(f.small,a,0,f.approver,false);
    }
    @AfterEach void cleanup() throws Exception { if(f!=null) f.close(); }
    @Test void permissionAndTenantFiltersRetainExactlyVisibleCases() {
        assertEquals(List.of(d,a),ids(f.queries.list(f.tenant,f.owner,null,false,null,100)));
        assertEquals(List.of(d,c,b),ids(f.queries.list(f.tenant,f.approver,null,false,null,100)));
        assertEquals(List.of(d,c,b,a),ids(f.queries.list(f.tenant,f.manager,null,false,null,100)));
        assertEquals(List.of(d,c,b,a),ids(f.queries.list(f.tenant,f.auditor,null,false,null,100)));
        assertEquals(List.of(d,a),ids(f.queries.list(f.small,f.manager,null,false,null,100)));
    }
    @Test void assignedAndStateFiltersDoNotDuplicateOrLeakRows() {
        var page=f.queries.list(f.tenant,f.approver,"ACTIVE",true,null,100);
        assertEquals(List.of(d,b),ids(page));
        @SuppressWarnings("unchecked") var assignments=(List<Map<String,Object>>)rows(page).getFirst().get("assignments");
        assertEquals(1,assignments.size());assertEquals(f.approver,assignments.getFirst().get("userId"));
        assertEquals(2,((List<?>)rows(page).get(1).get("assignments")).size());
        assertEquals(List.of(),ids(f.queries.list(f.tenant,f.approver,"CANCELLED",true,null,100)));
        assertEquals(List.of(d),ids(f.queries.list(f.tenant,f.owner,"ACTIVE",false,null,100)));
    }
    @Test void keysetPaginationHandlesEqualTimestampsAndNewerInserts() {
        f.admin.update("UPDATE core.cases SET created_at='2026-01-01T00:00:00Z' WHERE tenant_id=?",f.tenant);
        var first=f.queries.list(f.tenant,f.manager,null,false,null,2);
        assertEquals(List.of(d,c),ids(first));
        f.insert(f.tenant,new UUID(0,5),f.owner,"DRAFT","2026-01-02T00:00:00Z");
        var second=f.queries.list(f.tenant,f.manager,null,false,(String)first.get("nextCursor"),2);
        assertEquals(List.of(b,a),ids(second));assertNull(second.get("nextCursor"));
    }
    @Test void assignmentsAreBatchedInsteadOfOneQueryPerCase() {
        for(int limit:List.of(1,4)) {
            f.db.calls=0;
            var page=f.queries.list(f.tenant,f.manager,null,false,null,limit);
            assertEquals(limit,rows(page).size());
            assertEquals(3,f.db.calls,"membership, cases and a single assignment query");
        }
    }
    @Test void deactivatedOrForeignMembershipAndInvalidCursorsAreRejected() {
        f.admin.update("UPDATE core.memberships SET active=false WHERE tenant_id=? AND user_id=?",f.tenant,f.owner);
        assertEquals(404,assertThrows(Problem.class,()->f.queries.list(f.tenant,f.owner,null,false,null,25)).status);
        assertEquals(404,assertThrows(Problem.class,()->f.queries.list(UUID.randomUUID(),f.manager,null,false,null,25)).status);
        assertEquals(400,assertThrows(Problem.class,()->f.queries.list(f.tenant,f.manager,null,false,"broken",25)).status);
    }
    @Test void singleCaseLookupUsesBothTenantAndCaseIdAndReturnsAssignments() {
        var large=f.queries.one(f.tenant,d,false);var small=f.queries.one(f.small,d,false);
        assertEquals(f.owner,large.get("ownerId"));assertEquals(f.other,small.get("ownerId"));
        @SuppressWarnings("unchecked") var assignments=(List<Map<String,Object>>)large.get("assignments");
        assertEquals(f.approver,assignments.getFirst().get("userId"));
        assertEquals(404,assertThrows(Problem.class,()->f.queries.one(f.small,b,false)).status);
    }
    @Test void lockedLookupPreventsAnotherTransactionFromLockingTheSameCaseUntilCommit() {
        var transaction=new TransactionTemplate(new DataSourceTransactionManager(f.pool));
        transaction.executeWithoutResult(status->{
            assertEquals(d,f.queries.one(f.tenant,d,true).get("id"));
            var blocked=assertThrows(DataAccessException.class,()->f.admin.queryForObject(
                    "SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE NOWAIT",UUID.class,f.tenant,d));
            assertEquals("55P03",assertInstanceOf(SQLException.class,blocked.getMostSpecificCause()).getSQLState());
            assertEquals(d,f.admin.queryForObject(
                    "SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE NOWAIT",UUID.class,f.small,d));
        });
        assertEquals(d,f.admin.queryForObject(
                "SELECT id FROM core.cases WHERE tenant_id=? AND id=? FOR UPDATE NOWAIT",UUID.class,f.tenant,d));
    }
    @Test void listAndAuditRejectOutOfBoundsLimitsInsteadOfReturningUnboundedData() {
        for(int limit:List.of(0,101)) {
            assertEquals(400,assertThrows(Problem.class,()->f.queries.list(f.tenant,f.owner,null,false,null,limit)).status);
            assertEquals(400,assertThrows(Problem.class,()->f.queries.audit(f.tenant,f.owner,d,null,limit)).status);
        }
    }
    @Test void auditPaginationPreservesTieOrderAndExcludesOtherTenantAndCaseEvents() {
        UUID first=new UUID(1,1),second=new UUID(1,2),third=new UUID(1,3);
        for(UUID event:List.of(first,second,third))audit(f.tenant,d,event,"2026-02-01T00:00:00Z");
        audit(f.small,d,new UUID(1,4),"2026-03-01T00:00:00Z");
        audit(f.tenant,a,new UUID(1,5),"2026-03-01T00:00:00Z");
        var page=f.queries.audit(f.tenant,f.owner,d,null,2);
        assertEquals(List.of(third,second),ids(page));
        assertEquals(f.owner,rows(page).getFirst().get("actorId"));
        assertEquals("SYNTHETIC_REVIEW",rows(page).getFirst().get("eventType"));
        assertEquals(Map.of("synthetic",true),rows(page).getFirst().get("details"));
        audit(f.tenant,d,new UUID(1,6),"2026-04-01T00:00:00Z");
        var next=f.queries.audit(f.tenant,f.owner,d,(String)page.get("nextCursor"),2);
        assertEquals(List.of(first),ids(next));assertNull(next.get("nextCursor"));
    }
    @Test void emptyAuditAndUnauthorizedAuditHaveDistinctAuthorizedBehaviors() {
        var empty=f.queries.audit(f.tenant,f.owner,a,null,1);
        assertEquals(List.of(),rows(empty));assertNull(empty.get("nextCursor"));
        assertEquals(404,assertThrows(Problem.class,()->f.queries.audit(f.tenant,f.other,d,null,25)).status);
        f.admin.update("UPDATE core.memberships SET active=false WHERE tenant_id=? AND user_id=?",f.tenant,f.owner);
        assertEquals(404,assertThrows(Problem.class,()->f.queries.audit(f.tenant,f.owner,d,null,25)).status);
    }
    private void audit(UUID tenant,UUID caseId,UUID event,String createdAt) {
        f.admin.update("INSERT INTO core.audit(id,tenant_id,case_id,actor_id,event_type,details,created_at) VALUES (?,?,?,?,'SYNTHETIC_REVIEW','{\"synthetic\":true}',?::timestamptz)",
                event,tenant,caseId,f.owner,createdAt);
    }
}
