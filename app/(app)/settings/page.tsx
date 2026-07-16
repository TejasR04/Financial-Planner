import type { Metadata } from "next";
import { PageContainer, PageHeader } from "@/components/page-container";
import { SettingsForms } from "@/components/settings-forms";

export const metadata: Metadata = {
  title: "Settings — Meridian",
  description:
    "Manage your profile, planning assumptions, linked institutions, and notifications.",
};

export default function SettingsPage() {
  return (
    <PageContainer className="max-w-[1040px]">
      <PageHeader
        title="Settings"
        description="Manage your profile, planning defaults, connected institutions, and alerts."
      />
      <SettingsForms />
    </PageContainer>
  );
}
