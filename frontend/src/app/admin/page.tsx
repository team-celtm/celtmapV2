"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiBaseUrl } from "@/lib/api";
import type { ReadinessComponent, SubjectProgress } from "@/lib/celtm";
import { useTheme } from "@/contexts/ThemeContext";
import AppIcon from "@/components/AppIcon";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";
import { SubjectProgressCards } from "@/components/dashboard/SubjectProgressCards";
import ThemedSelect from "@/components/ThemedSelect";
import { motion } from "framer-motion";

interface AdminMe {
  id: string;
  email: string;
  role: "super_admin" | "institution_admin";
  institution_id?: string | null;
  department_id?: string | null;
  mfa_enabled?: boolean;
  mfa_required?: boolean;
}

interface Department {
  id: string;
  institution_id: string;
  name: string;
  head_name?: string | null;
  head_email?: string | null;
}

interface Institution {
  id: string;
  name: string;
  domain: string;
  departments: Department[];
}

interface StudentProgress {
  user_id: string;
  name: string;
  email: string;
  institution_name?: string | null;
  department_name?: string | null;
  readiness_score: number;
  resume_score?: number | null;
  assessment_score?: number | null;
  written_score?: number | null;
  credential_score?: number | null;
  readiness_components?: ReadinessComponent[];
  readiness_formula?: string | null;
  subject_progress?: SubjectProgress[];
  target_role?: string | null;
  strong_points: string[];
  weak_points: string[];
  institute_help: string[];
}

interface QuestionBankStatus {
  source: string;
  status: string;
  message: string;
  total_questions: number;
  mcq_count: number;
  descriptive_count: number;
  situational_count: number;
  metadata?: {
    subject_counts?: Record<string, number>;
    subject_type_counts?: Record<string, Record<string, number>>;
  };
}

interface AssessmentAssignment {
  id: string;
  title: string;
  department_id: string;
  category: string;
  question_type: string;
  question_set_id?: string | null;
  question_count?: number;
  mode: string;
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  status: string;
  missed?: boolean;
  terminated?: boolean;
  terminated_at?: string | null;
  terminated_by_email?: string | null;
  metadata?: Record<string, unknown>;
}

interface AdminAccount {
  id: string;
  email: string;
  role: "super_admin" | "institution_admin";
  institution_id?: string | null;
  department_id?: string | null;
  name: string;
  created_at?: string | null;
  updated_at?: string | null;
  last_password_reset_at?: string | null;
}

interface QuestionSet {
  id: string;
  title: string;
  source: string;
  category: string;
  question_type: string;
  question_count: number;
  type_counts?: Record<string, number>;
  created_at: string;
}

interface AdminMfaStatus {
  enabled: boolean;
  required: boolean;
  pending_enrollment: boolean;
  issuer: string;
  account: string;
}

type PopupData = Record<string, string | number | null | undefined>;

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error ? caught.message : fallback;
}

