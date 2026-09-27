import { FormEvent, useCallback, useEffect, useState } from "react";

type ApiHealth = { status: "ok" };
type UserMembership = {
  organizationId: string;
  organizationName: string;
  roleCode: string;
  roleName: string;
  permissions: string[];
};
type User = {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  dateJoined: string;
  memberships: UserMembership[];
};
type Organization = { id: string; name: string; created_at: string };
type Customer = {
  id: string;
  name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  created_at: string;
};
type Product = {
  id: string;
  name: string;
  sku: string;
  description: string;
  unit: string;
  sale_price: string;
  cost_price: string;
  created_at: string;
};
type OrganizationMember = {
  id: string;
  user: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
    phone: string;
    isActive: boolean;
  };
  role: OrganizationRole;
  is_active: boolean;
  joined_at: string;
};
type OrganizationRole = {
  id: string;
  code: string;
  name: string;
  is_system: boolean;
  permissions: { code: string; name: string; description: string }[];
};
type LoginResponse = { user: User; csrfToken: string };
type OrganizationSection = "customers" | "products" | "members" | "roles";

const productUnits = [
  { value: "piece", label: "قطعة" },
  { value: "kg", label: "كيلوجرام" },
  { value: "g", label: "جرام" },
  { value: "l", label: "لتر" },
  { value: "m", label: "متر" },
  { value: "box", label: "صندوق" },
  { value: "service", label: "خدمة" },
];

