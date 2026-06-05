"use client";

import { useEffect, useMemo, useState } from "react";
import { Palette, Sparkles, Upload } from "lucide-react";

import AppShell from "@/components/AppShell";
import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch, apiUpload, fileUrl } from "@/lib/api";
import {
  applyBrandingTheme,
  cacheBrandingTheme,
  BRANDING_PRESETS,
  buildLogoGeneratedTheme,
  extractDominantColorFromImage,
  normalizeBranding,
  presetLabel,
  readableTextColor,
} from "@/lib/branding";
import type { LogoUploadResponse, School, SchoolBranding } from "@/types";

type SchoolField = keyof School;
type BrandingField = keyof Pick<
  SchoolBranding,
  "primary_color" | "secondary_color" | "accent_color" | "sidebar_color" | "background_color" | "text_color"
>;

const colorFields: { key: BrandingField; label: string; help: string }[] = [
  { key: "primary_color", label: "Primary", help: "Buttons, highlights and active states" },
  { key: "secondary_color", label: "Secondary", help: "Strong headings and deep surfaces" },
  { key: "accent_color", label: "Accent", help: "Badges, small highlights and positive UI" },
  { key: "sidebar_color", label: "Sidebar", help: "Left navigation background" },
  { key: "background_color", label: "Background", help: "Main dashboard background" },
  { key: "text_color", label: "Text", help: "Default text color" },
];

function ColorField({
  label,
  help,
  value,
  onChange,
}: {
  label: string;
  help: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Label>{label}</Label>
          <p className="text-xs text-slate-500">{help}</p>
        </div>
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-12 cursor-pointer rounded-lg border border-slate-200 bg-white p-1"
          aria-label={`${label} color`}
        />
      </div>
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="mt-3 font-mono" />
    </div>
  );
}

