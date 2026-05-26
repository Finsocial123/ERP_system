"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  CreditCard,
  IndianRupee,
  ReceiptText,
  WalletCards,
} from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Card } from "@/components/ui";
import { apiFetch, getSavedAuth } from "@/lib/api";
import type { FeePortalResponse } from "@/types";
import FeeManager from "./FeeManager";

const ADMIN_ROLES = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"];

function money(value?: number | null) {
  return `₹${Number(value || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function statusBadge(status: string) {
  const tone =
    status === "PAID"
      ? "bg-emerald-50 text-emerald-700"
      : status === "PARTIAL"
        ? "bg-amber-50 text-amber-700"
        : status === "OVERDUE"
          ? "bg-red-50 text-red-700"
          : "bg-slate-100 text-slate-700";
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>
      {status}
    </span>
  );
}

function StudentFeeView() {
  const [data, setData] = useState<FeePortalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payingRecordId, setPayingRecordId] = useState<number | null>(null);
  const [paymentError, setPaymentError] = useState("");
  const [paymentSuccess, setPaymentSuccess] = useState("");

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await apiFetch<FeePortalResponse>("/fees/portal"));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load fee records",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handlePayOnline = async (recordId: number) => {
    setPayingRecordId(recordId);
    setPaymentError("");
    setPaymentSuccess("");

    try {
      // Step 1 — get order from backend
      const order = await apiFetch<any>("/fees/razorpay/create-order", {
        method: "POST",
        body: JSON.stringify({ student_fee_record_id: recordId }),
      });

      // Step 2 — open Razorpay popup
      const rzp = new (window as any).Razorpay({
        key: order.key,
        amount: order.amount,
        currency: "INR",
        order_id: order.order_id,
        name: "School Fee Payment",
        description: order.fee_title,
        prefill: { name: order.student_name },
        handler: async (response: any) => {
          try {
            // Step 3 — verify with backend (creates FeePayment record)
            await apiFetch("/fees/razorpay/verify-payment", {
              method: "POST",
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                student_fee_record_id: recordId,
              }),
            });
            setPaymentSuccess("Payment successful! Receipt has been generated.");
            // Refresh fee records
            await loadData();
          } catch (err) {
            setPaymentError(
              err instanceof Error ? err.message : "Payment verification failed",
            );
          } finally {
            setPayingRecordId(null);
          }
        },
        modal: {
          ondismiss: () => {
            setPayingRecordId(null);
          },
        },
      });
      rzp.open();
    } catch (err) {
      setPaymentError(
        err instanceof Error ? err.message : "Failed to initiate payment",
      );
      setPayingRecordId(null);
    }
  };
  return (
    <AppSection
      title={data?.role === "PARENT" ? "Child Fees" : "My Fees"}
      description="View assigned fees, pending balance, payment status and recent receipts."
    >
      {error && (
        <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {paymentError && (
        <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
          {paymentError}
        </p>
      )}
      {paymentSuccess && (
        <p className="mb-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {paymentSuccess}
        </p>
      )}
      {loading ? (
        <Card>
          <p className="text-sm text-slate-500">Loading fee records...</p>
        </Card>
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <div className="flex items-center gap-3">
                <IndianRupee className="text-slate-500" size={20} />
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Total Fee
                  </p>
                  <p className="text-xl font-bold text-slate-900">
                    {money(data.summary.total_billable)}
                  </p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <WalletCards className="text-slate-500" size={20} />
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Paid
                  </p>
                  <p className="text-xl font-bold text-emerald-700">
                    {money(data.summary.total_paid)}
                  </p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <AlertCircle className="text-slate-500" size={20} />
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Pending
                  </p>
                  <p className="text-xl font-bold text-amber-700">
                    {money(data.summary.total_pending)}
                  </p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <CreditCard className="text-slate-500" size={20} />
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Records
                  </p>
                  <p className="text-xl font-bold text-slate-900">
                    {data.summary.total_records}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          <Card className="overflow-hidden p-0">
            <div className="border-b border-slate-100 p-5">
              <h2 className="font-semibold text-slate-900">Fee Records</h2>
              <p className="text-sm text-slate-500">
                Pending and paid fee records assigned by school admin.
              </p>
            </div>
            {data.records.length === 0 ? (
              <p className="p-5 text-sm text-slate-500">
                No fee record assigned yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Student</th>
                      <th className="px-4 py-3">Fee</th>
                      <th className="px-4 py-3">Due Date</th>
                      <th className="px-4 py-3">Amount</th>
                      <th className="px-4 py-3">Paid</th>
                      <th className="px-4 py-3">Pending</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.records.map((record) => (
                      <tr key={record.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900">
                            {record.student_name || "Student"}
                          </p>
                          <p className="text-xs text-slate-500">
                            {record.admission_no || "-"}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {record.title}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {record.due_date || "-"}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {money(
                            record.amount +
                              record.fine_amount -
                              record.discount_amount,
                          )}
                        </td>
                        <td className="px-4 py-3 text-emerald-700">
                          {money(record.paid_amount)}
                        </td>
                        <td className="px-4 py-3 text-amber-700">
                          {money(record.balance_amount)}
                        </td>
                        <td className="px-4 py-3">
                          {statusBadge(record.status)}
                        </td>
                        <td className="px-4 py-3">
                          {record.balance_amount > 0 && record.status !== "WAIVED" ? (
                            <button
                              onClick={() => handlePayOnline(record.id)}
                              disabled={payingRecordId === record.id}
                              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
                            >
                              <CreditCard size={14} />
                              {payingRecordId === record.id ? "Processing..." : "Pay"}
                            </button>
                          ) : (
                            <span className="text-xs text-slate-500">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card className="overflow-hidden p-0">
            <div className="border-b border-slate-100 p-5">
              <h2 className="flex items-center gap-2 font-semibold text-slate-900">
                <ReceiptText size={18} /> Recent Receipts
              </h2>
              <p className="text-sm text-slate-500">
                Latest payment entries recorded by the school.
              </p>
            </div>
            {data.payments.length === 0 ? (
              <p className="p-5 text-sm text-slate-500">
                No payments recorded yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Receipt</th>
                      <th className="px-4 py-3">Student</th>
                      <th className="px-4 py-3">Fee</th>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Mode</th>
                      <th className="px-4 py-3">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.payments.map((payment) => (
                      <tr key={payment.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {payment.receipt_no}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {payment.student_name || "-"}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {payment.fee_title || "-"}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {payment.payment_date}
                        </td>
                        <td className="px-4 py-3 text-slate-700">
                          {payment.payment_mode}
                        </td>
                        <td className="px-4 py-3 font-semibold text-emerald-700">
                          {money(payment.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : null}
    </AppSection>
  );
}

export default function FeePortal() {
  const auth = getSavedAuth();
  const role = auth?.user.role;

  if (role && ADMIN_ROLES.includes(role)) {
    return <FeeManager />;
  }

  if (role === "STUDENT" || role === "PARENT") {
    return <StudentFeeView />;
  }

  return (
    <AppSection
      title="Fees"
      description="Fee records are available for admin, student and parent roles."
    >
      <Card>
        <p className="text-sm text-slate-500">
          You do not have permission to open fee management.
        </p>
      </Card>
    </AppSection>
  );
}