export default function AdminDashboard() {
  const router = useRouter();
  const { toggleTheme, isDarkMode } = useTheme();

  const [admin, setAdmin] = useState<AdminMe | null>(null);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [students, setStudents] = useState<StudentProgress[]>([]);
  const [questionBank, setQuestionBank] = useState<QuestionBankStatus | null>(null);
  const [assignments, setAssignments] = useState<AssessmentAssignment[]>([]);
  const [questionSets, setQuestionSets] = useState<QuestionSet[]>([]);
  const [adminAccounts, setAdminAccounts] = useState<AdminAccount[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<StudentProgress | null>(null);
  const [loadingStudentId, setLoadingStudentId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState<string | null>(null);
  const [isIngestingCsv, setIsIngestingCsv] = useState(false);
  const [isSyncingSupabase, setIsSyncingSupabase] = useState(false);
  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState(false);
  const [changePasswordForm, setChangePasswordForm] = useState({ current_password: "", new_password: "" });
  const [mfaStatus, setMfaStatus] = useState<AdminMfaStatus | null>(null);
  const [mfaEnrollment, setMfaEnrollment] = useState<{ secret: string; otpauth_url: string } | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaDisableCode, setMfaDisableCode] = useState("");
  const [isMfaWorking, setIsMfaWorking] = useState(false);
  const [institutionForm, setInstitutionForm] = useState({ name: "", domain: "" });
  const [departmentForm, setDepartmentForm] = useState({ institution_id: "", name: "", head_name: "", head_email: "" });
  const [headForm, setHeadForm] = useState({ institution_id: "", department_id: "", name: "", email: "", password: "" });
  const [courseForm, setCourseForm] = useState({ title: "", description: "", institution_id: "" });
  const [questionForm, setQuestionForm] = useState({ dimension: "Algorithms", difficulty: "Basic", question_type: "MCQ", scenario: "", question_text: "", options: "", correct_answer: "A", explanation: "" });
  const [assignmentForm, setAssignmentForm] = useState({
    title: "",
    department_id: "",
    category: "Algorithms",
    question_type: "MCQ",
    question_set_id: "",
    mode: "quick",
    starts_at: "",
    ends_at: "",
    duration_minutes: "30",
    instructions: "",
  });
  const [assignUploadedCsv, setAssignUploadedCsv] = useState(false);
  const [csvAssignmentForm, setCsvAssignmentForm] = useState({
    title: "",
    department_id: "",
    starts_at: "",
    ends_at: "",
    duration_minutes: "30",
    mode: "quick",
    instructions: "",
  });
  const [resetForm, setResetForm] = useState({ account_id: "", password: "" });
  const [createdPopup, setCreatedPopup] = useState<{ title: string; data: PopupData } | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  const token = typeof window !== "undefined" ? window.sessionStorage.getItem("adminToken") : null;
  const authHeaders = useMemo(() => ({
    Authorization: `Bearer ${token}`,
  }), [token]);

  const authedFetch = async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!token) {
      router.push("/login");
      throw new Error("Admin token missing.");
    }
    const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...authHeaders,
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(init.headers || {}),
      },
    });

    // Check if the response is a blob (for PDF export or CSV export)
    const contentType = response.headers.get("content-type");
    if (contentType && (contentType.includes("application/pdf") || contentType.includes("text/csv"))) {
      if (!response.ok) throw new Error("Export failed");
      return response.blob() as unknown as T;
    }

    const text = await response.text();
    const payload: unknown = text ? JSON.parse(text) : null;
    if (!response.ok) {
      const detail = payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail)
        : "Admin request failed.";
      throw new Error(detail);
    }
    return payload as T;
  };

  const load = async (nextSearch = search) => {
    try {
      setError("");
      const [me, inst, studentRows, bank, assignmentRows, questionSetRows, adminAccountRows, nextMfaStatus] = await Promise.all([
        authedFetch<AdminMe>("/admin/me"),
        authedFetch<Institution[]>("/admin/institutions"),
        authedFetch<StudentProgress[]>(`/admin/students${nextSearch ? `?search=${encodeURIComponent(nextSearch)}` : ""}`),
        authedFetch<QuestionBankStatus>("/question-bank/status"),
        authedFetch<AssessmentAssignment[]>("/admin/assessment-assignments").catch(() => []),
        authedFetch<QuestionSet[]>("/admin/question-sets").catch(() => []),
        authedFetch<AdminAccount[]>("/admin/admin-accounts").catch(() => []),
        authedFetch<AdminMfaStatus>("/admin/mfa").catch(() => null),
      ]);
      setAdmin(me);
      setInstitutions(inst);
      setStudents(studentRows);
      setQuestionBank(bank);
      setAssignments(assignmentRows);
      setQuestionSets(questionSetRows);
      setAdminAccounts(adminAccountRows);
      setMfaStatus(nextMfaStatus);
      if (inst[0]) {
        setDepartmentForm((current) => current.institution_id ? current : { ...current, institution_id: inst[0].id });
        setHeadForm((current) => current.institution_id ? current : { ...current, institution_id: inst[0].id });
      }
      const availableDepartments = inst.flatMap((item) => item.departments);
      const defaultDepartment =
        availableDepartments.find((dept) => dept.id === me.department_id) ??
        availableDepartments.find((dept) => dept.institution_id === me.institution_id) ??
        availableDepartments[0];
      if (defaultDepartment) {
        setAssignmentForm((current) => current.department_id ? current : { ...current, department_id: defaultDepartment.id });
        setCsvAssignmentForm((current) => current.department_id ? current : { ...current, department_id: defaultDepartment.id });
      }
    } catch (caught) {
      const message = errorMessage(caught, "Failed to load admin dashboard.");
      setError(message);
      if (message.includes("token")) router.push("/login");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedInstitution = institutions.find((item) => item.id === headForm.institution_id) ?? institutions[0];
  const isSuperAdmin = admin?.role === "super_admin";
  const subjectOptions = useMemo(() => {
    const subjectTypeCounts = questionBank?.metadata?.subject_type_counts ?? {};
    const subjectCounts = questionBank?.metadata?.subject_counts ?? {};
    const subjects = Object.keys(subjectTypeCounts).length ? Object.keys(subjectTypeCounts) : Object.keys(subjectCounts);
    return subjects
      .filter((subject) => subject && subject !== "General Knowledge")
      .sort((left, right) => left.localeCompare(right));
  }, [questionBank]);
  const assignableDepartments = institutions
    .filter((item) => isSuperAdmin || !admin?.institution_id || item.id === admin.institution_id)
    .flatMap((item) => item.departments
      .filter((dept) => isSuperAdmin || !admin?.department_id || dept.id === admin.department_id)
      .map((dept) => ({ value: dept.id, label: `${item.name} / ${dept.name}` })));

  useEffect(() => {
    if (!subjectOptions.length) return;
    setQuestionForm((current) =>
      subjectOptions.includes(current.dimension) ? current : { ...current, dimension: subjectOptions[0] },
    );
    setAssignmentForm((current) =>
      subjectOptions.includes(current.category) ? current : { ...current, category: subjectOptions[0] },
    );
  }, [subjectOptions]);

  const logout = () => {
    window.sessionStorage.removeItem("adminToken");
    window.sessionStorage.removeItem("adminRole");
    window.localStorage.removeItem("adminToken");
    window.localStorage.removeItem("adminRole");
    router.push("/login");
  };

  const openStudentDetail = async (student: StudentProgress) => {
    setSelectedStudent(student);
    setLoadingStudentId(student.user_id);
    try {
      const detail = await authedFetch<StudentProgress>(`/admin/students/${student.user_id}`);
      setSelectedStudent((current) =>
        current?.user_id === student.user_id ? { ...current, ...detail } : current,
      );
    } catch (caught) {
      setError(errorMessage(caught, "Failed to load student detail."));
    } finally {
      setLoadingStudentId((current) => (current === student.user_id ? null : current));
    }
  };

  const downloadPassport = async (userId: string, name: string) => {
    try {
      setIsExporting(userId);
      const blob = await authedFetch<Blob>(`/admin/students/${userId}/passport.pdf`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_passport.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      setToast(`Downloaded passport for ${name}`);
    } catch (caught) {
      setError(errorMessage(caught, "Failed to download passport."));
    } finally {
      setIsExporting(null);
    }
  };

  const exportStudentsReport = async (format: "csv" | "pdf") => {
    try {
      setIsExporting(`students-${format}`);
      setToast(`Exporting ${format.toUpperCase()}...`);
      const blob = await authedFetch<Blob>(`/admin/students/export.${format}`);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `students-export-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      setToast(`${format.toUpperCase()} export completed.`);
    } catch (caught) {
      setError(errorMessage(caught, `Failed to export students ${format.toUpperCase()}.`));
    } finally {
      setIsExporting(null);
    }
  };

  const exportStudentsCsv = () => exportStudentsReport("csv");
  const exportStudentsPdf = () => exportStudentsReport("pdf");

  const submitInstitution = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await authedFetch("/admin/institutions", {
        method: "POST",
        body: JSON.stringify(institutionForm),
      });
      setCreatedPopup({
        title: "Institution Created",
        data: { name: institutionForm.name, domain: institutionForm.domain || "N/A" }
      });
      setInstitutionForm({ name: "", domain: "" });
      setToast("Institution added.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to add institution."));
    }
  };

  const submitDepartment = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await authedFetch("/admin/departments", {
        method: "POST",
        body: JSON.stringify(departmentForm),
      });
      setDepartmentForm((current) => ({ ...current, name: "", head_name: "", head_email: "" }));
      setToast("Department added.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to add department."));
    }
  };

  const submitHead = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await authedFetch("/admin/heads", {
        method: "POST",
        body: JSON.stringify(headForm),
      });
      setCreatedPopup({
        title: "Admin Head Created",
        data: { name: headForm.name, email: headForm.email, password: headForm.password }
      });
      setHeadForm((current) => ({ ...current, name: "", email: "", password: "" }));
      setToast("Institution head access created.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to create institution head."));
    }
  };

  const submitCourse = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const payload: { title: string; description: string; institution_id?: string } = { ...courseForm };
      if (!payload.institution_id) delete payload.institution_id;
      if (admin?.role !== "super_admin" && admin?.institution_id) {
        payload.institution_id = admin.institution_id;
      }
      await authedFetch("/admin/courses", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setCourseForm({ title: "", description: "", institution_id: "" });
      setToast("Course added successfully.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to add course."));
    }
  };

  const submitQuestion = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const payload = {
        ...questionForm,
        options: questionForm.options.split(",").map(s => s.trim()).filter(Boolean)
      };
      const result = await authedFetch<{ question_set?: QuestionSet | null }>("/admin/questions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (result.question_set) {
        setQuestionSets((current) => [result.question_set as QuestionSet, ...current.filter((item) => item.id !== result.question_set?.id)]);
      }
      setQuestionForm({ dimension: "Algorithms", difficulty: "Basic", question_type: "MCQ", scenario: "", question_text: "", options: "", correct_answer: "A", explanation: "" });
      setToast("Question added to bank.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to add question."));
    }
  };

  const submitChangePassword = async (event: FormEvent) => {
    event.preventDefault();
    try {
      if (changePasswordForm.new_password.length < 8) {
        throw new Error("New password must be at least 8 characters");
      }
      await authedFetch("/admin/change-password", {
        method: "POST",
        body: JSON.stringify(changePasswordForm),
      });
      setToast("Password changed successfully.");
      setIsChangePasswordOpen(false);
      setChangePasswordForm({ current_password: "", new_password: "" });
    } catch (caught) {
      setError(errorMessage(caught, "Failed to change password."));
    }
  };

  const startMfaEnrollment = async () => {
    try {
      setIsMfaWorking(true);
      const enrollment = await authedFetch<{ secret: string; otpauth_url: string }>("/admin/mfa/enroll", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setMfaEnrollment(enrollment);
      setMfaCode("");
      setToast("MFA enrollment started. Add the secret to your authenticator app, then verify the code.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to start MFA enrollment."));
    } finally {
      setIsMfaWorking(false);
    }
  };

  const verifyMfaEnrollment = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setIsMfaWorking(true);
      const nextStatus = await authedFetch<AdminMfaStatus>("/admin/mfa/verify", {
        method: "POST",
        body: JSON.stringify({ code: mfaCode, secret: mfaEnrollment?.secret }),
      });
      setMfaStatus(nextStatus);
      setMfaEnrollment(null);
      setMfaCode("");
      setToast("MFA enabled for this admin account.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to verify MFA code."));
    } finally {
      setIsMfaWorking(false);
    }
  };

  const disableMfa = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setIsMfaWorking(true);
      const nextStatus = await authedFetch<AdminMfaStatus>("/admin/mfa", {
        method: "DELETE",
        body: JSON.stringify({ code: mfaDisableCode || undefined }),
      });
      setMfaStatus(nextStatus);
      setMfaDisableCode("");
      setToast(nextStatus.enabled ? "Global MFA is still required for this account." : "MFA disabled for this account.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to disable MFA."));
    } finally {
      setIsMfaWorking(false);
    }
  };

  const syncQuestionBank = async () => {
    try {
      setIsSyncingSupabase(true);
      const status = await authedFetch<QuestionBankStatus>("/admin/questions/sync", { method: "POST" });
      setQuestionBank(status);
      setToast(`Supabase question bank synced: ${status.total_questions} questions.`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to sync Supabase questions."));
    } finally {
      setIsSyncingSupabase(false);
    }
  };

  const downloadQuestionTemplate = async () => {
    try {
      const blob = await authedFetch<Blob>("/admin/questions/sample.csv");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "celtm-question-template.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      setToast("Question CSV template downloaded.");
    } catch (caught) {
      setError(errorMessage(caught, "Failed to download question CSV template."));
    }
  };

  const ingestQuestionCsv = async (file: File | null) => {
    if (!file) return;
    try {
      if (assignUploadedCsv && (!csvAssignmentForm.department_id || !csvAssignmentForm.starts_at || !csvAssignmentForm.ends_at)) {
        setError("Select department, start time, and end time before assigning an uploaded CSV.");
        return;
      }
      setIsIngestingCsv(true);
      const formData = new FormData();
      formData.append("file", file);
      if (assignUploadedCsv) {
        formData.append("assign_test", "true");
        formData.append("department_id", csvAssignmentForm.department_id);
        formData.append("test_title", csvAssignmentForm.title || file.name.replace(/\.csv$/i, ""));
        formData.append("starts_at", new Date(csvAssignmentForm.starts_at).toISOString());
        formData.append("ends_at", new Date(csvAssignmentForm.ends_at).toISOString());
        formData.append("duration_minutes", csvAssignmentForm.duration_minutes || "30");
        formData.append("mode", csvAssignmentForm.mode);
        formData.append("instructions", csvAssignmentForm.instructions);
      }
      const result = await authedFetch<{
        inserted: number;
        errors: Array<{ row: number; error: string }>;
        question_bank: QuestionBankStatus;
        question_set?: QuestionSet | null;
        assignment?: AssessmentAssignment | null;
        assignment_error?: string | null;
      }>(
        "/admin/ingest-csv",
        {
          method: "POST",
          body: formData,
        },
      );
      setQuestionBank(result.question_bank);
      if (result.question_set) {
        setQuestionSets((current) => [result.question_set as QuestionSet, ...current.filter((item) => item.id !== result.question_set?.id)]);
      }
      if (result.assignment_error) {
        setError(`CSV ingested, but assignment was not created: ${result.assignment_error}`);
      }
      if (result.errors.length) {
        setError(`${result.errors.length} CSV rows failed. First error: row ${result.errors[0].row} - ${result.errors[0].error}`);
      } else {
        setCreatedPopup({
          title: "CSV Ingested Successfully",
          data: {
            "Questions Added": result.inserted,
            "Assigned": result.assignment ? "Yes" : "No",
            "Assignment Title": result.assignment?.title || "N/A"
          }
        });
      }
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to ingest questions CSV."));
    } finally {
      setIsIngestingCsv(false);
      if (csvInputRef.current) csvInputRef.current.value = "";
    }
  };

  const submitAssignment = async (event: FormEvent) => {
    event.preventDefault();
    try {
      if (!assignmentForm.starts_at || !assignmentForm.ends_at) {
        setError("Select start and end time before assigning a test.");
        return;
      }
      const payload = {
        ...assignmentForm,
        question_set_id: assignmentForm.question_set_id || undefined,
        duration_minutes: Number(assignmentForm.duration_minutes || 30),
        starts_at: new Date(assignmentForm.starts_at).toISOString(),
        ends_at: new Date(assignmentForm.ends_at).toISOString(),
      };
      await authedFetch("/admin/assessment-assignments", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setAssignmentForm((current) => ({ ...current, title: "", starts_at: "", ends_at: "", instructions: "", question_set_id: "" }));
      setToast("Department test assigned successfully.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to assign test."));
    }
  };

  const resetAdminPassword = async (event: FormEvent) => {
    event.preventDefault();
    try {
      if (!resetForm.account_id || !resetForm.password) {
        setError("Select an admin account and enter a new password.");
        return;
      }
      await authedFetch(`/admin/admin-accounts/${resetForm.account_id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ password: resetForm.password }),
      });
      setCreatedPopup({
        title: "Admin Password Reset",
        data: {
          account: adminAccounts.find((item) => item.id === resetForm.account_id)?.email || resetForm.account_id,
          password: resetForm.password,
        },
      });
      setResetForm({ account_id: "", password: "" });
      setToast("Admin password reset and stored in the database.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to reset admin password."));
    }
  };

  const terminateAssignment = async (assignment: AssessmentAssignment) => {
    try {
      await authedFetch(`/admin/assessment-assignments/${assignment.id}/terminate`, {
        method: "POST",
        body: JSON.stringify({ reason: "Terminated from admin dashboard" }),
      });
      setToast(`Terminated ${assignment.title}.`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught, "Failed to terminate assessment."));
    }
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    void load(search);
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-on-background">
        <CeltmProgressLoader
          title="Loading admin console"
          caption="Cooking your admin view"
          minHeightClassName="min-h-screen"
          stages={["Checking admin session", "Loading institutions", "Fetching student progress", "Preparing controls"]}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-on-background px-5 py-8 md:px-10 transition-colors duration-300">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-[1500px] space-y-8"
      >
        <header className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between clay-card p-6">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">CELTM Admin</p>
            <h1 className="mt-2 text-4xl font-black tracking-tight">{isSuperAdmin ? "Super Admin Console" : "Institution Progress Console"}</h1>
            <p className="mt-2 text-sm font-semibold text-on-surface-variant">
              {admin?.email} - {isSuperAdmin ? "can manage institutes and heads" : "can monitor assigned institute students"}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => void exportStudentsCsv()}
              disabled={isExporting === "students-csv"}
              className="flex items-center gap-2 rounded-2xl bg-surface-container-high hover:bg-surface-container-highest px-4 py-2 text-xs font-black uppercase tracking-widest text-on-surface transition-colors"
            >
              <AppIcon name="text_snippet" className="h-4 w-4" />
              {isExporting === "students-csv" ? "Exporting..." : "Export CSV"}
            </button>
            <button
              onClick={() => void exportStudentsPdf()}
              disabled={isExporting === "students-pdf"}
              className="flex items-center gap-2 rounded-2xl bg-primary/10 hover:bg-primary/20 px-4 py-2 text-xs font-black uppercase tracking-widest text-primary transition-colors disabled:opacity-60"
            >
              <AppIcon name="file_download" className="h-4 w-4" />
              {isExporting === "students-pdf" ? "Exporting..." : "Export PDF"}
            </button>
            <button
              onClick={toggleTheme}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-container-high hover:bg-surface-container-highest transition-colors"
              aria-label="Toggle dark mode"
            >
              <AppIcon name={isDarkMode ? "light_mode" : "dark_mode"} className="h-5 w-5 text-on-surface" />
            </button>
            <button
              onClick={() => setIsChangePasswordOpen(true)}
              className="flex items-center gap-2 rounded-2xl bg-surface-container-high hover:bg-surface-container-highest px-4 py-2 text-xs font-black uppercase tracking-widest text-on-surface transition-colors"
            >
              <AppIcon name="lock" className="h-4 w-4" />
              Change Password
            </button>
            <button onClick={logout} className="rounded-full bg-error/10 hover:bg-error/20 px-6 py-3 text-[11px] font-black uppercase tracking-widest text-error transition-colors">
              Logout
            </button>
          </div>
        </header>

        {toast ? <div className="rounded-3xl border border-success/20 bg-success/10 px-5 py-4 text-sm font-bold text-success">{toast}</div> : null}
        {error ? <div className="rounded-3xl border border-error/20 bg-error/10 px-5 py-4 text-sm font-bold text-error">{error}</div> : null}

        <section className="clay-card p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Account security</p>
              <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Multi-factor authentication</h2>
              <p className="mt-2 text-sm font-semibold text-on-surface-variant">
                Status: {mfaStatus?.enabled ? "Enabled" : "Not enabled"}{mfaStatus?.required ? " / Required" : ""}
              </p>
            </div>
            <button
              type="button"
              disabled={isMfaWorking}
              onClick={() => void startMfaEnrollment()}
              className="rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-widest text-on-primary transition-colors hover:bg-primary-dim disabled:opacity-60"
            >
              {mfaStatus?.enabled ? "Rotate MFA" : "Enable MFA"}
            </button>
          </div>

          {mfaEnrollment ? (
            <form onSubmit={verifyMfaEnrollment} className="mt-5 grid gap-4 lg:grid-cols-[1.5fr_0.7fr_auto] lg:items-end">
              <Input label="Authenticator secret" value={mfaEnrollment.secret} onChange={() => undefined} required={false} />
              <Input label="6-digit code" value={mfaCode} onChange={setMfaCode} inputMode="numeric" maxLength={6} />
              <button
                type="submit"
                disabled={isMfaWorking || mfaCode.length < 6}
                className="rounded-2xl bg-success px-5 py-3.5 text-[11px] font-black uppercase tracking-widest text-white transition-colors disabled:opacity-60"
              >
                Verify
              </button>
            </form>
          ) : null}

          {mfaStatus?.enabled ? (
            <form onSubmit={disableMfa} className="mt-5 grid gap-4 lg:grid-cols-[0.7fr_auto] lg:items-end">
              <Input label="Code to disable" value={mfaDisableCode} onChange={setMfaDisableCode} inputMode="numeric" maxLength={6} required={false} />
              <button
                type="submit"
                disabled={isMfaWorking}
                className="rounded-2xl bg-error/10 px-5 py-3.5 text-[11px] font-black uppercase tracking-widest text-error transition-colors hover:bg-error/20 disabled:opacity-60"
              >
                Disable MFA
              </button>
            </form>
          ) : null}
        </section>

        {isSuperAdmin ? (
          <section className="grid gap-5 xl:grid-cols-4">
            <AdminForm title="Add institution" onSubmit={submitInstitution}>
              <Input label="Institution name" value={institutionForm.name} onChange={(value) => setInstitutionForm({ ...institutionForm, name: value })} />
              <Input label="Email domain (without @)" value={institutionForm.domain} onChange={(value) => setInstitutionForm({ ...institutionForm, domain: value })} placeholder="iitmandi.ac.in" />
              <p className="text-xs font-semibold leading-5 text-on-surface-variant">
                Add the institute email domain only. Write the part after @, for example iitmandi.ac.in.
              </p>
            </AdminForm>

            <AdminForm title="Add department" onSubmit={submitDepartment}>
              <Select label="Institution" value={departmentForm.institution_id} onChange={(value) => setDepartmentForm({ ...departmentForm, institution_id: value })} options={institutions.map((item) => ({ value: item.id, label: item.name }))} />
              <Input label="Department" value={departmentForm.name} onChange={(value) => setDepartmentForm({ ...departmentForm, name: value })} />
              <Input label="Head name optional" value={departmentForm.head_name} onChange={(value) => setDepartmentForm({ ...departmentForm, head_name: value })} />
              <Input label="Head email optional" value={departmentForm.head_email} onChange={(value) => setDepartmentForm({ ...departmentForm, head_email: value })} />
            </AdminForm>

            <AdminForm title="Create HOD/admin access" onSubmit={submitHead}>
              <Select label="Institution" value={headForm.institution_id} onChange={(value) => setHeadForm({ ...headForm, institution_id: value, department_id: "" })} options={institutions.map((item) => ({ value: item.id, label: item.name }))} />
              <Select label="Department" value={headForm.department_id} onChange={(value) => setHeadForm({ ...headForm, department_id: value })} options={(selectedInstitution?.departments || []).map((item) => ({ value: item.id, label: item.name }))} />
              <Input label="Head name" value={headForm.name} onChange={(value) => setHeadForm({ ...headForm, name: value })} />
              <Input label="Head email" value={headForm.email} onChange={(value) => setHeadForm({ ...headForm, email: value })} />
              <Input label="Password" type="password" value={headForm.password} onChange={(value) => setHeadForm({ ...headForm, password: value })} />
            </AdminForm>

            <AdminForm title="Reset admin password" onSubmit={resetAdminPassword}>
              <Select
                label="Admin account"
                value={resetForm.account_id}
                onChange={(value) => setResetForm({ ...resetForm, account_id: value })}
                options={adminAccounts.map((item) => ({ value: item.id, label: `${item.email} (${item.role.replace("_", " ")})` }))}
              />
              <Input label="New password" type="password" value={resetForm.password} onChange={(value) => setResetForm({ ...resetForm, password: value })} />
              <p className="text-xs font-semibold leading-5 text-on-surface-variant">
                Passwords are stored as hashes in the database. The plain password is shown once after reset.
              </p>
            </AdminForm>
          </section>
        ) : null}

        <section className="grid gap-5 xl:grid-cols-2 mt-8">
          <AdminForm title="Add Course" onSubmit={submitCourse}>
            {isSuperAdmin && (
              <Select label="Institution (Optional)" value={courseForm.institution_id} onChange={(value) => setCourseForm({ ...courseForm, institution_id: value })} options={institutions.map((item) => ({ value: item.id, label: item.name }))} />
            )}
            <Input label="Course Title" value={courseForm.title} onChange={(value) => setCourseForm({ ...courseForm, title: value })} />
            <Input label="Description" value={courseForm.description} onChange={(value) => setCourseForm({ ...courseForm, description: value })} />
          </AdminForm>

          <div className="clay-card flex h-full flex-col p-6 border-outline-variant/50">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-xl font-black tracking-tight text-on-surface">Supabase question bank</h2>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  All assessments now use questions synced from Supabase.
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest ${
                questionBank?.status === "ready" ? "bg-success/10 text-success" : "bg-error/10 text-error"
              }`}>
                {questionBank?.status || "unknown"}
              </span>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Total" value={String(questionBank?.total_questions ?? 0)} />
              <Metric label="MCQ" value={String(questionBank?.mcq_count ?? 0)} />
              <Metric label="Situational" value={String(questionBank?.situational_count ?? 0)} />
              <Metric label="Written" value={String(questionBank?.descriptive_count ?? 0)} />
            </div>
            <p className="mt-4 text-sm leading-6 text-on-surface-variant">
              {questionBank?.message || "Sync Supabase to make subject assessments available."}
            </p>
            {isSuperAdmin ? (
              <>
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={isSyncingSupabase}
                    onClick={() => void syncQuestionBank()}
                    className="flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-widest text-on-primary transition-colors hover:bg-primary-dim disabled:opacity-50"
                  >
                    {isSyncingSupabase ? (
                      <span className="flex items-center gap-2">
                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-on-primary border-t-transparent" />
                        Syncing...
                      </span>
                    ) : "Sync Supabase"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void downloadQuestionTemplate()}
                    className="rounded-2xl bg-surface-container-high px-5 py-3 text-[11px] font-black uppercase tracking-widest text-on-surface transition-colors hover:bg-surface-container-highest"
                  >
                    Download CSV template
                  </button>
                  <button
                    type="button"
                    disabled={isIngestingCsv}
                    onClick={() => csvInputRef.current?.click()}
                    className="flex items-center gap-2 rounded-2xl bg-surface-container-high px-5 py-3 text-[11px] font-black uppercase tracking-widest text-on-surface transition-colors hover:bg-surface-container-highest disabled:opacity-50"
                  >
                    {isIngestingCsv ? (
                      <span className="flex items-center gap-2">
                        <span className="h-3 w-3 animate-spin rounded-full border-2 border-on-surface border-t-transparent" />
                        Ingesting...
                      </span>
                    ) : "Ingest CSV"}
                  </button>
                  <input
                    ref={csvInputRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(event) => void ingestQuestionCsv(event.target.files?.[0] ?? null)}
                  />
                </div>
                <div className="mt-5 rounded-3xl bg-surface-container-low p-4">
                  <label className="flex items-center gap-3 text-sm font-bold text-on-surface">
                    <input
                      type="checkbox"
                      checked={assignUploadedCsv}
                      onChange={(event) => setAssignUploadedCsv(event.target.checked)}
                      className="h-4 w-4 accent-primary"
                    />
                    Assign uploaded CSV as a scheduled test
                  </label>
                  {assignUploadedCsv ? (
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <Select label="Department" value={csvAssignmentForm.department_id} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, department_id: value })} options={assignableDepartments} />
                      <Input label="Test title" value={csvAssignmentForm.title} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, title: value })} placeholder="Uses CSV file name if blank" required={false} />
                      <Select label="Mode" value={csvAssignmentForm.mode} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, mode: value })} options={[{ value: "quick", label: "Quick" }, { value: "standard", label: "Standard" }, { value: "deep", label: "Deep" }]} />
                      <Input label="Duration minutes" type="number" value={csvAssignmentForm.duration_minutes} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, duration_minutes: value })} />
                      <Input label="Start date and time" type="datetime-local" value={csvAssignmentForm.starts_at} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, starts_at: value })} />
                      <Input label="End date and time" type="datetime-local" value={csvAssignmentForm.ends_at} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, ends_at: value })} />
                      <Input label="Instructions" value={csvAssignmentForm.instructions} onChange={(value) => setCsvAssignmentForm({ ...csvAssignmentForm, instructions: value })} required={false} />
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="mt-5 rounded-3xl bg-surface-container-low p-4 text-sm font-semibold leading-6 text-on-surface-variant">
                Question sync and CSV ingestion are restricted to the CELTM super admin.
              </p>
            )}
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-2">
          {isSuperAdmin ? (
            <AdminForm title="Add Supabase Question" onSubmit={submitQuestion}>
              <div className="grid grid-cols-2 gap-4">
                <Select label="Subject" value={questionForm.dimension} onChange={(value) => setQuestionForm({ ...questionForm, dimension: value })} options={subjectOptions.map((item) => ({ value: item, label: item }))} />
                <Select label="Difficulty" value={questionForm.difficulty} onChange={(value) => setQuestionForm({ ...questionForm, difficulty: value })} options={["Basic", "Intermediate", "Advanced"].map((item) => ({ value: item, label: item }))} />
              </div>
              <Select label="Question Type" value={questionForm.question_type} onChange={(value) => setQuestionForm({ ...questionForm, question_type: value })} options={[{ value: "MCQ", label: "MCQ" }, { value: "SITUATIONAL", label: "Situational" }, { value: "DESCRIPTIVE", label: "Written / Descriptive" }]} />
              <Input label="Scenario (Optional)" value={questionForm.scenario} onChange={(value) => setQuestionForm({ ...questionForm, scenario: value })} required={false} />
              <Input label="Question Text" value={questionForm.question_text} onChange={(value) => setQuestionForm({ ...questionForm, question_text: value })} />
              {questionForm.question_type !== "DESCRIPTIVE" ? (
                <>
                  <Input label="Options (comma separated)" value={questionForm.options} onChange={(value) => setQuestionForm({ ...questionForm, options: value })} />
                  <Input label="Correct Answer" value={questionForm.correct_answer} onChange={(value) => setQuestionForm({ ...questionForm, correct_answer: value.toUpperCase() })} placeholder="A" />
                </>
              ) : null}
              <Input label="Explanation / sample answer" value={questionForm.explanation} onChange={(value) => setQuestionForm({ ...questionForm, explanation: value })} required={false} />
            </AdminForm>
          ) : null}

          <AdminForm title="Assign Department Test" onSubmit={submitAssignment}>
            <Select label="Department" value={assignmentForm.department_id} onChange={(value) => setAssignmentForm({ ...assignmentForm, department_id: value })} options={assignableDepartments} />
            <Input label="Test title" value={assignmentForm.title} onChange={(value) => setAssignmentForm({ ...assignmentForm, title: value })} placeholder="Machine Learning Sprint" />
            <Select
              label="Question set optional"
              value={assignmentForm.question_set_id}
              onChange={(value) => setAssignmentForm({ ...assignmentForm, question_set_id: value })}
              options={questionSets.map((item) => ({ value: item.id, label: `${item.title} (${item.question_type}, ${item.question_count})` }))}
              required={false}
            />
            <div className="grid grid-cols-2 gap-4">
              <Select label="Subject" value={assignmentForm.category} onChange={(value) => setAssignmentForm({ ...assignmentForm, category: value })} options={subjectOptions.map((item) => ({ value: item, label: item }))} />
              <Select label="Type" value={assignmentForm.question_type} onChange={(value) => setAssignmentForm({ ...assignmentForm, question_type: value })} options={[{ value: "MCQ", label: "MCQ" }, { value: "SITUATIONAL", label: "Situational" }, { value: "MIXED", label: "Mixed" }, { value: "DESCRIPTIVE", label: "Written" }]} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Select label="Mode" value={assignmentForm.mode} onChange={(value) => setAssignmentForm({ ...assignmentForm, mode: value })} options={[{ value: "quick", label: "Quick" }, { value: "standard", label: "Standard" }, { value: "deep", label: "Deep" }]} />
              <Input label="Duration minutes" type="number" value={assignmentForm.duration_minutes} onChange={(value) => setAssignmentForm({ ...assignmentForm, duration_minutes: value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Start date and time" type="datetime-local" value={assignmentForm.starts_at} onChange={(value) => setAssignmentForm({ ...assignmentForm, starts_at: value })} />
              <Input label="End date and time" type="datetime-local" value={assignmentForm.ends_at} onChange={(value) => setAssignmentForm({ ...assignmentForm, ends_at: value })} />
            </div>
            <Input label="Instructions" value={assignmentForm.instructions} onChange={(value) => setAssignmentForm({ ...assignmentForm, instructions: value })} required={false} />
          </AdminForm>
        </section>

        <section className="clay-card p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-black tracking-tight text-on-surface">Scheduled tests</h2>
              <p className="mt-1 text-sm text-on-surface-variant">Department assignments created by admin users.</p>
            </div>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-primary">
              {assignments.length} tests
            </span>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {assignments.length ? assignments.map((assignment) => (
              <div key={assignment.id} className="flex h-full min-h-[150px] flex-col rounded-3xl bg-surface-container px-5 py-5">
                <div className="flex flex-1 items-start justify-between gap-4">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-primary">{assignment.question_type} / {assignment.mode}</p>
                    <h3 className="mt-2 text-lg font-black text-on-surface">{assignment.title}</h3>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      {assignment.category} - {new Date(assignment.starts_at).toLocaleString()} to {new Date(assignment.ends_at).toLocaleString()} - {assignment.duration_minutes} min
                    </p>
                    {assignment.question_count ? (
                      <p className="mt-1 text-xs font-bold text-on-surface-variant">{assignment.question_count} fixed questions from a question set</p>
                    ) : null}
                    {assignment.terminated_by_email ? (
                      <p className="mt-1 text-xs font-bold text-error">Terminated by {assignment.terminated_by_email}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest ${
                      assignment.status === "terminated" ? "bg-error/10 text-error" : "bg-success/10 text-success"
                    }`}>{assignment.status}</span>
                    {assignment.status !== "terminated" ? (
                      <button
                        type="button"
                        onClick={() => void terminateAssignment(assignment)}
                        className="rounded-full bg-error/10 px-3 py-2 text-[10px] font-black uppercase tracking-widest text-error transition hover:bg-error/20"
                      >
                        Terminate
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            )) : (
              <p className="rounded-3xl bg-surface-container px-5 py-5 text-sm text-on-surface-variant">No tests assigned yet.</p>
            )}
          </div>
        </section>

        {/* Modal for created items */}
        {createdPopup && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="w-full max-w-md rounded-3xl bg-surface p-8 shadow-2xl border border-outline-variant/20 relative"
            >
              <h2 className="text-xl font-black text-on-surface mb-2">{createdPopup.title}</h2>
              <p className="text-sm text-on-surface-variant mb-6">Please save these credentials securely. They will not be shown again.</p>

              <div className="space-y-4 bg-surface-container-lowest p-5 rounded-2xl border border-outline-variant/10">
                {Object.entries(createdPopup.data).map(([k, v]) => (
                  <div key={k}>
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{k.replace('_', ' ')}</p>
                    <p className="text-sm font-bold text-on-surface break-all">{String(v)}</p>
                  </div>
                ))}
              </div>

              <button
                onClick={() => setCreatedPopup(null)}
                className="mt-6 w-full rounded-2xl bg-primary px-5 py-4 text-[11px] font-black uppercase tracking-widest text-white transition hover:opacity-90"
              >
                I have saved them
              </button>
            </motion.div>
          </div>
        )}

        {isChangePasswordOpen ? (
          <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="w-full max-w-md rounded-[32px] bg-surface p-8 shadow-2xl border border-outline-variant/20">
              <h3 className="text-2xl font-black text-on-surface">Change Password</h3>
              <form onSubmit={submitChangePassword} className="mt-6 space-y-4">
                <PasswordField label="Current Password" value={changePasswordForm.current_password} onChange={(value) => setChangePasswordForm({ ...changePasswordForm, current_password: value })} />
                <PasswordField label="New Password (min 8 chars)" value={changePasswordForm.new_password} onChange={(value) => setChangePasswordForm({ ...changePasswordForm, new_password: value })} />
                <div className="mt-8 flex justify-end gap-3">
                  <button type="button" onClick={() => setIsChangePasswordOpen(false)} className="rounded-full bg-surface-container-high px-6 py-3 text-sm font-bold text-on-surface transition-colors hover:bg-surface-container-highest">
                    Cancel
                  </button>
                  <button type="submit" className="rounded-full bg-primary px-6 py-3 text-sm font-bold text-white transition-transform hover:scale-105 active:scale-95">
                    Update Password
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : null}

        <section className="clay-card p-6">
          <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-2xl font-black tracking-tight text-on-surface">Student progress</h2>
              <p className="mt-1 text-sm text-on-surface-variant">Ranked by global readiness score. Open a row to inspect strong points, weak points, and institute support actions.</p>
            </div>
            <form onSubmit={submitSearch} className="flex gap-2">
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search student"
                className="w-64 rounded-2xl border border-outline-variant bg-surface-container px-4 py-3 text-sm outline-none focus:border-primary/50 text-on-surface"
              />
              <button className="rounded-2xl bg-primary hover:bg-primary-dim px-5 py-3 text-[11px] font-black uppercase tracking-widest text-on-primary transition-colors">Search</button>
            </form>
          </div>

          <div className="overflow-x-auto custom-scroll pb-2">
            <table className="w-full min-w-[900px] border-separate border-spacing-y-3 text-left">
              <thead className="text-[10px] uppercase tracking-[0.18em] text-on-surface-variant">
                <tr>
                  <th className="px-4">Rank</th>
                  <th className="px-4">Student</th>
                  <th className="px-4">Institute</th>
                  <th className="px-4">Target</th>
                  <th className="px-4">Resume</th>
                  <th className="px-4">Assessment</th>
                  <th className="px-4">Global readiness</th>
                </tr>
              </thead>
              <tbody>
                {students.map((student, index) => (
                  <tr key={student.user_id} onClick={() => void openStudentDetail(student)} className="cursor-pointer rounded-3xl bg-surface-container hover:bg-surface-container-high text-sm transition-colors text-on-surface">
                    <td className="rounded-l-3xl px-4 py-4 font-black text-primary">#{index + 1}</td>
                    <td className="px-4 py-4">
                      <p className="font-black">{student.name}</p>
                      <p className="text-xs text-on-surface-variant">{student.email}</p>
                    </td>
                    <td className="px-4 py-4">{student.institution_name || "Not set"} / {student.department_name || "Not set"}</td>
                    <td className="px-4 py-4">{student.target_role || "Pending"}</td>
                    <td className="px-4 py-4">{student.resume_score == null ? "Pending" : `${Math.round(student.resume_score)}%`}</td>
                    <td className="px-4 py-4">{student.assessment_score == null ? "Pending" : `${Math.round(student.assessment_score)}%`}</td>
                    <td className="rounded-r-3xl px-4 py-4 text-2xl font-black text-primary">{Math.round(student.readiness_score)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {students.length === 0 && (
              <div className="py-12 text-center text-sm font-semibold text-on-surface-variant">
                No students found.
              </div>
            )}
          </div>
        </section>
      </motion.div>

      {selectedStudent ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-5 backdrop-blur-md">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-h-[90vh] w-full max-w-4xl overflow-y-auto custom-scroll rounded-[36px] clay-card p-7 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Student detail</p>
                <h2 className="mt-2 text-3xl font-black text-on-surface">{selectedStudent.name}</h2>
                <p className="mt-1 text-sm text-on-surface-variant">{selectedStudent.email}</p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    void downloadPassport(selectedStudent.user_id, selectedStudent.name);
                  }}
                  disabled={isExporting === selectedStudent.user_id}
                  className="rounded-full bg-primary/10 hover:bg-primary/20 px-5 py-2.5 text-xs font-bold text-primary transition-colors flex items-center gap-2"
                >
                  <AppIcon name="download" className="h-4 w-4" />
                  {isExporting === selectedStudent.user_id ? "Exporting..." : "Passport"}
                </button>
                <button
                  onClick={() => {
                    setSelectedStudent(null);
                    setLoadingStudentId(null);
                  }}
                  className="rounded-full bg-surface-container-high hover:bg-surface-container-highest px-4 py-2.5 text-sm font-bold text-on-surface transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Metric label="Global readiness" value={`${Math.round(selectedStudent.readiness_score)}%`} />
              <Metric label="Resume" value={selectedStudent.resume_score == null ? "Pending" : `${Math.round(selectedStudent.resume_score)}%`} />
              <Metric label="Objective" value={selectedStudent.assessment_score == null ? "Pending" : `${Math.round(selectedStudent.assessment_score)}%`} />
              <Metric label="Written" value={selectedStudent.written_score == null ? "Pending" : `${Math.round(selectedStudent.written_score)}%`} />
              <Metric label="Credential" value={selectedStudent.credential_score == null ? "Pending" : `${Math.round(selectedStudent.credential_score)}%`} />
            </div>
            {selectedStudent.readiness_components?.length ? (
              <div className="mt-5 rounded-3xl bg-surface-container p-5 border border-outline-variant/30">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="text-sm font-black uppercase tracking-wider text-on-surface">Readiness components</h3>
                  <p className="text-xs font-bold text-on-surface-variant">
                    {selectedStudent.readiness_formula || "Active weighted average"}
                  </p>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-4">
                  {selectedStudent.readiness_components.map((component) => (
                    <div key={component.key} className="rounded-2xl bg-surface px-4 py-3">
                      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{component.label}</p>
                      <div className="mt-2 flex items-baseline justify-between gap-2">
                        <span className="text-lg font-black text-on-surface">{Math.round(component.score)}%</span>
                        <span className="text-[10px] font-black uppercase tracking-widest text-primary">
                          {Math.round(component.effective_weight * 100)}% weight
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="mt-6">
              {loadingStudentId === selectedStudent.user_id ? (
                <div className="rounded-3xl border border-outline-variant/30 bg-surface-container p-5 text-sm font-bold text-on-surface-variant">
                  Loading subject-wise assessment progress...
                </div>
              ) : (
                <SubjectProgressCards
                  subjects={selectedStudent.subject_progress ?? []}
                  title="Subject-wise assessment progress"
                  description="Repeated test improvement grouped by subject for HOD review."
                />
              )}
            </div>
            <div className="mt-6 grid gap-5 lg:grid-cols-3">
              <DetailList title="5 strong points" items={selectedStudent.strong_points} />
              <DetailList title="4 weak points" items={selectedStudent.weak_points} />
              <DetailList title="How institute can help" items={selectedStudent.institute_help} />
            </div>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}

function AdminForm({ title, onSubmit, children }: { title: string; onSubmit: (event: FormEvent) => void; children: React.ReactNode }) {
  return (
    <form onSubmit={onSubmit} className="clay-card flex h-full flex-col p-6 border-outline-variant/50">
      <h2 className="mb-5 text-xl font-black tracking-tight text-on-surface">{title}</h2>
      <div className="flex-1 space-y-4">{children}</div>
      <button className="mt-6 w-full rounded-2xl bg-primary hover:bg-primary-dim px-5 py-3.5 text-[11px] font-black uppercase tracking-widest text-on-primary transition-colors">Save</button>
    </form>
  );
}

function Input({
  label,
  value,
  onChange,
  placeholder = "",
  type = "text",
  required = true,
  inputMode,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
  inputMode?: "none" | "text" | "decimal" | "numeric" | "tel" | "search" | "email" | "url";
  maxLength?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{label}</span>
      <input
        required={required}
        type={type}
        value={value}
        inputMode={inputMode}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-outline-variant bg-surface-container px-4 py-3 text-sm outline-none focus:border-primary/50 text-on-surface"
      />
    </label>
  );
}

function PasswordField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const [show, setShow] = useState(false);
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{label}</span>
      <div className="relative">
        <input required type={show ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-2xl border border-outline-variant bg-surface-container px-4 py-3 pr-12 text-sm outline-none focus:border-primary/50 text-on-surface" />
        <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-on-surface-variant hover:text-on-surface">
          <AppIcon name={show ? "visibility_off" : "visibility"} className="h-5 w-5" />
        </button>
      </div>
    </label>
  );
}

function Select({ label, value, onChange, options, required = true }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }>; required?: boolean }) {
  return (
    <ThemedSelect
      label={label}
      required={required}
      value={value}
      onChange={onChange}
      placeholder="Select"
      options={options}
      buttonClassName="bg-surface-container"
    />
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="h-full rounded-3xl bg-surface-container p-6 text-center border border-outline-variant/30 lift-card flex flex-col justify-center">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{label}</p>
      <p className={`mt-2 font-black text-primary ${value === "Pending" ? "text-2xl" : "text-4xl"}`}>{value}</p>
    </div>
  );
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="h-full rounded-3xl bg-surface-container p-6 border border-outline-variant/30">
      <h3 className="text-sm font-black uppercase tracking-wider text-on-surface">{title}</h3>
      <ul className="mt-5 space-y-3">
        {(items.length ? items : ["Pending"]).map((item) => (
          <li key={item} className="text-sm leading-6 text-on-surface flex items-start">
            <span className="mr-2.5 mt-0.5 text-[10px] text-primary">-</span>
            <span className="flex-1 opacity-90">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