export default function SchoolSettingsPage() {
  const [form, setForm] = useState<Partial<School>>({});
  const [branding, setBranding] = useState<Partial<SchoolBranding>>({});
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingBranding, setSavingBranding] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const activeBranding = useMemo(() => normalizeBranding(branding), [branding]);
  const logoPreviewUrl = fileUrl(activeBranding.logo_url || form.logo_url);
  const primaryText = readableTextColor(activeBranding.primary_color);

  useEffect(() => {
    Promise.all([apiFetch<School>("/schools/me"), apiFetch<SchoolBranding>("/schools/branding/me")])
      .then(([school, brandingData]) => {
        setForm(school);
        setBranding(brandingData);
        applyBrandingTheme(brandingData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load school settings"))
      .finally(() => setLoading(false));
  }, []);

  const updateSchool = (key: SchoolField, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const updateBranding = (key: BrandingField, value: string) => {
    setBranding((prev) => {
      const next = { ...prev, [key]: value, theme_source: "manual", preset_name: "custom" };
      applyBrandingTheme(next);
      return next;
    });
  };

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setMessage("");
    setError("");
    try {
      const data = await apiFetch<School>("/schools/me", { method: "PUT", body: JSON.stringify(form) });
      setForm(data);
      setMessage("School profile updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Profile update failed");
    } finally {
      setSavingProfile(false);
    }
  };

  const saveBranding = async (nextBranding: Partial<SchoolBranding> = branding) => {
    setSavingBranding(true);
    setMessage("");
    setError("");
    try {
      const payload = normalizeBranding(nextBranding);
      const data = await apiFetch<SchoolBranding>("/schools/branding/me", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setBranding(data);
      applyBrandingTheme(data);
      cacheBrandingTheme(data);
      setMessage("Branding and theme updated successfully.");
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Branding update failed");
      return null;
    } finally {
      setSavingBranding(false);
    }
  };

  const applyPreset = (presetKey: string) => {
    const preset = BRANDING_PRESETS[presetKey];
    if (!preset) return;
    setBranding((prev) => {
      const next = {
        ...prev,
        ...preset,
        logo_url: prev.logo_url,
        favicon_url: prev.favicon_url,
      };
      applyBrandingTheme(next);
      return next;
    });
  };

  const uploadLogo = async (file: File) => {
    setUploadingLogo(true);
    setMessage("");
    setError("");
    try {
      const dominantColor = await extractDominantColorFromImage(file);
      const generatedTheme = buildLogoGeneratedTheme(dominantColor, branding);
      const formData = new FormData();
      formData.append("file", file);
      const upload = await apiUpload<LogoUploadResponse>("/schools/branding/logo", formData, { method: "POST" });
      const nextBranding = { ...generatedTheme, logo_url: upload.logo_url, favicon_url: branding.favicon_url || null };
      setBranding(nextBranding);
      setForm((prev) => ({ ...prev, logo_url: upload.logo_url }));
      applyBrandingTheme(nextBranding);
      await saveBranding(nextBranding);
      setMessage("Logo uploaded and a logo-based theme was generated. You can still edit the colors manually.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logo upload failed");
    } finally {
      setUploadingLogo(false);
    }
  };

  return (
    <AppShell>
      <AppSection title="School Profile" description="Manage institution details, logo and per-school website theme.">
        {loading ? (
          <Card><p className="text-sm text-slate-500">Loading...</p></Card>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="space-y-5">
              <Card>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-xl p-2" style={{ background: "var(--erp-primary-soft)", color: "var(--erp-primary)" }}>
                    <Upload size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Logo Upload</h2>
                    <p className="text-xs text-slate-500">PNG, JPG, JPEG or WEBP. Max size: 3 MB.</p>
                  </div>
                </div>

                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <div className="flex h-24 w-24 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    {logoPreviewUrl ? (
                      <img src={logoPreviewUrl} alt="School logo preview" className="max-h-full max-w-full object-contain" />
                    ) : (
                      <span className="text-xs font-semibold text-slate-400">No Logo</span>
                    )}
                  </div>
                  <div className="flex-1">
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) uploadLogo(file);
                        e.currentTarget.value = "";
                      }}
                      className="block w-full cursor-pointer rounded-xl border border-slate-200 bg-white text-sm file:mr-3 file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700"
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      After upload, the system reads the logo color and suggests a matching theme automatically.
                    </p>
                    {uploadingLogo && <p className="mt-2 text-xs font-semibold" style={{ color: "var(--erp-primary)" }}>Uploading and generating theme...</p>}
                  </div>
                </div>
              </Card>

              <Card>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-xl p-2" style={{ background: "var(--erp-primary-soft)", color: "var(--erp-primary)" }}>
                    <Palette size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Theme Picker</h2>
                    <p className="text-xs text-slate-500">Choose a preset or customize colors manually.</p>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.keys(BRANDING_PRESETS).map((key) => {
                    const preset = BRANDING_PRESETS[key];
                    const active = activeBranding.preset_name === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => applyPreset(key)}
                        className={`rounded-2xl border p-3 text-left transition ${active ? "border-slate-900 shadow-sm" : "border-slate-200 hover:border-slate-300"}`}
                      >
                        <div className="mb-3 flex gap-1">
                          {[preset.primary_color, preset.secondary_color, preset.accent_color].map((color) => (
                            <span key={color} className="h-6 w-6 rounded-full border border-white shadow-sm" style={{ background: color }} />
                          ))}
                        </div>
                        <p className="text-sm font-bold text-slate-900">{presetLabel(key)}</p>
                        <p className="text-xs text-slate-500">{active ? "Currently selected" : "Click to preview"}</p>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {colorFields.map((field) => (
                    <ColorField
                      key={field.key}
                      label={field.label}
                      help={field.help}
                      value={String(activeBranding[field.key])}
                      onChange={(value) => updateBranding(field.key, value)}
                    />
                  ))}
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div>
                    <Label>Theme Mode</Label>
                    <select
                      value={activeBranding.theme_mode}
                      onChange={(e) => setBranding((prev) => ({ ...prev, theme_mode: e.target.value, theme_source: "manual" }))}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm"
                    >
                      <option value="light">Light</option>
                      <option value="dark">Dark</option>
                      <option value="auto">Auto</option>
                    </select>
                  </div>
                  <div>
                    <Label>Corner Roundness</Label>
                    <Input
                      type="number"
                      min={6}
                      max={28}
                      value={activeBranding.border_radius}
                      onChange={(e) => setBranding((prev) => ({ ...prev, border_radius: Number(e.target.value), theme_source: "manual", preset_name: "custom" }))}
                    />
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-3">
                  <Button type="button" onClick={() => saveBranding()} disabled={savingBranding || uploadingLogo}>
                    {savingBranding ? "Saving Theme..." : "Save Branding & Theme"}
                  </Button>
                  <Button type="button" onClick={() => applyPreset("professional_blue")} style={{ background: "#475569" }}>
                    Reset Preview
                  </Button>
                </div>
              </Card>
            </div>

            <div className="space-y-5">
              <Card>
                <div className="mb-4 flex items-center gap-2">
                  <div className="rounded-xl p-2" style={{ background: "var(--erp-primary-soft)", color: "var(--erp-primary)" }}>
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900">Live Preview</h2>
                    <p className="text-xs text-slate-500">This preview shows how the school dashboard will feel.</p>
                  </div>
                </div>

                <div className="overflow-hidden rounded-3xl border border-slate-200" style={{ background: activeBranding.background_color }}>
                  <div className="grid min-h-72 grid-cols-[120px_1fr]">
                    <div className="p-3 text-white" style={{ background: activeBranding.sidebar_color }}>
                      <div className="mb-5 flex items-center gap-2">
                        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white p-1 text-xs font-bold" style={{ color: activeBranding.primary_color }}>
                          {logoPreviewUrl ? <img src={logoPreviewUrl} alt="Logo preview" className="max-h-full max-w-full object-contain" /> : "ERP"}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-xs font-bold">{form.name || "School ERP"}</p>
                          <p className="text-[10px] text-white/45">#{form.school_code || "CODE"}</p>
                        </div>
                      </div>
                      {["Dashboard", "Students", "Fees"].map((item, index) => (
                        <div key={item} className="mb-2 rounded-xl px-2 py-2 text-[11px]" style={{ background: index === 0 ? activeBranding.primary_color : "transparent", color: index === 0 ? primaryText : "rgba(255,255,255,0.65)" }}>
                          {item}
                        </div>
                      ))}
                    </div>
                    <div className="p-4">
                      <div className="mb-4 flex items-center justify-between">
                        <div>
                          <p className="text-xs font-semibold" style={{ color: activeBranding.primary_color }}>Admin Dashboard</p>
                          <h3 className="text-lg font-bold" style={{ color: activeBranding.text_color }}>{form.name || "Your School"}</h3>
                        </div>
                        <button type="button" className="rounded-xl px-3 py-2 text-xs font-bold" style={{ background: activeBranding.primary_color, color: primaryText }}>
                          Add Student
                        </button>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {["Students", "Teachers", "Pending Fees", "Attendance"].map((item, index) => (
                          <div key={item} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                            <p className="text-xs text-slate-500">{item}</p>
                            <p className="text-xl font-black" style={{ color: index === 2 ? activeBranding.accent_color : activeBranding.text_color }}>
                              {index === 2 ? "₹24K" : index === 3 ? "92%" : index === 0 ? "320" : "28"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>

              <Card>
                <h2 className="mb-4 text-base font-bold text-slate-900">Basic Institution Details</h2>
                <form onSubmit={saveProfile} className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label>Name</Label>
                    <Input value={form.name || ""} onChange={(e) => updateSchool("name", e.target.value)} required />
                  </div>
                  <div>
                    <Label>School / College Code</Label>
                    <Input value={form.school_code || ""} onChange={(e) => updateSchool("school_code", e.target.value.toUpperCase())} />
                    <p className="mt-1 text-xs text-slate-500">Users need this code on login.</p>
                  </div>
                  <div>
                    <Label>Type</Label>
                    <Input value={form.institution_type || ""} onChange={(e) => updateSchool("institution_type", e.target.value)} />
                  </div>
                  <div>
                    <Label>Email</Label>
                    <Input type="email" value={form.email || ""} onChange={(e) => updateSchool("email", e.target.value)} />
                  </div>
                  <div>
                    <Label>Phone</Label>
                    <Input value={form.phone || ""} onChange={(e) => updateSchool("phone", e.target.value)} />
                  </div>
                  <div>
                    <Label>City</Label>
                    <Input value={form.city || ""} onChange={(e) => updateSchool("city", e.target.value)} />
                  </div>
                  <div>
                    <Label>State</Label>
                    <Input value={form.state || ""} onChange={(e) => updateSchool("state", e.target.value)} />
                  </div>
                  <div>
                    <Label>Country</Label>
                    <Input value={form.country || ""} onChange={(e) => updateSchool("country", e.target.value)} />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Address</Label>
                    <Textarea value={form.address || ""} onChange={(e) => updateSchool("address", e.target.value)} />
                  </div>
                  <div className="md:col-span-2">
                    <Button type="submit" disabled={savingProfile}>{savingProfile ? "Saving..." : "Save Profile"}</Button>
                  </div>
                </form>
              </Card>
            </div>

            {message && <p className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700 xl:col-span-2">{message}</p>}
            {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 xl:col-span-2">{error}</p>}
          </div>
        )}
      </AppSection>
    </AppShell>
  );
}
