"use client";

import { useEffect, useMemo, useState } from "react";
import { Edit2, Plus, Trash2, X } from "lucide-react";

import { apiFetch, setSelectedAcademicSessionId } from "@/lib/api";
import type { FieldConfig } from "@/types";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";

type Item = Record<string, string | number | boolean | null> & { id: number };
type LookupItem = Record<string, string | number | boolean | null> & { id?: number };

type Props = {
  title: string;
  description: string;
  endpoint: string;
  fields: FieldConfig[];
};

function defaultForm(fields: FieldConfig[]) {
  return fields.reduce<Record<string, string | boolean>>((acc, field) => {
    acc[field.name] = field.type === "checkbox" ? false : "";
    return acc;
  }, {});
}

function formatCellValue(value: string | number | boolean | null | undefined) {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return String(value);
}

function isAcademicSessionEndpoint(endpoint: string) {
  return endpoint.replace(/\/+$/, "") === "/academic-sessions";
}

function hardReloadAfterSessionChange(sessionId: number | string) {
  setSelectedAcademicSessionId(sessionId);
  window.setTimeout(() => window.location.reload(), 80);
}

export default function CrudManager({
  title,
  description,
  endpoint,
  fields,
}: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [form, setForm] = useState<Record<string, string | boolean>>(
    defaultForm(fields)
  );
  const [editing, setEditing] = useState<Item | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [lookups, setLookups] = useState<Record<string, LookupItem[]>>({});

  // FIX:
  // Earlier code manually added "is_active" at the end.
  // But some pages already pass "is_active" in fields.
  // This caused duplicate columns: ["id", ..., "is_active", "is_active"]
  const visibleColumns = useMemo(() => {
    return Array.from(new Set(["id", ...fields.map((field) => field.name)]));
  }, [fields]);

  const selectFields = useMemo(() => fields.filter((field) => field.type === "select" && field.optionsEndpoint), [fields]);

  const loadLookups = async () => {
    if (selectFields.length === 0) return;

    const next: Record<string, LookupItem[]> = {};

    await Promise.all(
      selectFields.map(async (field) => {
        if (!field.optionsEndpoint) return;
        try {
          next[field.name] = await apiFetch<LookupItem[]>(field.optionsEndpoint);
        } catch {
          next[field.name] = [];
        }
      })
    );

    setLookups(next);
  };

  const getSelectOptions = (field: FieldConfig) => {
    if (field.options?.length) return field.options;

    const valueKey = field.optionValueKey || "id";
    const labelKey = field.optionLabelKey || "name";

    return (lookups[field.name] || []).map((item) => ({
      value: item[valueKey] as string | number,
      label: String(item[labelKey] ?? item[valueKey] ?? ""),
    }));
  };

  const isNumberPayloadField = (field: FieldConfig) => {
    return field.type === "number" || field.valueType === "number" || field.name.endsWith("_id");
  };

  const loadItems = async () => {
    setLoading(true);
    setError("");

    try {
      const data = await apiFetch<Item[]>(endpoint);
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint]);

  useEffect(() => {
    loadLookups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectFields]);

  const reset = () => {
    setForm(defaultForm(fields));
    setEditing(null);
  };

  const preparePayload = () => {
    const payload: Record<string, string | number | boolean | null> = {};

    for (const field of fields) {
      const value = form[field.name];

      if (isNumberPayloadField(field)) {
        payload[field.name] = value === "" ? null : Number(value);
      } else if (field.type === "checkbox") {
        payload[field.name] = Boolean(value);
      } else {
        payload[field.name] = value === "" ? null : String(value);
      }
    }

    return payload;
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();

    setSaving(true);
    setError("");

    try {
      const payload = preparePayload();

      let savedItem: Item | null = null;

      if (editing) {
        savedItem = await apiFetch<Item>(`${endpoint}/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        savedItem = await apiFetch<Item>(endpoint, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      reset();

      if (isAcademicSessionEndpoint(endpoint) && savedItem?.id) {
        hardReloadAfterSessionChange(savedItem.id);
        return;
      }

      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (item: Item) => {
    setEditing(item);

    const next = defaultForm(fields);

    for (const field of fields) {
      const value = item[field.name];

      next[field.name] =
        field.type === "checkbox"
          ? Boolean(value)
          : value == null
            ? ""
            : String(value);
    }

    setForm(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const remove = async (item: Item) => {
    if (!confirm("Delete this record?")) return;

    setError("");

    try {
      await apiFetch(`${endpoint}/${item.id}`, {
        method: "DELETE",
      });

      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <AppSection title={title} description={description}>
      <Card>
        <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
          {fields.map((field) => (
            <div
              key={`field-${field.name}`}
              className={field.type === "textarea" ? "md:col-span-2" : ""}
            >
              <Label>{field.label}</Label>

              {field.type === "select" ? (
                <select
                  value={String(form[field.name] ?? "")}
                  required={field.required}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400"
                  style={{ borderRadius: "var(--erp-border-radius, 16px)" }}
                >
                  <option value="">{field.emptyLabel || `Select ${field.label.toLowerCase()}`}</option>
                  {getSelectOptions(field).map((option) => (
                    <option key={`${field.name}-${option.value}`} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "textarea" ? (
                <Textarea
                  value={String(form[field.name] ?? "")}
                  placeholder={field.placeholder}
                  required={field.required}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                />
              ) : field.type === "checkbox" ? (
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(form[field.name])}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        [field.name]: e.target.checked,
                      }))
                    }
                  />
                  {field.label}
                </label>
              ) : (
                <Input
                  type={field.type || "text"}
                  value={String(form[field.name] ?? "")}
                  placeholder={field.placeholder}
                  required={field.required}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                />
              )}
            </div>
          ))}

          <div className="flex items-end gap-2 md:col-span-2">
            <Button type="submit" disabled={saving}>
              <span className="inline-flex items-center gap-2">
                <Plus size={16} />
                {editing ? "Update" : "Create"}
              </span>
            </Button>

            {editing && (
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
              >
                <X size={16} />
                Cancel
              </button>
            )}
          </div>
        </form>

        {error && (
          <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </Card>

      <Card className="mt-6 overflow-hidden p-0">
        {loading ? (
          <p className="p-5 text-sm text-slate-500">Loading...</p>
        ) : items.length === 0 ? (
          <p className="p-5 text-sm text-slate-500">No records yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                <tr>
                  {visibleColumns.map((column) => (
                    <th
                      key={`header-${column}`}
                      className="px-4 py-3"
                    >
                      {column.replaceAll("_", " ")}
                    </th>
                  ))}

                  <th key="header-actions" className="px-4 py-3">
                    Actions
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={`row-${item.id}`} className="hover:bg-slate-50">
                    {visibleColumns.map((column) => (
                      <td
                        key={`cell-${item.id}-${column}`}
                        className="px-4 py-3 text-slate-700"
                      >
                        {formatCellValue(item[column])}
                      </td>
                    ))}

                    <td
                      key={`actions-${item.id}`}
                      className="flex gap-2 px-4 py-3"
                    >
                      <button
                        onClick={() => startEdit(item)}
                        className="rounded-lg border border-slate-200 p-2 hover:bg-slate-100"
                      >
                        <Edit2 size={15} />
                      </button>

                      <button
                        onClick={() => remove(item)}
                        className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </AppSection>
  );
}

export function AppSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>

      {children}
    </div>
  );
}