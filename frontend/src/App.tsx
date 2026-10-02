import { FormEvent, Fragment, useCallback, useEffect, useState } from "react";

type ApiHealth = { status: "ok" };
type UserMembership = {
  organizationId: string;
  organizationName: string;
  businessType: "company" | "restaurant";
  countryCode: "EG" | "SA";
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
type Organization = {
  id: string;
  name: string;
  business_type: "company" | "restaurant";
  country_code: "EG" | "SA";
  created_at: string;
};
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
  category: string | null;
  description: string;
  unit: string;
  sale_price: string;
  cost_price: string;
  is_active: boolean;
  created_at: string;
};
type ProductCategory = {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
};
type Warehouse = {
  id: string;
  name: string;
  code: string;
  address: string;
  is_active: boolean;
};
type StockMovement = {
  id: string;
  warehouse: string;
  product: string;
  direction: "in" | "out";
  quantity: string;
  note: string;
  actor: string | null;
  created_at: string;
};
type StockBalance = {
  warehouse_id: string;
  warehouse_name: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: string;
};
type InvoiceLine = {
  id: string;
  product: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  line_total: string;
};
type PaymentCollection = {
  id: string;
  amount: string;
  method: "cash" | "bank" | "card";
  note: string;
  actor: string | null;
  collected_at: string;
};
type SalesInvoice = {
  id: string;
  number: string;
  customer: string;
  customer_name: string;
  warehouse: string;
  warehouse_name: string;
  issue_date: string;
  total: string;
  amount_collected: string;
  balance_due: string;
  actor: string | null;
  issued_at: string;
  lines: InvoiceLine[];
  payments: PaymentCollection[];
};
type InvoiceDraftLine = {
  productId: string;
  quantity: string;
  unitPrice: string;
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
  role: {
    name: string;
    is_system: boolean;
  };
  is_active: boolean;
  joined_at: string;
};
type LoginResponse = { user: User; csrfToken: string };
type SessionStatus = { authenticated: boolean };
type OrganizationSection =
  | "customers"
  | "products"
  | "members"
  | "inventory"
  | "sales";
type OpenForm =
  | "customer"
  | "product"
  | "category"
  | "warehouse"
  | "movement"
  | "invoice"
  | null;
type AuthView =
  | "login"
  | "register"
  | "forgot-password"
  | "reset-password"
  | "verify-email"
  | "resend-verification";
