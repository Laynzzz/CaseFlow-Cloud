import { useEffect, useState } from "react";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { auth, initializeAuth } from "./auth";
import { api, unwrap } from "./api/client";
import { Notice, Empty } from "./components";
import { WorkQueue } from "./pages/WorkQueue";
import { DraftForm } from "./pages/DraftForm";
import { CaseDetail } from "./pages/CaseDetail";
import { Administration } from "./pages/Administration";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 10000, refetchOnWindowFocus: true },
  },
});
function FocusOnNavigation() {
  const location = useLocation();
  useEffect(() => {
    document.getElementById("workspace")?.focus();
  }, [location.pathname]);
  return null;
}
function Workspace() {
  const navigate = useNavigate(),
    cache = useQueryClient();
  const location = useLocation();
  const [selected, setSelected] = useState(""),
    [tenantName, setTenantName] = useState(""),
    [creating, setCreating] = useState(false),
    [error, setError] = useState<unknown>();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => unwrap(api.GET("/api/v1/me")),
  });
  const membership =
    me.data?.memberships.find((t) => t.id === selected) ??
    me.data?.memberships[0];
  const tenant = membership?.id;
  async function createOrganization(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(undefined);
    try {
      const result = await unwrap(
        api.POST("/api/v1/tenants", { body: { name: tenantName } }),
      );
      setSelected(result.id);
      setTenantName("");
      await cache.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    } catch (e) {
      setError(e);
    } finally {
      setCreating(false);
    }
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to content
      </a>
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          CaseFlow<span>Cloud</span>
        </NavLink>
        <label className="tenant-picker">
          Organization
          <select
            value={tenant ?? ""}
            onChange={(e) => {
              setSelected(e.target.value);
              navigate("/");
            }}
          >
            <option value="" disabled>
              Select organization
            </option>
            {me.data?.memberships.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            Purchase requests
          </NavLink>
          {membership?.roles.includes("REQUESTER") && (
            <NavLink to="/new">New request</NavLink>
          )}
          {membership?.roles.includes("ADMIN") && (
            <NavLink to="/admin">Administration</NavLink>
          )}
          <NavLink to="/account">My account</NavLink>
        </nav>
        <div className="sidebar-footer">
          <strong>{me.data?.displayName ?? "Signed in"}</strong>
          <span>{membership?.roles.join(" · ").toLowerCase()}</span>
          <button
            className="secondary"
            onClick={() => {
              cache.clear();
              void auth.logout({ redirectUri: window.location.origin + "/" });
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main id="workspace" className="workspace" tabIndex={-1}>
        <FocusOnNavigation />
        <Notice error={me.error} />
        {me.error && (
          <button onClick={() => void me.refetch()}>Try again</button>
        )}
        {me.isPending ? (
          <Empty>Loading your organizations…</Empty>
        ) : (
          <Routes>
            <Route
              path="/account"
              element={
                <>
                  <div className="page-title">
                    <h1>My account</h1>
                  </div>
                  <section className="panel">
                    <h2>{me.data?.displayName}</h2>
                    <p>
                      Share this member ID with your organization administrator
                      after you have signed in.
                    </p>
                    <code className="member-id">{me.data?.id}</code>
                  </section>
                  <section className="panel">
                    <h2>Create an organization</h2>
                    <Notice error={error} />
                    <form onSubmit={createOrganization}>
                      <label>
                        Organization name
                        <input
                          required
                          maxLength={120}
                          value={tenantName}
                          onChange={(e) => setTenantName(e.target.value)}
                        />
                      </label>
                      <button disabled={creating}>
                        {creating ? "Creating…" : "Create organization"}
                      </button>
                    </form>
                  </section>
                </>
              }
            />
            {tenant && membership ? (
              <>
                <Route
                  path="/"
                  element={
                    <WorkQueue
                      key={tenant}
                      tenant={tenant}
                      canRequest={membership.roles.includes("REQUESTER")}
                    />
                  }
                />
                <Route
                  path="/new"
                  element={
                    membership.roles.includes("REQUESTER") ? (
                      <>
                        <div className="page-title">
                          <div>
                            <p className="eyebrow">Start a purchase</p>
                            <h1>New request</h1>
                          </div>
                        </div>
                        <DraftForm key={tenant} tenant={tenant} />
                      </>
                    ) : (
                      <Empty>
                        Your current role cannot submit purchase requests.
                      </Empty>
                    )
                  }
                />
                <Route
                  path="/cases/:caseId"
                  element={
                    <CaseDetail
                      key={`${tenant}:${location.pathname}`}
                      tenant={tenant}
                      userId={me.data!.id}
                      roles={membership.roles}
                    />
                  }
                />
                <Route
                  path="/admin"
                  element={
                    membership.roles.includes("ADMIN") ? (
                      <Administration key={tenant} tenant={tenant} />
                    ) : (
                      <Empty>Administrator access is required.</Empty>
                    )
                  }
                />
              </>
            ) : (
              <Route
                path="*"
                element={
                  <section className="panel">
                    <h1>Welcome to CaseFlow</h1>
                    <p>
                      You do not have an active organization membership yet.
                      Create an organization or share your member ID with an
                      administrator.
                    </p>
                    <NavLink className="button" to="/account">
                      Open my account
                    </NavLink>
                  </section>
                }
              />
            )}
            {tenant && (
              <Route
                path="*"
                element={
                  <Empty>
                    This page could not be found. Use the navigation to return
                    to your requests.
                  </Empty>
                }
              />
            )}
          </Routes>
        )}
        <footer>Development build · Synthetic demonstration data</footer>
      </main>
    </div>
  );
}
function AuthGate() {
  const [state, setState] = useState<
    "loading" | "ready" | "signedOut" | "failed"
  >("loading");
  useEffect(() => {
    let active = true;
    void initializeAuth()
      .then((ok) => {
        if (active) setState(ok ? "ready" : "signedOut");
      })
      .catch(() => {
        if (active) setState("failed");
      });
    auth.onAuthLogout = () => {
      queryClient.clear();
      setState("signedOut");
    };
    auth.onTokenExpired = () => {
      void auth.updateToken(30).catch(() => {
        queryClient.clear();
        setState("signedOut");
      });
    };
    return () => {
      active = false;
    };
  }, []);
  if (state === "ready")
    return (
      <BrowserRouter>
        <Workspace />
      </BrowserRouter>
    );
  return (
    <main className="welcome">
      <header>
        <span className="brand">
          CaseFlow<span>Cloud</span>
        </span>
        <span className="badge">Purchase approvals</span>
      </header>
      <section className="intro">
        <p className="eyebrow">A clear path from request to approval</p>
        <h1>
          Every purchase starts
          <br />
          with a clear request.
        </h1>
        <p className="lede">
          Bring purchase details, supporting quotes, and human decisions into
          one place.
        </p>
        {state === "loading" ? (
          <p role="status">Connecting to sign-in…</p>
        ) : state === "failed" ? (
          <>
            <p role="alert">
              Sign-in is currently unavailable. Please try again shortly.
            </p>
            <button onClick={() => window.location.reload()}>Try again</button>
          </>
        ) : (
          <button
            onClick={() =>
              void auth.login({ redirectUri: window.location.origin + "/" })
            }
          >
            Sign in to your workspace
          </button>
        )}
      </section>
      <section className="journey">
        <h2>From request to a recorded decision</h2>
        <ol>
          <li>
            <span className="number">01</span>
            <h3>Make a request</h3>
            <p>Describe the purchase, cost, and business need.</p>
          </li>
          <li>
            <span className="number">02</span>
            <h3>Review in order</h3>
            <p>Assigned reviewers make each approval decision.</p>
          </li>
          <li>
            <span className="number">03</span>
            <h3>Keep the history</h3>
            <p>See the purchase status and the people behind each decision.</p>
          </li>
        </ol>
      </section>
      <footer>
        Development build using synthetic organizations and purchases.
      </footer>
    </main>
  );
}
export function AppShell() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  );
}