function formatPrice(value: string) {
  return new Intl.NumberFormat("ar-EG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

async function responseError(response: Response) {
  const payload: unknown = await response.json().catch(() => null);
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
  }
  if (payload && typeof payload === "object") {
    const firstError = Object.values(payload).flat()[0];
    if (typeof firstError === "string") return firstError;
  }
  return `تعذر إتمام الطلب (رمز ${response.status}).`;
}

export default function App() {
  const [apiStatus, setApiStatus] = useState<"loading" | "online" | "offline">(
    "loading",
  );
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState("");
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [isAccountView, setIsAccountView] = useState(false);
  const [organizationSection, setOrganizationSection] =
    useState<OrganizationSection>("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [organizationMembers, setOrganizationMembers] = useState<OrganizationMember[]>([]);
  const [organizationRoles, setOrganizationRoles] = useState<OrganizationRole[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadOrganizations = useCallback(async () => {
    const response = await fetch("/api/v1/organizations/");
    if (!response.ok) throw new Error(await responseError(response));
    const items: Organization[] = await response.json();
    setOrganizations(items);
  }, []);

  const loadCustomers = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/customers/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: Customer[] = await response.json();
    setCustomers(items);
  }, []);

  const loadProducts = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/products/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: Product[] = await response.json();
    setProducts(items);
  }, []);

  const loadOrganizationMembers = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/members/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: OrganizationMember[] = await response.json();
    setOrganizationMembers(items);
  }, []);

  const loadOrganizationRoles = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/roles/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: OrganizationRole[] = await response.json();
    setOrganizationRoles(items);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function initialize() {
      try {
        const [healthResponse, csrfResponse] = await Promise.all([
          fetch("/api/v1/health/", { signal: controller.signal }),
          fetch("/api/v1/auth/csrf/", { signal: controller.signal }),
        ]);
        if (!healthResponse.ok) throw new Error("تعذر الاتصال بخادم النظام.");
        const health: ApiHealth = await healthResponse.json();
        if (health.status !== "ok") throw new Error("حالة خادم النظام غير متوقعة.");
        if (!csrfResponse.ok) throw new Error("تعذر تهيئة جلسة آمنة.");

        const csrf: { csrfToken: string } = await csrfResponse.json();
        setCsrfToken(csrf.csrfToken);
        setApiStatus("online");

        const userResponse = await fetch("/api/v1/auth/me/", {
          signal: controller.signal,
        });
        if (userResponse.ok) {
          const currentUser: User = await userResponse.json();
          setUser(currentUser);
          await loadOrganizations();
        } else if (userResponse.status !== 401 && userResponse.status !== 403) {
          throw new Error(await responseError(userResponse));
        }
      } catch (caught: unknown) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setApiStatus((current) => (current === "loading" ? "offline" : current));
        setError(
          caught instanceof Error
            ? caught.message
            : "حدث خطأ غير متوقع أثناء الاتصال بالخادم.",
        );
      } finally {
        setIsLoading(false);
      }
    }

    void initialize();
    return () => controller.abort();
  }, [loadOrganizations]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/v1/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: LoginResponse = await response.json();
      setUser(result.user);
      setIsAccountView(false);
      setCsrfToken(result.csrfToken);
      await loadOrganizations();
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تسجيل الدخول. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch("/api/v1/organizations/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ name: form.get("name") }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const organization: Organization = await response.json();
      setOrganizations((current) =>
        [...current, organization].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      formElement.reset();
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر إنشاء الشركة. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenCustomers(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      await loadCustomers(organization.id);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("customers");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحميل العملاء. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenProducts(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      await loadProducts(organization.id);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("products");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحميل المنتجات. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenMembers(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      await loadOrganizationMembers(organization.id);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("members");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحميل أعضاء الشركة. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenRoles(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      await loadOrganizationRoles(organization.id);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("roles");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحميل أدوار الشركة. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/v1/auth/me/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          firstName: form.get("firstName"),
          lastName: form.get("lastName"),
          phone: form.get("phone"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const updatedUser: User = await response.json();
      setUser(updatedUser);
      setNotice("تم حفظ بيانات الحساب.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحديث بيانات الحساب. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch("/api/v1/auth/password/change/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          currentPassword: form.get("currentPassword"),
          newPassword: form.get("newPassword"),
          confirmNewPassword: form.get("confirmNewPassword"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      formElement.reset();
      setNotice("تم تغيير كلمة المرور. ما زالت جلستك الحالية مفتوحة.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تغيير كلمة المرور. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/customers/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            name: form.get("name"),
            phone: form.get("phone"),
            email: form.get("email"),
            address: form.get("address"),
            notes: form.get("notes"),
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const customer: Customer = await response.json();
      setCustomers((current) =>
        [...current, customer].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      formElement.reset();
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر إضافة العميل. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/products/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            name: form.get("name"),
            sku: form.get("sku"),
            description: form.get("description"),
            unit: form.get("unit"),
            sale_price: form.get("sale_price") || "0",
            cost_price: form.get("cost_price") || "0",
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const product: Product = await response.json();
      setProducts((current) =>
        [...current, product].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      formElement.reset();
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر إضافة المنتج. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setError("");
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/v1/auth/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setUser(null);
      setOrganizations([]);
      setIsAccountView(false);
      setSelectedOrganizationId(null);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تسجيل الخروج. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const statusLabel = {
    loading: "جارٍ التحقق",
    online: "متصل",
    offline: "غير متصل",
  }[apiStatus];
  const selectedOrganization =
    organizations.find((organization) => organization.id === selectedOrganizationId) ??
    null;
  const selectedOrganizationMembership = user?.memberships.find(
    (membership) => membership.organizationId === selectedOrganizationId,
  );
  const canManageMembers =
    selectedOrganizationMembership?.permissions.includes("users.manage") ?? false;
  const canManageRoles =
    selectedOrganizationMembership?.permissions.includes("roles.manage") ?? false;

  if (isLoading) {
    return (
      <main className="auth-shell">
        <div className="auth-card loading-card">جارٍ تجهيز مساحة العمل...</div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand auth-brand">
            <span className="brand-mark">E</span>
            <span>مساحة العمل</span>
          </div>
          <div className="welcome-kicker">نظام تخطيط موارد المؤسسات</div>
          <h1>تسجيل الدخول</h1>
          <p className="auth-description">
            سجّل الدخول للبدء بإدارة شركاتك وبياناتك.
          </p>
          {error && <div className="alert-error" role="alert">{error}</div>}
          <form className="auth-form" onSubmit={handleLogin}>
            <label htmlFor="email">البريد الإلكتروني</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              placeholder="name@company.com"
              required
              disabled={isSubmitting}
            />
            <label htmlFor="password">كلمة المرور</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              disabled={isSubmitting}
            />
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "جارٍ تسجيل الدخول..." : "دخول آمن"}
            </button>
          </form>
          <div className="auth-footer">
            الخادم: {statusLabel}
            <span className={`status-dot api-${apiStatus}`} />
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">E</span>
          <span>مساحة العمل</span>
        </div>
        <div className="sidebar-label">الرئيسية</div>
        <a className="nav-item nav-item-active" href="#overview">
          <span className="nav-icon">⌂</span>
          نظرة عامة
        </a>
        <div className="sidebar-label">إدارة الأعمال</div>
        <a
          className={`nav-item ${!isAccountView && !selectedOrganization ? "nav-item-active" : ""}`}
          href="#organizations"
          onClick={() => {
            setIsAccountView(false);
            setSelectedOrganizationId(null);
            setCustomers([]);
            setProducts([]);
            setError("");
            setNotice("");
          }}
        >
          <span className="nav-icon">▦</span>
          الشركات
        </a>
        <a
          className={`nav-item ${selectedOrganization && organizationSection === "customers" ? "nav-item-active" : "nav-item-muted"}`}
          href="#organizations"
          onClick={() => {
            if (organizations.length > 0) {
              void handleOpenCustomers(organizations[0]);
            }
          }}
        >
          <span className="nav-icon">◇</span>
          العملاء
        </a>
        <a
          className={`nav-item ${selectedOrganization && organizationSection === "products" ? "nav-item-active" : "nav-item-muted"}`}
          href="#organizations"
          onClick={() => {
            if (organizations.length > 0) {
              void handleOpenProducts(organizations[0]);
            }
          }}
        >
          <span className="nav-icon">▤</span>
          المنتجات
        </a>
        {organizations.some((organization) =>
          user?.memberships.some(
            (membership) =>
              membership.organizationId === organization.id &&
              membership.permissions.includes("users.manage"),
          ),
        ) && (
          <a
            className={`nav-item ${selectedOrganization && organizationSection === "members" ? "nav-item-active" : "nav-item-muted"}`}
            href="#organizations"
            onClick={() => {
              const manageableOrganization = organizations.find((organization) =>
                user?.memberships.some(
                  (membership) =>
                    membership.organizationId === organization.id &&
                    membership.permissions.includes("users.manage"),
                ),
              );
              if (manageableOrganization) void handleOpenMembers(manageableOrganization);
            }}
          >
            <span className="nav-icon">♙</span>
            أعضاء الشركة
          </a>
        )}
        {organizations.some((organization) =>
          user?.memberships.some(
            (membership) =>
              membership.organizationId === organization.id &&
              membership.permissions.includes("roles.manage"),
          ),
        ) && (
          <a
            className={`nav-item ${selectedOrganization && organizationSection === "roles" ? "nav-item-active" : "nav-item-muted"}`}
            href="#organizations"
            onClick={() => {
              const manageableOrganization = organizations.find((organization) =>
                user?.memberships.some(
                  (membership) =>
                    membership.organizationId === organization.id &&
                    membership.permissions.includes("roles.manage"),
                ),
              );
              if (manageableOrganization) void handleOpenRoles(manageableOrganization);
            }}
          >
            <span className="nav-icon">♧</span>
            الأدوار والصلاحيات
          </a>
        )}
        <a
          className={`nav-item ${isAccountView ? "nav-item-active" : "nav-item-muted"}`}
          href="#account"
          onClick={() => {
            setIsAccountView(true);
            setSelectedOrganizationId(null);
            setError("");
            setNotice("");
          }}
        >
          <span className="nav-icon">◉</span>
          حسابي
        </a>
        <div className="sidebar-footer">نسخة تأسيسية · 0.1</div>
      </aside>

      <section className="workspace" id="overview">
        <header className="topbar">
          <div>
            <div className="eyebrow">نظام تخطيط موارد المؤسسات</div>
            <h1>مساحة العمل</h1>
          </div>
          <div className="topbar-actions">
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setIsAccountView(true);
                setSelectedOrganizationId(null);
                setError("");
                setNotice("");
              }}
              disabled={isSubmitting}
            >
              حسابي
            </button>
            <span className={`api-pill api-${apiStatus}`}>
              <span className="status-dot" />
              الخادم: {statusLabel}
            </span>
            <button
              className="text-button"
              type="button"
              onClick={handleLogout}
              disabled={isSubmitting}
            >
              تسجيل الخروج
            </button>
          </div>
        </header>

        {error && <div className="alert-error page-alert" role="alert">{error}</div>}
        {notice && <div className="alert-success page-alert" role="status">{notice}</div>}

        <section className="welcome-card">
          <div className="welcome-copy">
            <div className="welcome-kicker">أهلًا {user.firstName || user.email}</div>
            <h2>مساحة عملك جاهزة لتنظيم أعمالك.</h2>
            <p>أنشئ شركة للبدء. بيانات كل شركة معزولة عن الشركات الأخرى.</p>
          </div>
          <div className="welcome-orbit" aria-hidden="true">
            <span className="orbit-ring orbit-ring-outer" />
            <span className="orbit-ring orbit-ring-inner" />
            <span className="orbit-core">E</span>
          </div>
        </section>

        <section className="organizations-section" id="organizations">
          {isAccountView ? (
            <section className="account-section" id="account">
              <div className="section-heading account-heading">
                <div>
                  <button
                    className="back-button"
                    type="button"
                    onClick={() => {
                      setIsAccountView(false);
                      setError("");
                      setNotice("");
                    }}
                  >
                    ← مساحة العمل
                  </button>
                  <h2>حسابي</h2>
                  <p>بيانات الحساب وعضويات الشركات وإعدادات كلمة المرور.</p>
                </div>
              </div>

              <article className="account-card">
                <div className="account-card-heading">
                  <span className="organization-icon">ح</span>
                  <div>
                    <h3>{user.firstName || user.lastName
                      ? `${user.firstName} ${user.lastName}`.trim()
                      : user.email}</h3>
                    <p>{user.email}</p>
                  </div>
                </div>
                <form
                  className="customer-form account-form"
                  key={`${user.firstName}|${user.lastName}|${user.phone}`}
                  onSubmit={handleUpdateProfile}
                >
                  <div className="customer-form-row">
                    <div className="customer-field">
                      <label htmlFor="profile-first-name">الاسم الأول</label>
                      <input
                        id="profile-first-name"
                        name="firstName"
                        type="text"
                        maxLength={150}
                        defaultValue={user.firstName}
                        autoComplete="given-name"
                        disabled={isSubmitting}
                      />
                    </div>
                    <div className="customer-field">
                      <label htmlFor="profile-last-name">اسم العائلة</label>
                      <input
                        id="profile-last-name"
                        name="lastName"
                        type="text"
                        maxLength={150}
                        defaultValue={user.lastName}
                        autoComplete="family-name"
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>
                  <label htmlFor="profile-email">البريد الإلكتروني</label>
                  <input
                    id="profile-email"
                    type="email"
                    value={user.email}
                    autoComplete="email"
                    readOnly
                  />
                  <label htmlFor="profile-phone">رقم الهاتف</label>
                  <input
                    id="profile-phone"
                    name="phone"
                    type="tel"
                    maxLength={40}
                    defaultValue={user.phone}
                    autoComplete="tel"
                    disabled={isSubmitting}
                  />
                  <button className="primary-button" type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "جارٍ الحفظ..." : "حفظ بيانات الحساب"}
                  </button>
                </form>
                <div className="account-meta">
                  <span>تاريخ إنشاء الحساب</span>
                  <time dateTime={user.dateJoined}>
                    {new Intl.DateTimeFormat("ar-EG", {
                      dateStyle: "medium",
                    }).format(new Date(user.dateJoined))}
                  </time>
                </div>
              </article>

              <div className="section-heading account-subheading">
                <div>
                  <h2>عضويات الشركات</h2>
                  <p>الأدوار والصلاحيات النشطة لحسابك، للعرض فقط.</p>
                </div>
                <span className="count-badge">{user.memberships.length}</span>
              </div>
              {user.memberships.length > 0 ? (
                <div className="membership-list">
                  {user.memberships.map((membership) => (
                    <article
                      className="membership-card"
                      key={membership.organizationId}
                    >
                      <span className="organization-icon">ش</span>
                      <div className="membership-details">
                        <h3>{membership.organizationName}</h3>
                        <p>الدور: {membership.roleName}</p>
                        <div className="permission-tags">
                          {membership.permissions.map((permission) => (
                            <span className="permission-tag" key={permission}>
                              {permission}
                            </span>
                          ))}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">◉</span>
                  <h3>لا توجد عضويات نشطة</h3>
                  <p>أنشئ شركة أو اطلب من مالك الشركة إضافتك.</p>
                </div>
              )}

              <div className="section-heading account-subheading">
                <div>
                  <h2>الأمان</h2>
                  <p>تغيير كلمة المرور يؤمّن الجلسات الأخرى تلقائيًا.</p>
                </div>
              </div>
              <form className="customer-form account-form" onSubmit={handleChangePassword}>
                <label htmlFor="current-password">كلمة المرور الحالية</label>
                <input
                  id="current-password"
                  name="currentPassword"
                  type="password"
                  autoComplete="current-password"
                  required
                  disabled={isSubmitting}
                />
                <div className="customer-form-row">
                  <div className="customer-field">
                    <label htmlFor="new-password">كلمة المرور الجديدة</label>
                    <input
                      id="new-password"
                      name="newPassword"
                      type="password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      disabled={isSubmitting}
                    />
                  </div>
                  <div className="customer-field">
                    <label htmlFor="confirm-new-password">تأكيد كلمة المرور الجديدة</label>
                    <input
                      id="confirm-new-password"
                      name="confirmNewPassword"
                      type="password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      disabled={isSubmitting}
                    />
                  </div>
                </div>
                <p className="field-hint">
                  يجب أن تكون كلمة المرور قوية، وألا تكون شائعة أو مشابهة لبيانات حسابك.
                </p>
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "جارٍ التحديث..." : "تغيير كلمة المرور"}
                </button>
              </form>
            </section>
          ) : selectedOrganization ? (
            <>
              <div className="module-tabs" role="tablist" aria-label="بيانات الشركة">
                <button
                  className={`module-tab ${organizationSection === "customers" ? "module-tab-active" : ""}`}
                  type="button"
                  role="tab"
                  aria-selected={organizationSection === "customers"}
                  onClick={() => void handleOpenCustomers(selectedOrganization)}
                  disabled={isSubmitting}
                >
                  العملاء
                </button>
                <button
                  className={`module-tab ${organizationSection === "products" ? "module-tab-active" : ""}`}
                  type="button"
                  role="tab"
                  aria-selected={organizationSection === "products"}
                  onClick={() => void handleOpenProducts(selectedOrganization)}
                  disabled={isSubmitting}
                >
                  المنتجات
                </button>
                {canManageMembers && (
                  <button
                    className={`module-tab ${organizationSection === "members" ? "module-tab-active" : ""}`}
                    type="button"
                    role="tab"
                    aria-selected={organizationSection === "members"}
                    onClick={() => void handleOpenMembers(selectedOrganization)}
                    disabled={isSubmitting}
                  >
                    الأعضاء
                  </button>
                )}
                {canManageRoles && (
                  <button
                    className={`module-tab ${organizationSection === "roles" ? "module-tab-active" : ""}`}
                    type="button"
                    role="tab"
                    aria-selected={organizationSection === "roles"}
                    onClick={() => void handleOpenRoles(selectedOrganization)}
                    disabled={isSubmitting}
                  >
                    الأدوار والصلاحيات
                  </button>
                )}
              </div>
              {organizationSection === "customers" ? (
                <>
              <div className="section-heading">
                <div>
                  <button
                    className="back-button"
                    type="button"
                    onClick={() => {
                      setSelectedOrganizationId(null);
                      setCustomers([]);
                      setError("");
                    }}
                  >
                    ← الشركات
                  </button>
                  <h2>عملاء {selectedOrganization.name}</h2>
                  <p>قائمة العملاء تخص هذه الشركة فقط.</p>
                </div>
                <span className="count-badge">{customers.length}</span>
              </div>

              <form className="customer-form" onSubmit={handleCreateCustomer}>
                <label htmlFor="customer-name">اسم العميل *</label>
                <input
                  id="customer-name"
                  name="name"
                  type="text"
                  maxLength={160}
                  placeholder="الاسم أو اسم الشركة"
                  required
                  disabled={isSubmitting}
                />
                <div className="customer-form-row">
                  <div className="customer-field">
                    <label htmlFor="customer-phone">رقم الهاتف</label>
                    <input
                      id="customer-phone"
                      name="phone"
                      type="tel"
                      maxLength={40}
                      placeholder="+20..."
                      disabled={isSubmitting}
                    />
                  </div>
                  <div className="customer-field">
                    <label htmlFor="customer-email">البريد الإلكتروني</label>
                    <input
                      id="customer-email"
                      name="email"
                      type="email"
                      maxLength={254}
                      placeholder="name@example.com"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>
                <label htmlFor="customer-address">العنوان</label>
                <input
                  id="customer-address"
                  name="address"
                  type="text"
                  maxLength={500}
                  placeholder="المدينة والعنوان"
                  disabled={isSubmitting}
                />
                <label htmlFor="customer-notes">ملاحظات</label>
                <textarea
                  id="customer-notes"
                  name="notes"
                  maxLength={1000}
                  placeholder="ملاحظات داخلية اختيارية"
                  rows={2}
                  disabled={isSubmitting}
                />
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "جارٍ الحفظ..." : "إضافة العميل"}
                </button>
              </form>

              {customers.length > 0 ? (
                <div className="customer-list">
                  {customers.map((customer) => (
                    <article className="customer-card" key={customer.id}>
                      <span className="organization-icon">ع</span>
                      <div className="customer-card-details">
                        <h3>{customer.name}</h3>
                        <p>
                          {[customer.phone, customer.email]
                            .filter(Boolean)
                            .join(" · ") || "لا توجد بيانات تواصل"}
                        </p>
                        {customer.address && <p>{customer.address}</p>}
                        {customer.notes && (
                          <p className="customer-notes">{customer.notes}</p>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">◇</span>
                  <h3>لسه مافيش عملاء</h3>
                  <p>أضف أول عميل للشركة من النموذج أعلاه.</p>
                </div>
              )}
                </>
              ) : organizationSection === "products" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <button
                        className="back-button"
                        type="button"
                        onClick={() => {
                          setSelectedOrganizationId(null);
                          setProducts([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>منتجات {selectedOrganization.name}</h2>
                      <p>كتالوج الشركة وأسعار المنتجات ووحدات القياس.</p>
                    </div>
                    <span className="count-badge">{products.length}</span>
                  </div>

                  <form className="customer-form" onSubmit={handleCreateProduct}>
                    <label htmlFor="product-name">اسم المنتج *</label>
                    <input
                      id="product-name"
                      name="name"
                      type="text"
                      maxLength={160}
                      placeholder="اسم المنتج أو الخدمة"
                      required
                      disabled={isSubmitting}
                    />
                    <div className="customer-form-row">
                      <div className="customer-field">
                        <label htmlFor="product-sku">رمز المنتج (SKU)</label>
                        <input
                          id="product-sku"
                          name="sku"
                          type="text"
                          maxLength={64}
                          placeholder="مثال: ITEM-001"
                          disabled={isSubmitting}
                        />
                      </div>
                      <div className="customer-field">
                        <label htmlFor="product-unit">وحدة القياس</label>
                        <select
                          id="product-unit"
                          name="unit"
                          defaultValue="piece"
                          disabled={isSubmitting}
                        >
                          {productUnits.map((unit) => (
                            <option key={unit.value} value={unit.value}>
                              {unit.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="customer-form-row">
                      <div className="customer-field">
                        <label htmlFor="product-sale-price">سعر البيع</label>
                        <input
                          id="product-sale-price"
                          name="sale_price"
                          type="number"
                          min="0"
                          max="9999999999.99"
                          step="0.01"
                          inputMode="decimal"
                          defaultValue="0.00"
                          required
                          disabled={isSubmitting}
                        />
                      </div>
                      <div className="customer-field">
                        <label htmlFor="product-cost-price">سعر التكلفة</label>
                        <input
                          id="product-cost-price"
                          name="cost_price"
                          type="number"
                          min="0"
                          max="9999999999.99"
                          step="0.01"
                          inputMode="decimal"
                          defaultValue="0.00"
                          required
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>
                    <label htmlFor="product-description">وصف المنتج</label>
                    <textarea
                      id="product-description"
                      name="description"
                      maxLength={1000}
                      placeholder="وصف اختياري"
                      rows={2}
                      disabled={isSubmitting}
                    />
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? "جارٍ الحفظ..." : "إضافة المنتج"}
                    </button>
                  </form>

                  {products.length > 0 ? (
                    <div className="product-list">
                      {products.map((product) => (
                        <article className="product-card" key={product.id}>
                          <span className="organization-icon">م</span>
                          <div className="product-card-details">
                            <div className="product-title-row">
                              <h3>{product.name}</h3>
                              {product.sku && (
                                <span className="product-sku">{product.sku}</span>
                              )}
                            </div>
                            <p>
                              بيع: {formatPrice(product.sale_price)} · تكلفة:{" "}
                              {formatPrice(product.cost_price)} ·{" "}
                              {productUnits.find((unit) => unit.value === product.unit)
                                ?.label ?? product.unit}
                            </p>
                            {product.description && <p>{product.description}</p>}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">▤</span>
                      <h3>لسه مافيش منتجات</h3>
                      <p>أضف أول منتج أو خدمة للكتالوج من النموذج أعلاه.</p>
                    </div>
                  )}
                </>
              ) : organizationSection === "members" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <button
                        className="back-button"
                        type="button"
                        onClick={() => {
                          setSelectedOrganizationId(null);
                          setOrganizationMembers([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>أعضاء {selectedOrganization.name}</h2>
                      <p>
                        بيانات أعضاء هذه الشركة وأدوارهم فقط. هذه الشاشة للعرض
                        دون تعديل العضويات.
                      </p>
                    </div>
                    <span className="count-badge">{organizationMembers.length}</span>
                  </div>

                  {organizationMembers.length > 0 ? (
                    <div className="membership-list">
                      {organizationMembers.map((membership) => (
                        <article className="membership-card" key={membership.id}>
                          <span className="organization-icon">ع</span>
                          <div className="membership-details">
                            <div className="member-heading">
                              <div>
                                <h3>
                                  {`${membership.user.firstName} ${membership.user.lastName}`.trim() ||
                                    membership.user.email}
                                </h3>
                                <p>
                                  {membership.user.email}
                                  {membership.user.phone && ` · ${membership.user.phone}`}
                                </p>
                              </div>
                              <span
                                className={`membership-status ${membership.is_active && membership.user.isActive ? "membership-status-active" : "membership-status-inactive"}`}
                              >
                                {membership.is_active && membership.user.isActive
                                  ? "نشط"
                                  : "غير نشط"}
                              </span>
                            </div>
                            <p>
                              الدور: {membership.role.name}
                              {membership.role.is_system && " · دور أساسي"}
                            </p>
                            <div className="permission-tags">
                              {membership.role.permissions.length > 0 ? (
                                membership.role.permissions.map((permission) => (
                                  <span
                                    className="permission-tag"
                                    key={permission.code}
                                    title={permission.description || permission.name}
                                  >
                                    {permission.code}
                                  </span>
                                ))
                              ) : (
                                <span className="member-empty-permissions">
                                  لا توجد صلاحيات مخصصة
                                </span>
                              )}
                            </div>
                            <p className="member-joined">
                              تاريخ الانضمام:{" "}
                              {new Intl.DateTimeFormat("ar-EG", {
                                dateStyle: "medium",
                              }).format(new Date(membership.joined_at))}
                            </p>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">♙</span>
                      <h3>لا يوجد أعضاء في هذه الشركة</h3>
                      <p>ستظهر العضويات هنا عند إضافتها في خطوة لاحقة.</p>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="section-heading">
                    <div>
                      <button
                        className="back-button"
                        type="button"
                        onClick={() => {
                          setSelectedOrganizationId(null);
                          setOrganizationRoles([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>الأدوار والصلاحيات · {selectedOrganization.name}</h2>
                      <p>
                        كتالوج الأدوار والصلاحيات المعتمد لهذه الشركة. التعديل
                        غير متاح في هذه المرحلة.
                      </p>
                    </div>
                    <span className="count-badge">{organizationRoles.length}</span>
                  </div>

                  {organizationRoles.length > 0 ? (
                    <div className="role-list">
                      {organizationRoles.map((role) => (
                        <article className="role-card" key={role.id}>
                          <div className="role-heading">
                            <div>
                              <h3>{role.name}</h3>
                              <span className="role-code">{role.code}</span>
                            </div>
                            {role.is_system && (
                              <span className="module-state state-ready">
                                دور أساسي
                              </span>
                            )}
                          </div>
                          <div className="role-permission-list">
                            {role.permissions.length > 0 ? (
                              role.permissions.map((permission) => (
                                <div className="role-permission" key={permission.code}>
                                  <span className="permission-tag">{permission.code}</span>
                                  <span>{permission.name}</span>
                                  {permission.description && (
                                    <span className="role-permission-description">
                                      {permission.description}
                                    </span>
                                  )}
                                </div>
                              ))
                            ) : (
                              <p className="member-empty-permissions">
                                لا توجد صلاحيات مخصصة لهذا الدور.
                              </p>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">♧</span>
                      <h3>لا توجد أدوار لهذه الشركة</h3>
                      <p>ستظهر الأدوار المعرفة للشركة هنا.</p>
                    </div>
                  )}
                </>
              )}
            </>
          ) : (
            <>
              <div className="section-heading">
                <div>
                  <h2>الشركات</h2>
                  <p>تظهر هنا الشركات التي لديك عضوية نشطة فيها فقط.</p>
                </div>
                <span className="count-badge">{organizations.length}</span>
              </div>

              <form className="organization-form" onSubmit={handleCreateOrganization}>
                <label className="visually-hidden" htmlFor="organization-name">
                  اسم الشركة الجديدة
                </label>
                <input
                  id="organization-name"
                  name="name"
                  type="text"
                  maxLength={160}
                  placeholder="اسم الشركة الجديدة"
                  required
                  disabled={isSubmitting}
                />
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "جارٍ الحفظ..." : "إضافة شركة"}
                </button>
              </form>

              {organizations.length > 0 ? (
                <div className="organization-list">
                  {organizations.map((organization) => (
                    <article className="organization-card" key={organization.id}>
                      <span className="organization-icon">ش</span>
                      <div>
                        <h3>{organization.name}</h3>
                        <p>شركة · عضويتك مفعّلة</p>
                      </div>
                      <div className="organization-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => void handleOpenCustomers(organization)}
                          disabled={isSubmitting}
                        >
                          إدارة العملاء
                        </button>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => void handleOpenProducts(organization)}
                          disabled={isSubmitting}
                        >
                          إدارة المنتجات
                        </button>
                        {user?.memberships
                          .find((membership) => membership.organizationId === organization.id)
                          ?.permissions.includes("users.manage") && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void handleOpenMembers(organization)}
                            disabled={isSubmitting}
                          >
                            أعضاء الشركة
                          </button>
                        )}
                        {user?.memberships
                          .find((membership) => membership.organizationId === organization.id)
                          ?.permissions.includes("roles.manage") && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void handleOpenRoles(organization)}
                            disabled={isSubmitting}
                          >
                            الأدوار والصلاحيات
                          </button>
                        )}
                      </div>
                      <span className="module-state state-ready">نشطة</span>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">▦</span>
                  <h3>مافيش شركات لسه</h3>
                  <p>أضف أول شركة عشان تبدأ إعداد بياناتها.</p>
                </div>
              )}
            </>
          )}
        </section>

        <footer className="page-footer">
          مشروع خاص قيد التطوير <span>·</span> البيانات التجريبية فقط
        </footer>
      </section>
    </main>
  );
}