const initialResetParams = new URLSearchParams(window.location.hash.slice(1));

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
  if (response.status === 404) {
    return `مسار الخدمة غير موجود على الخادم (${new URL(response.url).pathname}). أعد تشغيل الخادم وتأكد من نشر النسخة الحالية.`;
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
  const [editingOrganization, setEditingOrganization] =
    useState<Organization | null>(null);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [isAccountView, setIsAccountView] = useState(false);
  const [openForm, setOpenForm] = useState<OpenForm>(null);
  const [organizationSection, setOrganizationSection] =
    useState<OrganizationSection>("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [productCategories, setProductCategories] = useState<ProductCategory[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [stockBalances, setStockBalances] = useState<StockBalance[]>([]);
  const [salesInvoices, setSalesInvoices] = useState<SalesInvoice[]>([]);
  const [invoiceLines, setInvoiceLines] = useState<InvoiceDraftLine[]>([
    { productId: "", quantity: "1.000", unitPrice: "0.00" },
  ]);
  const [collectingInvoiceId, setCollectingInvoiceId] = useState<string | null>(null);
  const [organizationMembers, setOrganizationMembers] = useState<OrganizationMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [passwordResetCredentials] = useState(() => ({
    uid: initialResetParams.get("uid"),
    token: initialResetParams.get("token"),
  }));
  const [emailVerificationCredentials] = useState(() => ({
    uid: initialResetParams.get("uid"),
    token: initialResetParams.get("token"),
  }));
  const [authView, setAuthView] = useState<AuthView>(() =>
    initialResetParams.get("password_reset") === "1"
      ? "reset-password"
      : initialResetParams.get("email_verification") === "1"
        ? "verify-email"
      : "login",
  );
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (
      initialResetParams.get("password_reset") === "1" ||
      initialResetParams.get("email_verification") === "1"
    ) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

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

  const loadProductCategories = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/product-categories/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: ProductCategory[] = await response.json();
    setProductCategories(items);
  }, []);

  const loadInventory = useCallback(async (
    organizationId: string,
    includeProductCatalog: boolean,
  ) => {
    const base = `/api/v1/organizations/${encodeURIComponent(organizationId)}`;
    const [warehouseResponse, balanceResponse, movementResponse, productResponse] =
      await Promise.all([
        fetch(`${base}/warehouses/`),
        fetch(`${base}/stock-balances/`),
        fetch(`${base}/stock-movements/`),
        includeProductCatalog ? fetch(`${base}/products/`) : Promise.resolve(null),
      ]);
    for (const response of [
      warehouseResponse,
      balanceResponse,
      movementResponse,
      productResponse,
    ]) {
      if (response && !response.ok) throw new Error(await responseError(response));
    }
    const [warehouseItems, balanceItems, movementItems, productItems] =
      await Promise.all([
        warehouseResponse.json() as Promise<Warehouse[]>,
        balanceResponse.json() as Promise<StockBalance[]>,
        movementResponse.json() as Promise<StockMovement[]>,
        productResponse
          ? (productResponse.json() as Promise<Product[]>)
          : Promise.resolve([] as Product[]),
      ]);
    setWarehouses(warehouseItems);
    setStockBalances(balanceItems);
    setStockMovements(movementItems);
    setProducts(productItems);
  }, []);

  const loadSalesInvoices = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/sales-invoices/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: SalesInvoice[] = await response.json();
    setSalesInvoices(items);
  }, []);

  const loadOrganizationMembers = useCallback(async (organizationId: string) => {
    const response = await fetch(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/members/`,
    );
    if (!response.ok) throw new Error(await responseError(response));
    const items: OrganizationMember[] = await response.json();
    setOrganizationMembers(items);
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

        const sessionResponse = await fetch("/api/v1/auth/session/", {
          signal: controller.signal,
        });
        if (!sessionResponse.ok) {
          throw new Error(await responseError(sessionResponse));
        }
        const session: SessionStatus = await sessionResponse.json();
        if (session.authenticated) {
          const userResponse = await fetch("/api/v1/auth/me/", {
            signal: controller.signal,
          });
          if (!userResponse.ok) {
            throw new Error(await responseError(userResponse));
          }
          const currentUser: User = await userResponse.json();
          setUser(currentUser);
          await loadOrganizations();
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
      try {
        await loadOrganizations();
      } catch (caught: unknown) {
        setError(
          caught instanceof Error
            ? `تم تسجيل الدخول بنجاح، لكن تعذر تحميل الشركات. ${caught.message}`
            : "تم تسجيل الدخول بنجاح، لكن تعذر تحميل الشركات. حدّث الصفحة وحاول مجددًا.",
        );
      }
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

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/v1/auth/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          email: form.get("email"),
          firstName: form.get("firstName"),
          lastName: form.get("lastName"),
          organizationName: form.get("organizationName"),
          businessType: form.get("businessType"),
          countryCode: form.get("countryCode"),
          password: form.get("password"),
          confirmPassword: form.get("confirmPassword"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: { detail: string } = await response.json();
      setAuthView("login");
      setNotice(result.detail);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر إنشاء الحساب. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePasswordResetRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/v1/auth/password/reset/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ email: form.get("email") }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: { detail: string } = await response.json();
      setNotice(result.detail);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر طلب إعادة تعيين كلمة المرور. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePasswordResetConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/v1/auth/password/reset/confirm/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          uid: passwordResetCredentials.uid,
          token: passwordResetCredentials.token,
          newPassword: form.get("newPassword"),
          confirmPassword: form.get("confirmPassword"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: { detail: string } = await response.json();
      window.history.replaceState({}, "", window.location.pathname);
      setAuthView("login");
      setNotice(result.detail);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحديث كلمة المرور. اطلب رابط استعادة جديدًا.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEmailVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/v1/auth/email/verify/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(emailVerificationCredentials),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: { detail: string } = await response.json();
      setAuthView("login");
      setNotice(result.detail);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تفعيل الحساب. اطلب رسالة تفعيل جديدة.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResendVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/v1/auth/email/resend-verification/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ email: form.get("email") }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result: { detail: string } = await response.json();
      setNotice(result.detail);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر إرسال رسالة التفعيل. حاول مرة أخرى.",
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
        body: JSON.stringify({
          name: form.get("name"),
          business_type: form.get("business_type"),
          country_code: form.get("country_code"),
        }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const organization: Organization = await response.json();
      setOrganizations((current) =>
        [...current, organization].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      setOpenForm(null);
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
      setOpenForm(null);
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
      await Promise.all([
        loadProducts(organization.id),
        loadProductCategories(organization.id),
      ]);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("products");
      setEditingProduct(null);
      setOpenForm(null);
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

  async function handleOpenInventory(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      const canReadProducts =
        user?.memberships
          .find((membership) => membership.organizationId === organization.id)
          ?.permissions.includes("products.read") ?? false;
      await loadInventory(organization.id, canReadProducts);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("inventory");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تحميل بيانات المخزون.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOpenSales(organization: Organization) {
    setError("");
    setIsSubmitting(true);
    try {
      const permissions =
        user?.memberships.find(
          (membership) => membership.organizationId === organization.id,
        )?.permissions ?? [];
      const requests: Promise<void>[] = [
        loadSalesInvoices(organization.id),
      ];
      if (permissions.includes("customers.read")) {
        requests.push(loadCustomers(organization.id));
      }
      if (permissions.includes("products.read")) {
        requests.push(loadProducts(organization.id));
      }
      if (permissions.includes("inventory.read")) {
        requests.push(loadInventory(organization.id, permissions.includes("products.read")));
      }
      await Promise.all(requests);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("sales");
      setCollectingInvoiceId(null);
      setInvoiceLines([{ productId: "", quantity: "1.000", unitPrice: "0.00" }]);
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر تحميل فواتير المبيعات.",
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
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/customers/${editingCustomer ? `${encodeURIComponent(editingCustomer.id)}/` : ""}`,
        {
          method: editingCustomer ? "PATCH" : "POST",
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
        (editingCustomer
          ? current.map((item) => (item.id === customer.id ? customer : item))
          : [...current, customer]
        ).sort((first, second) => first.name.localeCompare(second.name, "ar")),
      );
      setEditingCustomer(null);
      setOpenForm(null);
      formElement.reset();
      setNotice(editingCustomer ? "تم حفظ تعديلات العميل." : "تمت إضافة العميل.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر حفظ بيانات العميل. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteCustomer(customer: Customer) {
    if (!selectedOrganizationId) return;
    if (!window.confirm(`حذف العميل «${customer.name}» نهائيًا؟ إذا كان مرتبطًا بفواتير فلن يسمح النظام بحذفه حفاظًا على السجلات.`)) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/customers/${encodeURIComponent(customer.id)}/`,
        { method: "DELETE", headers: { "X-CSRFToken": csrfToken } },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setCustomers((current) => current.filter((item) => item.id !== customer.id));
      if (editingCustomer?.id === customer.id) {
        setEditingCustomer(null);
        setOpenForm(null);
      }
      setNotice("تم حذف العميل نهائيًا.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "تعذر حذف العميل.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
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
            category: form.get("category") || null,
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
      setOpenForm(null);
      formElement.reset();
      setNotice("تمت إضافة المنتج.");
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

  async function handleUpdateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId || !editingProduct) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/products/${encodeURIComponent(editingProduct.id)}/`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            name: form.get("name"),
            sku: form.get("sku"),
            category: form.get("category") || null,
            description: form.get("description"),
            unit: form.get("unit"),
            sale_price: form.get("sale_price") || "0",
            cost_price: form.get("cost_price") || "0",
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const updatedProduct: Product = await response.json();
      setProducts((current) =>
        current
          .map((product) =>
            product.id === updatedProduct.id ? updatedProduct : product,
          )
          .sort((first, second) => first.name.localeCompare(second.name, "ar")),
      );
      setEditingProduct(null);
      setOpenForm(null);
      setNotice("تم حفظ تعديلات المنتج.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر حفظ تعديلات المنتج. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteProduct(product: Product) {
    if (!selectedOrganizationId) return;
    if (!window.confirm(`حذف المنتج «${product.name}» نهائيًا؟ إذا كان مرتبطًا بفواتير أو حركات مخزون فلن يسمح النظام بحذفه حفاظًا على السجلات.`)) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/products/${encodeURIComponent(product.id)}/`,
        { method: "DELETE", headers: { "X-CSRFToken": csrfToken } },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setProducts((current) => current.filter((item) => item.id !== product.id));
      if (editingProduct?.id === product.id) {
        setEditingProduct(null);
        setOpenForm(null);
      }
      setNotice("تم حذف المنتج نهائيًا.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "تعذر حذف المنتج.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateProductCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/product-categories/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ name: form.get("name") }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const category: ProductCategory = await response.json();
      setProductCategories((current) =>
        [...current, category].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      setOpenForm(null);
      formElement.reset();
      setNotice("تمت إضافة التصنيف.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر إضافة تصنيف المنتج. حاول مرة أخرى.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateWarehouse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/warehouses/${editingWarehouse ? `${encodeURIComponent(editingWarehouse.id)}/` : ""}`,
        {
          method: editingWarehouse ? "PATCH" : "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            name: form.get("name"),
            code: form.get("code"),
            address: form.get("address"),
            is_active: editingWarehouse
              ? form.get("is_active") === "on"
              : true,
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const warehouse: Warehouse = await response.json();
      setWarehouses((current) =>
        (editingWarehouse
          ? current.map((item) => (item.id === warehouse.id ? warehouse : item))
          : [...current, warehouse]
        ).sort((first, second) => first.name.localeCompare(second.name, "ar")),
      );
      setEditingWarehouse(null);
      setOpenForm(null);
      formElement.reset();
      setNotice(editingWarehouse ? "تم حفظ تعديلات المخزن." : "تمت إضافة المخزن.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر حفظ بيانات المخزن.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteWarehouse(warehouse: Warehouse) {
    if (!selectedOrganizationId) return;
    if (!window.confirm(`حذف المخزن «${warehouse.name}» نهائيًا؟ لا يمكن حذف المخازن المرتبطة بحركات مخزون أو فواتير.`)) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/warehouses/${encodeURIComponent(warehouse.id)}/`,
        { method: "DELETE", headers: { "X-CSRFToken": csrfToken } },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setWarehouses((current) => current.filter((item) => item.id !== warehouse.id));
      if (editingWarehouse?.id === warehouse.id) {
        setEditingWarehouse(null);
        setOpenForm(null);
      }
      setNotice("تم حذف المخزن الفارغ.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "تعذر حذف المخزن.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteOrganization(organization: Organization) {
    if (!window.confirm(`حذف الشركة «${organization.name}» وكل بياناتها غير المرتبطة بحركات أو فواتير نهائيًا؟ إذا وُجدت سجلات مالية أو حركات مخزون سيمنع النظام الحذف. لا يمكن التراجع عن هذه العملية.`)) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(organization.id)}/`,
        { method: "DELETE", headers: { "X-CSRFToken": csrfToken } },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setOrganizations((current) => current.filter((item) => item.id !== organization.id));
      setEditingOrganization((current) =>
        current?.id === organization.id ? null : current,
      );
      setUser((current) =>
        current
          ? {
              ...current,
              memberships: current.memberships.filter(
                (membership) => membership.organizationId !== organization.id,
              ),
            }
          : current,
      );
      if (selectedOrganizationId === organization.id) {
        setSelectedOrganizationId(null);
        setCustomers([]);
        setProducts([]);
        setWarehouses([]);
        setSalesInvoices([]);
        setStockMovements([]);
        setStockBalances([]);
      }
      setNotice("تم حذف الشركة والبيانات التابعة لها.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "تعذر حذف الشركة.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateOrganization(
    event: FormEvent<HTMLFormElement>,
    organization: Organization,
  ) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSubmitting(true);
    const name = new FormData(event.currentTarget).get("name");

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(organization.id)}/`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ name }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const updatedOrganization: Organization = await response.json();
      setOrganizations((current) =>
        current.map((item) =>
          item.id === updatedOrganization.id ? updatedOrganization : item,
        ),
      );
      setUser((current) =>
        current
          ? {
              ...current,
              memberships: current.memberships.map((membership) =>
                membership.organizationId === updatedOrganization.id
                  ? { ...membership, organizationName: updatedOrganization.name }
                  : membership,
              ),
            }
          : current,
      );
      setEditingOrganization(null);
      setNotice("تم حفظ اسم الشركة.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "تعذر تعديل الشركة.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateStockMovement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/stock-movements/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            warehouse: form.get("warehouse"),
            product: form.get("product"),
            direction: form.get("direction"),
            quantity: form.get("quantity"),
            note: form.get("note"),
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const canReadProducts =
        user?.memberships
          .find((membership) => membership.organizationId === selectedOrganizationId)
          ?.permissions.includes("products.read") ?? false;
      await loadInventory(selectedOrganizationId, canReadProducts);
      setOpenForm(null);
      formElement.reset();
      setNotice("تم تسجيل حركة المخزون وتحديث الرصيد.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error
          ? caught.message
          : "تعذر تسجيل حركة المخزون.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateInvoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/sales-invoices/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            customer: form.get("customer"),
            warehouse: form.get("warehouse"),
            lines: invoiceLines.map((line) => ({
              product: line.productId,
              quantity: line.quantity,
              unit_price: line.unitPrice,
            })),
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const permissions =
        user?.memberships.find(
          (membership) => membership.organizationId === selectedOrganizationId,
        )?.permissions ?? [];
      await Promise.all([
        loadSalesInvoices(selectedOrganizationId),
        ...(permissions.includes("inventory.read")
          ? [loadInventory(selectedOrganizationId, permissions.includes("products.read"))]
          : []),
      ]);
      setOpenForm(null);
      setInvoiceLines([{ productId: "", quantity: "1.000", unitPrice: "0.00" }]);
      setNotice("تم إصدار فاتورة البيع وتحديث رصيد المخزون.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر إصدار فاتورة البيع.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCollectPayment(
    event: FormEvent<HTMLFormElement>,
    invoiceId: string,
  ) {
    event.preventDefault();
    if (!selectedOrganizationId) return;

    setError("");
    setNotice("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch(
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/sales-invoices/${encodeURIComponent(invoiceId)}/payments/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            amount: form.get("amount"),
            method: form.get("method"),
            note: form.get("note"),
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      await loadSalesInvoices(selectedOrganizationId);
      setCollectingInvoiceId(null);
      setNotice("تم تسجيل التحصيل بنجاح.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر تسجيل التحصيل.",
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
  const dashboardOrganization = selectedOrganization ?? organizations[0] ?? null;
  const salesOrganization = organizations.find((organization) =>
    organization.id === selectedOrganizationId &&
    user?.memberships.some(
      (membership) =>
        membership.organizationId === organization.id &&
        membership.permissions.includes("sales.read"),
    ),
  ) ?? organizations.find((organization) =>
    user?.memberships.some(
      (membership) =>
        membership.organizationId === organization.id &&
        membership.permissions.includes("sales.read"),
    ),
  ) ?? null;
  const selectedOrganizationMembership = user?.memberships.find(
    (membership) => membership.organizationId === selectedOrganizationId,
  );
  const canManageMembers =
    selectedOrganizationMembership?.permissions.includes("users.manage") ?? false;
  const canManageProducts =
    selectedOrganizationMembership?.permissions.includes("products.manage") ?? false;
  const canManageCustomers =
    selectedOrganizationMembership?.permissions.includes("customers.manage") ?? false;
  const canReadInventory =
    selectedOrganizationMembership?.permissions.includes("inventory.read") ?? false;
  const canManageInventory =
    selectedOrganizationMembership?.permissions.includes("inventory.manage") ?? false;
  const canReadSales =
    selectedOrganizationMembership?.permissions.includes("sales.read") ?? false;
  const canManageSales =
    selectedOrganizationMembership?.permissions.includes("sales.manage") ?? false;
  const selectedPermissions = selectedOrganizationMembership?.permissions ?? [];
  const canCreateSalesInvoice =
    canManageSales &&
    selectedPermissions.includes("customers.read") &&
    selectedPermissions.includes("products.read") &&
    canReadInventory;
  if (isLoading) {
    return (
      <main className="auth-shell">
        <div className="auth-card loading-card">جارٍ تجهيز نسق...</div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand auth-brand">
            <span className="brand-mark">ن</span>
            <span>نسق</span>
          </div>
          <div className="welcome-kicker">منصة إدارة الأعمال</div>
          <h1>
            {authView === "register"
              ? "إنشاء حساب جديد"
              : authView === "forgot-password"
                ? "استعادة كلمة المرور"
                : authView === "reset-password"
                  ? "اختيار كلمة مرور جديدة"
                  : authView === "verify-email"
                    ? "تفعيل الحساب"
                    : authView === "resend-verification"
                      ? "إعادة إرسال رسالة التفعيل"
                  : "تسجيل الدخول"}
          </h1>
          <p className="auth-description">
            {authView === "register"
              ? "أنشئ حسابك وابدأ بإدارة شركتك أو مطعمك."
              : authView === "forgot-password"
                ? "أدخل بريد حسابك وسنرسل رابطًا آمنًا إذا كان مسجلًا لدينا."
                : authView === "reset-password"
                  ? "اختر كلمة مرور قوية لحسابك."
                    : authView === "verify-email"
                      ? "أكد ملكية بريدك الإلكتروني لإكمال التسجيل."
                      : authView === "resend-verification"
                        ? "أدخل بريدك وسنرسل رسالة تفعيل إذا كان الحساب بانتظار التأكيد."
                : "سجّل الدخول للبدء بإدارة شركاتك وبياناتك."}
          </p>
          {error && <div className="alert-error" role="alert">{error}</div>}
          {notice && <div className="alert-success" role="status">{notice}</div>}
          {authView === "register" ? (
            <form className="auth-form" onSubmit={handleRegister}>
              <label htmlFor="register-first-name">الاسم الأول *</label>
              <input
                id="register-first-name"
                name="firstName"
                type="text"
                autoComplete="given-name"
                maxLength={150}
                required
                disabled={isSubmitting}
              />
              <label htmlFor="register-last-name">اسم العائلة</label>
              <input
                id="register-last-name"
                name="lastName"
                type="text"
                autoComplete="family-name"
                maxLength={150}
                disabled={isSubmitting}
              />
              <label htmlFor="register-organization-name">اسم الشركة أو المطعم *</label>
              <input
                id="register-organization-name"
                name="organizationName"
                type="text"
                maxLength={160}
                required
                disabled={isSubmitting}
              />
              <label htmlFor="register-business-type">نوع النشاط *</label>
              <select
                id="register-business-type"
                name="businessType"
                defaultValue="company"
                required
                disabled={isSubmitting}
              >
                <option value="company">شركة / نشاط تجاري</option>
                <option value="restaurant">مطعم</option>
              </select>
              <label htmlFor="register-country">دولة النشاط *</label>
              <select
                id="register-country"
                name="countryCode"
                defaultValue="EG"
                required
                disabled={isSubmitting}
              >
                <option value="EG">مصر</option>
                <option value="SA">السعودية</option>
              </select>
              <label htmlFor="register-email">البريد الإلكتروني *</label>
              <input
                id="register-email"
                name="email"
                type="email"
                autoComplete="email"
                maxLength={254}
                required
                disabled={isSubmitting}
              />
              <label htmlFor="register-password">كلمة المرور *</label>
              <input
                id="register-password"
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={isSubmitting}
              />
              <label htmlFor="register-confirm-password">تأكيد كلمة المرور *</label>
              <input
                id="register-confirm-password"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={isSubmitting}
              />
              <p className="field-hint">
                استخدم كلمة مرور قوية. سيتم إنشاء شركة جديدة وربطها بحسابك كمالك.
              </p>
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ إنشاء الحساب..." : "إنشاء الحساب والشركة"}
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("login");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                لدي حساب بالفعل — تسجيل الدخول
              </button>
            </form>
          ) : authView === "forgot-password" ? (
            <form className="auth-form" onSubmit={handlePasswordResetRequest}>
              <label htmlFor="reset-request-email">البريد الإلكتروني</label>
              <input
                id="reset-request-email"
                name="email"
                type="email"
                autoComplete="email"
                required
                disabled={isSubmitting}
              />
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ إرسال الطلب..." : "إرسال رابط الاستعادة"}
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("login");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                العودة لتسجيل الدخول
              </button>
            </form>
          ) : authView === "reset-password" ? (
            <form className="auth-form" onSubmit={handlePasswordResetConfirm}>
              <label htmlFor="reset-new-password">كلمة المرور الجديدة</label>
              <input
                id="reset-new-password"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={isSubmitting}
              />
              <label htmlFor="reset-confirm-password">تأكيد كلمة المرور</label>
              <input
                id="reset-confirm-password"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                disabled={isSubmitting}
              />
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ تحديث كلمة المرور..." : "حفظ كلمة المرور"}
              </button>
            </form>
          ) : authView === "verify-email" ? (
            <form className="auth-form" onSubmit={handleEmailVerification}>
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ تفعيل الحساب..." : "تأكيد البريد وتفعيل الحساب"}
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("resend-verification");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                لم تصلك رسالة التفعيل؟
              </button>
            </form>
          ) : authView === "resend-verification" ? (
            <form className="auth-form" onSubmit={handleResendVerification}>
              <label htmlFor="verification-email">البريد الإلكتروني</label>
              <input
                id="verification-email"
                name="email"
                type="email"
                autoComplete="email"
                required
                disabled={isSubmitting}
              />
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ إرسال الطلب..." : "إعادة إرسال رسالة التفعيل"}
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("login");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                العودة لتسجيل الدخول
              </button>
            </form>
          ) : (
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
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("forgot-password");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                نسيت كلمة المرور؟
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("resend-verification");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                لم تصلك رسالة التفعيل؟
              </button>
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "جارٍ تسجيل الدخول..." : "دخول آمن"}
              </button>
              <button
                className="auth-switch-button"
                type="button"
                onClick={() => {
                  setAuthView("register");
                  setError("");
                  setNotice("");
                }}
                disabled={isSubmitting}
              >
                مستخدم جديد؟ أنشئ حسابًا مجانيًا
              </button>
            </form>
          )}
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
          <span className="brand-mark">ن</span>
          <span>نسق</span>
        </div>
        <nav className="sidebar-navigation" aria-label="التنقل الرئيسي">
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
                membership.permissions.includes("inventory.read"),
            ),
          ) && (
            <a
              className={`nav-item ${selectedOrganization && organizationSection === "inventory" ? "nav-item-active" : "nav-item-muted"}`}
              href="#organizations"
              onClick={() => {
                const inventoryOrganization = organizations.find((organization) =>
                  user?.memberships.some(
                    (membership) =>
                      membership.organizationId === organization.id &&
                      membership.permissions.includes("inventory.read"),
                  ),
                );
                if (inventoryOrganization) void handleOpenInventory(inventoryOrganization);
              }}
            >
              <span className="nav-icon">▥</span>
              المخزون
            </a>
          )}
          {salesOrganization && (
            <a
              className={`nav-item ${selectedOrganization && organizationSection === "sales" ? "nav-item-active" : "nav-item-muted"}`}
              href="#organizations"
              onClick={() => void handleOpenSales(salesOrganization)}
            >
              <span className="nav-icon">▧</span>
              المبيعات
            </a>
          )}
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
        </nav>
        <div className="sidebar-footer">إدارة أعمالك ببساطة</div>
      </aside>

      <section className="workspace" id="overview">
        <header className="topbar">
          <div>
            <div className="eyebrow">منصة إدارة الأعمال</div>
            <h1>لوحة التحكم</h1>
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
            <h2>كل أعمالك، في نسق واحد.</h2>
            <p>تابع المخزون والعملاء والمبيعات من مساحة عمل آمنة ومنظمة.</p>
          </div>
          <div className="welcome-orbit" aria-hidden="true">
            <span className="orbit-ring orbit-ring-outer" />
            <span className="orbit-ring orbit-ring-inner" />
            <span className="orbit-core">ن</span>
          </div>
        </section>

        <section className="dashboard-summary" aria-label="ملخص سريع">
          <article className="summary-card">
            <span className="summary-icon">ش</span>
            <div>
              <span className="summary-label">الشركات النشطة</span>
              <strong>{organizations.length}</strong>
            </div>
          </article>
          <button
            className="summary-card summary-card-action"
            type="button"
            onClick={() =>
              dashboardOrganization && void handleOpenCustomers(dashboardOrganization)
            }
            disabled={isSubmitting || !dashboardOrganization}
          >
            <span className="summary-icon summary-icon-blue">ع</span>
            <div>
              <span className="summary-label">العملاء</span>
              <strong>{selectedOrganization ? customers.length : "عرض العملاء"}</strong>
            </div>
          </button>
          <button
            className="summary-card summary-card-action"
            type="button"
            onClick={() =>
              dashboardOrganization && void handleOpenProducts(dashboardOrganization)
            }
            disabled={isSubmitting || !dashboardOrganization}
          >
            <span className="summary-icon summary-icon-orange">م</span>
            <div>
              <span className="summary-label">المنتجات</span>
              <strong>{selectedOrganization ? products.length : "عرض المنتجات"}</strong>
            </div>
          </button>
          {salesOrganization && (
            <button
              className="summary-card summary-card-action"
              type="button"
              onClick={() => void handleOpenSales(salesOrganization)}
              disabled={isSubmitting}
            >
              <span className="summary-icon">ف</span>
              <div>
                <span className="summary-label">فواتير البيع</span>
                <strong>
                  {selectedOrganizationId === salesOrganization.id
                    ? salesInvoices.length
                    : "عرض المبيعات"}
                </strong>
              </div>
            </button>
          )}
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
                    ← لوحة التحكم
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
                  <p>الشركات المرتبطة بحسابك.</p>
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
                {canReadInventory && (
                  <button
                    className={`module-tab ${organizationSection === "inventory" ? "module-tab-active" : ""}`}
                    type="button"
                    role="tab"
                    aria-selected={organizationSection === "inventory"}
                    onClick={() => void handleOpenInventory(selectedOrganization)}
                    disabled={isSubmitting}
                  >
                    المخزون
                  </button>
                )}
                {canReadSales && (
                  <button
                    className={`module-tab ${organizationSection === "sales" ? "module-tab-active" : ""}`}
                    type="button"
                    role="tab"
                    aria-selected={organizationSection === "sales"}
                    onClick={() => void handleOpenSales(selectedOrganization)}
                    disabled={isSubmitting}
                  >
                    المبيعات
                  </button>
                )}
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
                <div className="section-heading-actions">
                  <span className="count-badge">{customers.length}</span>
                  {canManageCustomers && (
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => {
                        if (openForm === "customer" && !editingCustomer) {
                          setOpenForm(null);
                          return;
                        }
                        setEditingCustomer(null);
                        setOpenForm("customer");
                      }}
                      disabled={isSubmitting}
                      aria-expanded={openForm === "customer"}
                    >
                      {openForm === "customer" ? "إغلاق النموذج" : "إضافة عميل"}
                    </button>
                  )}
                </div>
              </div>

              {canManageCustomers && openForm === "customer" && (
              <form
                key={editingCustomer?.id ?? "new-customer"}
                className="customer-form"
                onSubmit={handleCreateCustomer}
              >
                <h3 className="form-section-title">
                  {editingCustomer ? "تعديل بيانات العميل" : "إضافة عميل"}
                </h3>
                <label htmlFor="customer-name">اسم العميل *</label>
                <input
                  id="customer-name"
                  name="name"
                  type="text"
                  maxLength={160}
                  placeholder="الاسم أو اسم الشركة"
                  defaultValue={editingCustomer?.name ?? ""}
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
                      defaultValue={editingCustomer?.phone ?? ""}
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
                      defaultValue={editingCustomer?.email ?? ""}
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
                  defaultValue={editingCustomer?.address ?? ""}
                  disabled={isSubmitting}
                />
                <label htmlFor="customer-notes">ملاحظات</label>
                <textarea
                  id="customer-notes"
                  name="notes"
                  maxLength={1000}
                  placeholder="ملاحظات داخلية اختيارية"
                  rows={2}
                  defaultValue={editingCustomer?.notes ?? ""}
                  disabled={isSubmitting}
                />
                <div className="product-form-actions">
                  <button className="primary-button" type="submit" disabled={isSubmitting}>
                    {isSubmitting
                      ? "جارٍ الحفظ..."
                      : editingCustomer
                        ? "حفظ التعديلات"
                        : "إضافة العميل"}
                  </button>
                  {editingCustomer && (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setEditingCustomer(null);
                        setOpenForm(null);
                      }}
                      disabled={isSubmitting}
                    >
                      إلغاء
                    </button>
                  )}
                </div>
              </form>
              )}

              {customers.length > 0 ? (
                <div className="customer-list">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">العميل</th>
                        <th scope="col">الهاتف</th>
                        <th scope="col">البريد الإلكتروني</th>
                        <th scope="col">العنوان</th>
                        {canManageCustomers && <th scope="col">إجراءات</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {customers.map((customer) => (
                        <tr key={customer.id}>
                          <td><strong>{customer.name}</strong></td>
                          <td>{customer.phone || "—"}</td>
                          <td>{customer.email || "—"}</td>
                          <td>{customer.address || "—"}</td>
                          {canManageCustomers && (
                            <td>
                              <button
                                className="table-action"
                                type="button"
                                onClick={() => {
                                  setEditingCustomer(customer);
                                  setOpenForm("customer");
                                }}
                                disabled={isSubmitting}
                              >
                                تعديل
                              </button>
                              <button
                                className="table-action table-action-danger"
                                type="button"
                                onClick={() => void handleDeleteCustomer(customer)}
                                disabled={isSubmitting}
                              >
                                حذف
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">◇</span>
                  <h3>لا يوجد عملاء بعد</h3>
                  <p>
                    {canManageCustomers
                      ? openForm === "customer"
                        ? "أكمل بيانات العميل في النموذج أعلاه."
                        : "ابدأ بإضافة أول عميل إلى هذه الشركة."
                      : "لا توجد سجلات عملاء لهذه الشركة بعد."}
                  </p>
                  {canManageCustomers && openForm !== "customer" && (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setEditingCustomer(null);
                        setOpenForm("customer");
                      }}
                      disabled={isSubmitting}
                    >
                      إضافة أول عميل
                    </button>
                  )}
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
                          setProductCategories([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>منتجات {selectedOrganization.name}</h2>
                      <p>كتالوج الشركة وأسعار المنتجات ووحدات القياس.</p>
                    </div>
                    <div className="section-heading-actions">
                      <span className="count-badge">{products.length}</span>
                      {canManageProducts && (
                        <>
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() =>
                              setOpenForm((current) =>
                                current === "category" ? null : "category",
                              )
                            }
                            disabled={isSubmitting}
                            aria-expanded={openForm === "category"}
                          >
                            {openForm === "category"
                              ? "إغلاق التصنيف"
                              : "إضافة تصنيف"}
                          </button>
                          <button
                            className="primary-button"
                            type="button"
                            onClick={() => {
                              setEditingProduct(null);
                              setOpenForm((current) =>
                                current === "product" ? null : "product",
                              );
                            }}
                            disabled={isSubmitting}
                            aria-expanded={openForm === "product"}
                          >
                            {openForm === "product"
                              ? "إغلاق النموذج"
                              : "إضافة منتج"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {canManageProducts && openForm === "category" && (
                    <form
                      className="organization-form product-category-form"
                      onSubmit={handleCreateProductCategory}
                    >
                      <label className="visually-hidden" htmlFor="product-category-name">
                        اسم التصنيف الجديد
                      </label>
                      <input
                        id="product-category-name"
                        name="name"
                        type="text"
                        maxLength={100}
                        placeholder="اسم تصنيف جديد"
                        required
                        disabled={isSubmitting}
                      />
                      <button
                        className="secondary-button"
                        type="submit"
                        disabled={isSubmitting}
                      >
                        إضافة تصنيف
                      </button>
                    </form>
                  )}

                  {canManageProducts && (openForm === "product" || editingProduct) && <form
                    key={editingProduct?.id ?? "new-product"}
                    className="customer-form"
                    onSubmit={editingProduct ? handleUpdateProduct : handleCreateProduct}
                  >
                    <label htmlFor="product-name">
                      {editingProduct ? "تعديل المنتج" : "اسم المنتج *"}
                    </label>
                    <input
                      id="product-name"
                      name="name"
                      type="text"
                      maxLength={160}
                      placeholder="اسم المنتج أو الخدمة"
                      defaultValue={editingProduct?.name ?? ""}
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
                          defaultValue={editingProduct?.sku ?? ""}
                          disabled={isSubmitting}
                        />
                      </div>
                      <div className="customer-field">
                        <label htmlFor="product-unit">وحدة القياس</label>
                        <select
                          id="product-unit"
                          name="unit"
                          defaultValue={editingProduct?.unit ?? "piece"}
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
                    <label htmlFor="product-category">تصنيف المنتج</label>
                    <select
                      id="product-category"
                      name="category"
                      defaultValue={editingProduct?.category ?? ""}
                      disabled={isSubmitting}
                    >
                      <option value="">بدون تصنيف</option>
                      {productCategories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                    </select>
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
                          defaultValue={editingProduct?.sale_price ?? "0.00"}
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
                          defaultValue={editingProduct?.cost_price ?? "0.00"}
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
                      defaultValue={editingProduct?.description ?? ""}
                      disabled={isSubmitting}
                    />
                    <div className="product-form-actions">
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={isSubmitting}
                      >
                        {isSubmitting
                          ? "جارٍ الحفظ..."
                          : editingProduct
                            ? "حفظ التعديلات"
                            : "إضافة المنتج"}
                      </button>
                      {editingProduct && (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => {
                            setEditingProduct(null);
                            setOpenForm(null);
                          }}
                          disabled={isSubmitting}
                        >
                          إلغاء
                        </button>
                      )}
                    </div>
                  </form>}

                  {products.length > 0 ? (
                    <div className="product-list">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">المنتج</th>
                            <th scope="col">التصنيف</th>
                            <th scope="col">الوحدة</th>
                            <th scope="col">سعر البيع</th>
                            <th scope="col">التكلفة</th>
                            {canManageProducts && <th scope="col">إجراءات</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {products.map((product) => (
                            <tr key={product.id}>
                              <td>
                                <strong>{product.name}</strong>
                                {product.sku && (
                                  <span className="table-subtext">{product.sku}</span>
                                )}
                              </td>
                              <td>
                                {productCategories.find(
                                  (category) => category.id === product.category,
                                )?.name ?? "—"}
                              </td>
                              <td>
                                {productUnits.find((unit) => unit.value === product.unit)
                                  ?.label ?? product.unit}
                              </td>
                              <td>{formatPrice(product.sale_price)}</td>
                              <td>{formatPrice(product.cost_price)}</td>
                              {canManageProducts && (
                                <td>
                                  <button
                                    className="table-action"
                                    type="button"
                                    onClick={() => {
                                      setEditingProduct(product);
                                      setOpenForm("product");
                                    }}
                                    disabled={isSubmitting}
                                  >
                                    تعديل
                                  </button>
                                  <button
                                    className="table-action table-action-danger"
                                    type="button"
                                    onClick={() => void handleDeleteProduct(product)}
                                    disabled={isSubmitting}
                                  >
                                    حذف
                                  </button>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">▤</span>
                      <h3>لسه مافيش منتجات</h3>
                      <p>
                        {canManageProducts
                          ? openForm === "product"
                            ? "أكمل بيانات المنتج في النموذج أعلاه."
                            : "ابدأ بإضافة أول منتج أو خدمة إلى الكتالوج."
                          : "لا توجد سجلات منتجات لهذه الشركة بعد."}
                      </p>
                      {canManageProducts && openForm !== "product" && (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => {
                            setEditingProduct(null);
                            setOpenForm("product");
                          }}
                          disabled={isSubmitting}
                        >
                          إضافة أول منتج
                        </button>
                      )}
                    </div>
                  )}
                </>
              ) : organizationSection === "inventory" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <button
                        className="back-button"
                        type="button"
                        onClick={() => {
                          setSelectedOrganizationId(null);
                          setStockMovements([]);
                          setStockBalances([]);
                          setWarehouses([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>المخزون · {selectedOrganization.name}</h2>
                      <p>الأرصدة الحالية وسجل الحركات المسجلة للمخازن.</p>
                    </div>
                    <span className="count-badge">{stockBalances.length}</span>
                  </div>

                  <div className="section-heading account-subheading">
                    <div>
                      <h2>المخازن</h2>
                      <p>المخازن النشطة التابعة لهذه الشركة.</p>
                    </div>
                    <div className="section-heading-actions">
                      <span className="count-badge">{warehouses.length}</span>
                      {canManageInventory && (
                        <button
                          className="primary-button"
                          type="button"
                          onClick={() =>
                            {
                              setEditingWarehouse(null);
                              setOpenForm((current) =>
                                current === "warehouse" && !editingWarehouse
                                  ? null
                                  : "warehouse",
                              );
                            }
                          }
                          disabled={isSubmitting}
                          aria-expanded={openForm === "warehouse"}
                        >
                          {openForm === "warehouse" && !editingWarehouse
                            ? "إغلاق النموذج"
                            : "إضافة مخزن"}
                        </button>
                      )}
                    </div>
                  </div>
                  {warehouses.length > 0 ? (
                    <div className="product-list">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">المخزن</th>
                            <th scope="col">الرمز</th>
                            <th scope="col">العنوان</th>
                            <th scope="col">الحالة</th>
                            {canManageInventory && <th scope="col">إجراءات</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {warehouses.map((warehouse) => (
                            <tr key={warehouse.id}>
                              <td><strong>{warehouse.name}</strong></td>
                              <td>{warehouse.code || "—"}</td>
                              <td>{warehouse.address || "—"}</td>
                              <td>{warehouse.is_active ? "نشط" : "متوقف"}</td>
                              {canManageInventory && (
                                <td>
                                  <button
                                    className="table-action"
                                    type="button"
                                    onClick={() => {
                                      setEditingWarehouse(warehouse);
                                      setOpenForm("warehouse");
                                    }}
                                    disabled={isSubmitting}
                                  >
                                    تعديل
                                  </button>
                                  <button
                                    className="table-action table-action-danger"
                                    type="button"
                                    onClick={() => void handleDeleteWarehouse(warehouse)}
                                    disabled={isSubmitting}
                                  >
                                    حذف
                                  </button>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty-inline">لم تتم إضافة مخازن لهذه الشركة بعد.</p>
                  )}

                  {canManageInventory && openForm === "warehouse" && (
                      <form
                        className="customer-form"
                        key={editingWarehouse?.id ?? "new-warehouse"}
                        onSubmit={handleCreateWarehouse}
                      >
                        <h3 className="form-section-title">
                          {editingWarehouse ? "تعديل بيانات المخزن" : "إضافة مخزن"}
                        </h3>
                        <div className="customer-form-row">
                          <div className="customer-field">
                            <label htmlFor="warehouse-name">اسم المخزن *</label>
                            <input
                              id="warehouse-name"
                              name="name"
                              type="text"
                              maxLength={160}
                              defaultValue={editingWarehouse?.name ?? ""}
                              required
                              disabled={isSubmitting}
                            />
                          </div>
                          <div className="customer-field">
                            <label htmlFor="warehouse-code">رمز المخزن</label>
                            <input
                              id="warehouse-code"
                              name="code"
                              type="text"
                              maxLength={64}
                              defaultValue={editingWarehouse?.code ?? ""}
                              disabled={isSubmitting}
                            />
                          </div>
                        </div>
                        <label htmlFor="warehouse-address">العنوان</label>
                        <input
                          id="warehouse-address"
                          name="address"
                          type="text"
                          maxLength={500}
                          defaultValue={editingWarehouse?.address ?? ""}
                          disabled={isSubmitting}
                        />
                        {editingWarehouse && (
                          <label className="warehouse-active-toggle">
                            <input
                              name="is_active"
                              type="checkbox"
                              defaultChecked={editingWarehouse.is_active}
                              disabled={isSubmitting}
                            />
                            المخزن نشط ويمكن استخدامه في الحركات الجديدة
                          </label>
                        )}
                        <div className="product-form-actions">
                          <button
                            className="primary-button"
                            type="submit"
                            disabled={isSubmitting}
                          >
                            {isSubmitting
                              ? "جارٍ الحفظ..."
                              : editingWarehouse
                                ? "حفظ التعديلات"
                                : "إضافة مخزن"}
                          </button>
                          {editingWarehouse && (
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => {
                                setEditingWarehouse(null);
                                setOpenForm(null);
                              }}
                              disabled={isSubmitting}
                            >
                              إلغاء
                            </button>
                          )}
                        </div>
                      </form>
                  )}
                  {canManageInventory && warehouses.length > 0 && products.length > 0 && (
                    <>
                      <div className="section-heading account-subheading">
                        <div>
                          <h2>تسجيل حركة</h2>
                          <p>أضف رصيدًا أو سجّل صرفًا من مخزن.</p>
                        </div>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() =>
                            setOpenForm((current) =>
                              current === "movement" ? null : "movement",
                            )
                          }
                          disabled={isSubmitting}
                          aria-expanded={openForm === "movement"}
                        >
                          {openForm === "movement" ? "إغلاق النموذج" : "حركة جديدة"}
                        </button>
                      </div>
                      {openForm === "movement" && (
                        <form
                          className="customer-form"
                          onSubmit={handleCreateStockMovement}
                        >
                          <h3 className="form-section-title">تسجيل حركة مخزون</h3>
                          <div className="customer-form-row">
                            <div className="customer-field">
                              <label htmlFor="movement-warehouse">المخزن *</label>
                              <select
                                id="movement-warehouse"
                                name="warehouse"
                                required
                                disabled={isSubmitting}
                              >
                                {warehouses
                                  .filter((warehouse) => warehouse.is_active)
                                  .map((warehouse) => (
                                    <option key={warehouse.id} value={warehouse.id}>
                                      {warehouse.name}
                                    </option>
                                  ))}
                              </select>
                            </div>
                            <div className="customer-field">
                              <label htmlFor="movement-product">المنتج *</label>
                              <select
                                id="movement-product"
                                name="product"
                                required
                                disabled={isSubmitting}
                              >
                                {products
                                  .filter((product) => product.is_active)
                                  .map((product) => (
                                    <option key={product.id} value={product.id}>
                                      {product.name}
                                    </option>
                                  ))}
                              </select>
                            </div>
                          </div>
                          <div className="customer-form-row">
                            <div className="customer-field">
                              <label htmlFor="movement-direction">نوع الحركة</label>
                              <select
                                id="movement-direction"
                                name="direction"
                                defaultValue="in"
                                disabled={isSubmitting}
                              >
                                <option value="in">إضافة رصيد</option>
                                <option value="out">صرف من الرصيد</option>
                              </select>
                            </div>
                            <div className="customer-field">
                              <label htmlFor="movement-quantity">الكمية *</label>
                              <input
                                id="movement-quantity"
                                name="quantity"
                                type="number"
                                min="0.001"
                                step="0.001"
                                required
                                disabled={isSubmitting}
                              />
                            </div>
                          </div>
                          <label htmlFor="movement-note">ملاحظة</label>
                          <input
                            id="movement-note"
                            name="note"
                            type="text"
                            maxLength={500}
                            disabled={isSubmitting}
                          />
                          <button
                            className="primary-button"
                            type="submit"
                            disabled={isSubmitting}
                          >
                            تسجيل الحركة
                          </button>
                        </form>
                      )}
                    </>
                  )}

                  <div className="section-heading account-subheading">
                    <div>
                      <h2>أرصدة المخزون</h2>
                      <p>الرصيد محسوب من سجل الحركات، وليس قيمة قابلة للتعديل اليدوي.</p>
                    </div>
                  </div>
                  {stockBalances.length > 0 ? (
                    <div className="product-list">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">المخزن</th>
                            <th scope="col">المنتج</th>
                            <th scope="col">SKU</th>
                            <th scope="col">الرصيد</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockBalances.map((balance) => (
                            <tr key={`${balance.warehouse_id}-${balance.product_id}`}>
                              <td>{balance.warehouse_name}</td>
                              <td><strong>{balance.product_name}</strong></td>
                              <td>{balance.product_sku || "—"}</td>
                              <td>{balance.quantity}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">▥</span>
                      <h3>لا توجد أرصدة مسجلة</h3>
                      <p>أضف مخزنًا ثم سجّل حركة إضافة رصيد لبدء متابعة المخزون.</p>
                    </div>
                  )}

                  <div className="section-heading account-subheading">
                    <div>
                      <h2>آخر الحركات</h2>
                      <p>الحركات المنشأة لا يمكن تعديلها أو حذفها.</p>
                    </div>
                    <span className="count-badge">{stockMovements.length}</span>
                  </div>
                  {stockMovements.length > 0 ? (
                    <div className="product-list">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">التاريخ</th>
                            <th scope="col">الاتجاه</th>
                            <th scope="col">المخزن</th>
                            <th scope="col">المنتج</th>
                            <th scope="col">الكمية</th>
                            <th scope="col">ملاحظة</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stockMovements.map((movement) => (
                            <tr key={movement.id}>
                              <td>
                                {new Intl.DateTimeFormat("ar-EG", {
                                  dateStyle: "short",
                                  timeStyle: "short",
                                }).format(new Date(movement.created_at))}
                              </td>
                              <td>
                                {movement.direction === "in" ? "إضافة" : "صرف"}
                              </td>
                              <td>
                                {warehouses.find(
                                  (warehouse) => warehouse.id === movement.warehouse,
                                )?.name ?? "—"}
                              </td>
                              <td>
                                {products.find((product) => product.id === movement.product)
                                  ?.name ?? "—"}
                              </td>
                              <td>{movement.quantity}</td>
                              <td>{movement.note || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty-inline">لم تُسجل حركات مخزون بعد.</p>
                  )}
                </>
              ) : organizationSection === "sales" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <button
                        className="back-button"
                        type="button"
                        onClick={() => {
                          setSelectedOrganizationId(null);
                          setSalesInvoices([]);
                          setError("");
                        }}
                      >
                        ← الشركات
                      </button>
                      <h2>المبيعات · {selectedOrganization.name}</h2>
                      <p>
                        فواتير صادرة وتحصيلات مرتبطة بها. إصدار الفاتورة يخصم
                        المنتجات من المخزن المحدد.
                      </p>
                    </div>
                    <div className="section-heading-actions">
                      <span className="count-badge">{salesInvoices.length} فاتورة</span>
                      {canCreateSalesInvoice && (
                        <button
                          className="primary-button"
                          type="button"
                          onClick={() =>
                            setOpenForm((current) =>
                              current === "invoice" ? null : "invoice",
                            )
                          }
                          disabled={isSubmitting}
                          aria-expanded={openForm === "invoice"}
                        >
                          {openForm === "invoice" ? "إغلاق النموذج" : "فاتورة جديدة"}
                        </button>
                      )}
                    </div>
                  </div>

                  <section className="sales-summary" aria-label="ملخص المبيعات">
                    <article className="sales-summary-card">
                      <span>عدد الفواتير</span>
                      <strong>{salesInvoices.length}</strong>
                    </article>
                    <article className="sales-summary-card">
                      <span>إجمالي المبيعات</span>
                      <strong>
                        {formatPrice(
                          String(salesInvoices.reduce(
                            (total, invoice) => total + Number(invoice.total),
                            0,
                          )),
                        )}{" "}
                        ج.م
                      </strong>
                    </article>
                    <article className="sales-summary-card">
                      <span>إجمالي المحصل</span>
                      <strong>
                        {formatPrice(
                          String(salesInvoices.reduce(
                            (total, invoice) => total + Number(invoice.amount_collected),
                            0,
                          )),
                        )}{" "}
                        ج.م
                      </strong>
                    </article>
                    <article className="sales-summary-card">
                      <span>المتبقي للتحصيل</span>
                      <strong>
                        {formatPrice(
                          String(salesInvoices.reduce(
                            (total, invoice) => total + Number(invoice.balance_due),
                            0,
                          )),
                        )}{" "}
                        ج.م
                      </strong>
                    </article>
                  </section>

                  {canCreateSalesInvoice && openForm === "invoice" ? (
                    <form className="customer-form invoice-form" onSubmit={handleCreateInvoice}>
                      <div className="section-heading account-subheading">
                        <div>
                          <h2>إصدار فاتورة بيع</h2>
                          <p>
                            الأسعار والإجمالي يتحقق منها الخادم. الضريبة غير
                            مشمولة في هذه النسخة الأولية.
                          </p>
                        </div>
                      </div>
                      <div className="customer-form-row">
                        <div className="customer-field">
                          <label htmlFor="invoice-customer">العميل *</label>
                          <select
                            id="invoice-customer"
                            name="customer"
                            required
                            defaultValue=""
                            disabled={isSubmitting || customers.length === 0}
                          >
                            <option value="" disabled>اختر العميل</option>
                            {customers.map((customer) => (
                              <option key={customer.id} value={customer.id}>
                                {customer.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="customer-field">
                          <label htmlFor="invoice-warehouse">المخزن *</label>
                          <select
                            id="invoice-warehouse"
                            name="warehouse"
                            required
                            defaultValue=""
                            disabled={isSubmitting || warehouses.length === 0}
                          >
                            <option value="" disabled>اختر المخزن</option>
                            {warehouses.filter((warehouse) => warehouse.is_active).map((warehouse) => (
                              <option key={warehouse.id} value={warehouse.id}>
                                {warehouse.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="invoice-lines-heading">
                        <h3>بنود الفاتورة</h3>
                        <button
                          className="table-action"
                          type="button"
                          onClick={() =>
                            setInvoiceLines((current) => [
                              ...current,
                              { productId: "", quantity: "1.000", unitPrice: "0.00" },
                            ])
                          }
                          disabled={isSubmitting}
                        >
                          إضافة بند
                        </button>
                      </div>
                      <div className="invoice-draft-lines">
                        {invoiceLines.map((line, index) => (
                          <div className="invoice-line-row" key={index}>
                            <div className="customer-field">
                              <label htmlFor={`invoice-product-${index}`}>المنتج / الخدمة *</label>
                              <select
                                id={`invoice-product-${index}`}
                                required
                                value={line.productId}
                                disabled={isSubmitting || products.length === 0}
                                onChange={(event) => {
                                  const productId = event.target.value;
                                  const selectedProduct = products.find(
                                    (product) => product.id === productId,
                                  );
                                  setInvoiceLines((current) =>
                                    current.map((draft, draftIndex) =>
                                      draftIndex === index
                                        ? {
                                            ...draft,
                                            productId,
                                            unitPrice: selectedProduct?.sale_price ?? "0.00",
                                          }
                                        : draft,
                                    ),
                                  );
                                }}
                              >
                                <option value="" disabled>اختر المنتج</option>
                                {products.filter((product) => product.is_active).map((product) => (
                                  <option key={product.id} value={product.id}>
                                    {product.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="customer-field">
                              <label htmlFor={`invoice-quantity-${index}`}>الكمية *</label>
                              <input
                                id={`invoice-quantity-${index}`}
                                type="number"
                                min="0.001"
                                step="0.001"
                                required
                                value={line.quantity}
                                disabled={isSubmitting}
                                onChange={(event) =>
                                  setInvoiceLines((current) =>
                                    current.map((draft, draftIndex) =>
                                      draftIndex === index
                                        ? { ...draft, quantity: event.target.value }
                                        : draft,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <div className="customer-field">
                              <label htmlFor={`invoice-price-${index}`}>سعر الوحدة *</label>
                              <input
                                id={`invoice-price-${index}`}
                                type="number"
                                min="0"
                                step="0.01"
                                required
                                value={line.unitPrice}
                                disabled={isSubmitting}
                                onChange={(event) =>
                                  setInvoiceLines((current) =>
                                    current.map((draft, draftIndex) =>
                                      draftIndex === index
                                        ? { ...draft, unitPrice: event.target.value }
                                        : draft,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <button
                              className="table-action invoice-remove-line"
                              type="button"
                              aria-label="حذف البند"
                              onClick={() =>
                                setInvoiceLines((current) =>
                                  current.filter((_, lineIndex) => lineIndex !== index),
                                )
                              }
                              disabled={isSubmitting || invoiceLines.length === 1}
                            >
                              حذف
                            </button>
                          </div>
                        ))}
                      </div>
                      {(customers.length === 0 || warehouses.length === 0 || products.length === 0) && (
                        <p className="field-hint" role="status">
                          لإصدار فاتورة، أضف عميلًا ومنتجًا ومخزنًا أولًا.
                        </p>
                      )}
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={
                          isSubmitting ||
                          customers.length === 0 ||
                          warehouses.filter((warehouse) => warehouse.is_active).length === 0 ||
                          products.filter((product) => product.is_active).length === 0
                        }
                      >
                        {isSubmitting ? "جارٍ إصدار الفاتورة..." : "إصدار الفاتورة"}
                      </button>
                    </form>
                  ) : canManageSales ? (
                    <div className="empty-inline">
                      يلزم صلاحية قراءة العملاء والمنتجات والمخزون لإصدار فاتورة من هذه الشاشة.
                    </div>
                  ) : null}

                  <div className="section-heading account-subheading">
                    <div>
                      <h2>فواتير البيع والتحصيل</h2>
                      <p>ملخص المبيعات والأرصدة المستحقة لهذه الشركة.</p>
                    </div>
                  </div>
                  {salesInvoices.length > 0 ? (
                    <div className="product-list">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">رقم الفاتورة</th>
                            <th scope="col">التاريخ والعميل</th>
                            <th scope="col">الإجمالي</th>
                            <th scope="col">المحصل</th>
                            <th scope="col">المتبقي</th>
                            <th scope="col">الحالة / الإجراء</th>
                          </tr>
                        </thead>
                        <tbody>
                          {salesInvoices.map((invoice) => {
                            const isPaid = Number(invoice.balance_due) <= 0;
                            return (
                              <Fragment key={invoice.id}>
                                <tr>
                                  <td>
                                    <strong>{invoice.number}</strong>
                                    <span className="table-subtext">{invoice.warehouse_name}</span>
                                    <span className="table-subtext" dir="rtl">
                                      {invoice.lines
                                        .map((line) => `${line.product_name} × ${line.quantity}`)
                                        .join("، ")}
                                    </span>
                                  </td>
                                  <td>
                                    {new Intl.DateTimeFormat("ar-EG", {
                                      dateStyle: "medium",
                                    }).format(new Date(invoice.issue_date))}
                                    <span className="table-subtext" dir="rtl">
                                      {invoice.customer_name}
                                    </span>
                                  </td>
                                  <td>{formatPrice(invoice.total)} ج.م</td>
                                  <td>{formatPrice(invoice.amount_collected)} ج.م</td>
                                  <td>{formatPrice(invoice.balance_due)} ج.م</td>
                                  <td>
                                    <span className={`invoice-status ${isPaid ? "invoice-status-paid" : "invoice-status-due"}`}>
                                      {isPaid ? "مسددة" : "مستحق"}
                                    </span>
                                    {((canManageSales && !isPaid) || invoice.payments.length > 0) && (
                                      <button
                                        className="table-action"
                                        type="button"
                                        onClick={() =>
                                          setCollectingInvoiceId((current) =>
                                            current === invoice.id ? null : invoice.id,
                                          )
                                        }
                                        disabled={isSubmitting}
                                      >
                                        {canManageSales && !isPaid
                                          ? "تسجيل تحصيل"
                                          : "عرض التحصيلات"}
                                      </button>
                                    )}
                                  </td>
                                </tr>
                                {collectingInvoiceId === invoice.id &&
                                  ((canManageSales && !isPaid) || invoice.payments.length > 0) && (
                                  <tr>
                                    <td colSpan={6}>
                                      {canManageSales && !isPaid && (
                                        <form
                                          className="payment-form"
                                          onSubmit={(event) =>
                                            void handleCollectPayment(event, invoice.id)
                                          }
                                        >
                                          <label>
                                            المبلغ *
                                            <input
                                              name="amount"
                                              type="number"
                                              min="0.01"
                                              max={invoice.balance_due}
                                              step="0.01"
                                              defaultValue={invoice.balance_due}
                                              required
                                              disabled={isSubmitting}
                                            />
                                          </label>
                                          <label>
                                            طريقة التحصيل
                                            <select name="method" defaultValue="cash" disabled={isSubmitting}>
                                              <option value="cash">نقدي</option>
                                              <option value="bank">تحويل بنكي</option>
                                              <option value="card">بطاقة</option>
                                            </select>
                                          </label>
                                          <label>
                                            ملاحظة
                                            <input name="note" type="text" maxLength={500} disabled={isSubmitting} />
                                          </label>
                                          <button className="primary-button" type="submit" disabled={isSubmitting}>
                                            حفظ التحصيل
                                          </button>
                                        </form>
                                      )}
                                      {invoice.payments.length > 0 && (
                                        <div className="payment-history">
                                          {invoice.payments.map((payment) => (
                                            <span key={payment.id}>
                                              {formatPrice(payment.amount)} ج.م ·{" "}
                                              {payment.method === "cash"
                                                ? "نقدي"
                                                : payment.method === "bank"
                                                  ? "تحويل بنكي"
                                                  : "بطاقة"}
                                              {" · "}
                                              {new Intl.DateTimeFormat("ar-EG", {
                                                dateStyle: "short",
                                                timeStyle: "short",
                                              }).format(new Date(payment.collected_at))}
                                              {payment.note && ` · ${payment.note}`}
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                    </td>
                                  </tr>
                                )}
                              </Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <span className="empty-state-icon">▧</span>
                      <h3>لا توجد فواتير بيع بعد</h3>
                      <p>أصدر أول فاتورة بعد إضافة عميل ومخزن ورصيد متاح من المنتجات.</p>
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
              ) : null}
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
                <select
                  name="business_type"
                  aria-label="نوع النشاط"
                  defaultValue="company"
                  disabled={isSubmitting}
                >
                  <option value="company">شركة / نشاط تجاري</option>
                  <option value="restaurant">مطعم</option>
                </select>
                <select
                  name="country_code"
                  aria-label="دولة النشاط"
                  defaultValue="EG"
                  disabled={isSubmitting}
                >
                  <option value="EG">مصر</option>
                  <option value="SA">السعودية</option>
                </select>
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "جارٍ الحفظ..." : "إضافة منشأة"}
                </button>
              </form>

              {organizations.length > 0 ? (
                <div className="organization-list">
                  {organizations.map((organization) => (
                    <article className="organization-card" key={organization.id}>
                      <span className="organization-icon">ش</span>
                      <div>
                        {editingOrganization?.id === organization.id ? (
                          <form
                            className="organization-inline-edit"
                            onSubmit={(event) =>
                              void handleUpdateOrganization(event, organization)
                            }
                          >
                            <label
                              className="visually-hidden"
                              htmlFor={`organization-name-${organization.id}`}
                            >
                              اسم الشركة
                            </label>
                            <input
                              id={`organization-name-${organization.id}`}
                              name="name"
                              type="text"
                              maxLength={160}
                              defaultValue={organization.name}
                              required
                              disabled={isSubmitting}
                            />
                            <button
                              className="secondary-button"
                              type="submit"
                              disabled={isSubmitting}
                            >
                              حفظ
                            </button>
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => setEditingOrganization(null)}
                              disabled={isSubmitting}
                            >
                              إلغاء
                            </button>
                          </form>
                        ) : (
                          <>
                            <h3>{organization.name}</h3>
                            <p>
                              {organization.business_type === "restaurant" ? "مطعم" : "شركة / نشاط تجاري"}
                              {" · "}
                              {organization.country_code === "SA" ? "السعودية" : "مصر"}
                              {" · عضويتك مفعّلة"}
                            </p>
                          </>
                        )}
                      </div>
                      <div className="organization-actions">
                        {user?.memberships
                          .find((membership) => membership.organizationId === organization.id)
                          ?.permissions.includes("organization.manage") && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() =>
                              setEditingOrganization((current) =>
                                current?.id === organization.id ? null : organization,
                              )
                            }
                            disabled={isSubmitting}
                          >
                            تعديل الشركة
                          </button>
                        )}
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
                          ?.permissions.includes("inventory.read") && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void handleOpenInventory(organization)}
                            disabled={isSubmitting}
                          >
                            إدارة المخزون
                          </button>
                        )}
                        {user?.memberships
                          .find((membership) => membership.organizationId === organization.id)
                          ?.permissions.includes("organization.manage") && (
                          <button
                            className="secondary-button table-danger-button"
                            type="button"
                            onClick={() => void handleDeleteOrganization(organization)}
                            disabled={isSubmitting}
                          >
                            حذف الشركة
                          </button>
                        )}
                        {user?.memberships
                          .find((membership) => membership.organizationId === organization.id)
                          ?.permissions.includes("sales.read") && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void handleOpenSales(organization)}
                            disabled={isSubmitting}
                          >
                            فواتير المبيعات
                          </button>
                        )}
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
          نسق لإدارة الأعمال <span>·</span> منصة تشغيل موحدة
        </footer>
      </section>
    </main>
  );
}
