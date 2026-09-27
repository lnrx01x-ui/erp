import { FormEvent, Fragment, useCallback, useEffect, useState } from "react";

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
type SessionStatus = { authenticated: boolean };
type OrganizationSection =
  | "customers"
  | "products"
  | "members"
  | "roles"
  | "inventory"
  | "sales";

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
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [productCategories, setProductCategories] = useState<ProductCategory[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [stockBalances, setStockBalances] = useState<StockBalance[]>([]);
  const [salesInvoices, setSalesInvoices] = useState<SalesInvoice[]>([]);
  const [invoiceLines, setInvoiceLines] = useState<InvoiceDraftLine[]>([
    { productId: "", quantity: "1.000", unitPrice: "0.00" },
  ]);
  const [collectingInvoiceId, setCollectingInvoiceId] = useState<string | null>(null);
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
      await Promise.all([
        loadProducts(organization.id),
        loadProductCategories(organization.id),
      ]);
      setSelectedOrganizationId(organization.id);
      setIsAccountView(false);
      setOrganizationSection("products");
      setEditingProduct(null);
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
      setNotice("تمت إضافة العميل.");
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
        `/api/v1/organizations/${encodeURIComponent(selectedOrganizationId)}/warehouses/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            name: form.get("name"),
            code: form.get("code"),
            address: form.get("address"),
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const warehouse: Warehouse = await response.json();
      setWarehouses((current) =>
        [...current, warehouse].sort((first, second) =>
          first.name.localeCompare(second.name, "ar"),
        ),
      );
      formElement.reset();
      setNotice("تمت إضافة المخزن.");
    } catch (caught: unknown) {
      setError(
        caught instanceof Error ? caught.message : "تعذر إضافة المخزن.",
      );
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
  const canManageRoles =
    selectedOrganizationMembership?.permissions.includes("roles.manage") ?? false;
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
          <span className="brand-mark">ن</span>
          <span>نسق</span>
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

              {canManageCustomers && (
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
                      </tr>
                    </thead>
                    <tbody>
                      {customers.map((customer) => (
                        <tr key={customer.id}>
                          <td><strong>{customer.name}</strong></td>
                          <td>{customer.phone || "—"}</td>
                          <td>{customer.email || "—"}</td>
                          <td>{customer.address || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">◇</span>
                  <h3>لسه مافيش عملاء</h3>
                  <p>
                    {canManageCustomers
                      ? "أضف أول عميل للشركة من النموذج أعلاه."
                      : "لا توجد سجلات عملاء لهذه الشركة بعد."}
                  </p>
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
                    <span className="count-badge">{products.length}</span>
                  </div>

                  {canManageProducts && (
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

                  {canManageProducts && <form
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
                          onClick={() => setEditingProduct(null)}
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
                                    onClick={() => setEditingProduct(product)}
                                    disabled={isSubmitting}
                                  >
                                    تعديل
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
                          ? "أضف أول منتج أو خدمة للكتالوج من النموذج أعلاه."
                          : "لا توجد سجلات منتجات لهذه الشركة بعد."}
                      </p>
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
                    <span className="count-badge">{warehouses.length}</span>
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
                          </tr>
                        </thead>
                        <tbody>
                          {warehouses.map((warehouse) => (
                            <tr key={warehouse.id}>
                              <td><strong>{warehouse.name}</strong></td>
                              <td>{warehouse.code || "—"}</td>
                              <td>{warehouse.address || "—"}</td>
                              <td>{warehouse.is_active ? "نشط" : "متوقف"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty-inline">لم تتم إضافة مخازن لهذه الشركة بعد.</p>
                  )}

                  {canManageInventory && (
                    <>
                      <form
                        className="customer-form"
                        onSubmit={handleCreateWarehouse}
                      >
                        <h3 className="form-section-title">إضافة مخزن</h3>
                        <div className="customer-form-row">
                          <div className="customer-field">
                            <label htmlFor="warehouse-name">اسم المخزن *</label>
                            <input
                              id="warehouse-name"
                              name="name"
                              type="text"
                              maxLength={160}
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
                          disabled={isSubmitting}
                        />
                        <button
                          className="primary-button"
                          type="submit"
                          disabled={isSubmitting}
                        >
                          إضافة مخزن
                        </button>
                      </form>

                      {warehouses.length > 0 && products.length > 0 && (
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
                    <span className="count-badge">{salesInvoices.length} فاتورة</span>
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

                  {canCreateSalesInvoice ? (
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
          نسق لإدارة الأعمال <span>·</span> منصة تشغيل موحدة
        </footer>
      </section>
    </main>
  );
}
